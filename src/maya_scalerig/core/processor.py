"""Main Maya ASCII processing pipeline."""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import Any, Optional

from maya_scalerig.core.constants import (
    ADV_EYELID_AIM_END_RE,
    ADV_EYELID_MAIN_JOINT_RE,
    ADV_EYELID_MM_RE,
    ARRAY_COORD_ATTRS,
    BASE_SCALAR_ATTRS,
    BASE_VECTOR_ATTRS,
    CREATE_RE,
    NAME_RE,
    NUM_RE,
    POLY_GENERATOR_ATTR_ALIASES,
    POLY_GENERATOR_DEFAULT_SCALAR_ATTRS_BY_TYPE,
    POLY_GENERATOR_SCALAR_ATTRS_BY_TYPE,
    QUOTED_RE,
    REST_LENGTH_ATTRS,
    REST_NODE_TYPES,
    SELECT_RE,
    SKIN_CLUSTER_BIND_PRE_MATRIX_ATTRS,
    TRANSLATE_LIMIT_ATTRS,
)
from maya_scalerig.core.options import Options
from maya_scalerig.core.scalers import (
    scale_addattr_default,
    scale_matrix_stmt,
    scale_nurbs_curve_cc,
    scale_nurbs_surface_cc,
    scale_point_array_stmt,
    scale_tail_all_values,
    scale_tail_first_value,
    scale_tail_number_indices,
)
from maya_scalerig.core.text_utils import (
    fmt_scaled,
    find_attr_ref,
    normalize_attr,
    resolve_node_and_attr,
    scale_tail_every_second_value,
    short_node_name,
    update_statement_state,
)

CONNECT_SKIN_INFLUENCE_RE = re.compile(r'connectAttr\s+"([^"]+)\.wm"\s+"([^"]+)\.ma\[(\d+)\]"')
CONNECT_DEST_RE = re.compile(r'connectAttr\s+"[^"]+"\s+"([^"]+)"')
SETATTR_MATRIX_RE = re.compile(r'setAttr\s+"([^"]+)"\s+-type\s+"matrix"(.*?);', re.S)
SETATTR_TRANSLATE_RE = re.compile(r'setAttr\s+"\.t"(?:\s+-type\s+"[^"]+")?(.*?);', re.S)


def _split_adv_side_name(node_name: str, suffix: str = '') -> Optional[tuple[str, str]]:
    match = re.match(r'^(.*)_([RL])$', node_name)
    if not match:
        return None
    base, side = match.groups()
    if suffix and not base.endswith(suffix):
        return None
    return base, side


def _invert_3x3_row0(values: list[float]) -> Optional[tuple[float, float, float]]:
    if len(values) < 11:
        return None
    a00, a01, a02 = values[0], values[1], values[2]
    a10, a11, a12 = values[4], values[5], values[6]
    a20, a21, a22 = values[8], values[9], values[10]
    det = (
        a00 * (a11 * a22 - a12 * a21)
        - a01 * (a10 * a22 - a12 * a20)
        + a02 * (a10 * a21 - a11 * a20)
    )
    if abs(det) < 1e-12:
        return None
    return (
        (a11 * a22 - a12 * a21) / det,
        (a02 * a21 - a01 * a22) / det,
        (a01 * a12 - a02 * a11) / det,
    )


def _iter_create_blocks(text: str):
    current_type = None
    current_name = None
    buffer: list[str] = []
    for line in text.splitlines(True):
        cm = CREATE_RE.match(line)
        if cm:
            if current_name is not None:
                yield current_type, current_name, ''.join(buffer)
            current_type = cm.group(1)
            nm = NAME_RE.search(cm.group(2))
            current_name = nm.group(1) if nm else None
            buffer = [line]
        elif current_name is not None:
            buffer.append(line)
    if current_name is not None:
        yield current_type, current_name, ''.join(buffer)


def _remember_node_attr(store: dict[str, set[str]], node_name: Optional[str], attr: str) -> None:
    if not node_name:
        return
    node_short = short_node_name(node_name) or node_name
    attr_norm = normalize_attr(attr)
    store.setdefault(node_name, set()).add(attr_norm)
    store.setdefault(node_short, set()).add(attr_norm)


def build_scene_metadata(src: Path) -> dict[str, Any]:
    text = src.read_text(encoding='latin-1')
    aim_x_by_node: dict[str, float] = {}
    mm_inv_x_by_node: dict[str, tuple[float, float, float]] = {}
    skin_influences: dict[tuple[str, int], str] = {}
    node_names: set[str] = set()
    poly_generator_attrs: dict[str, set[str]] = {}
    connected_input_attrs: dict[str, set[str]] = {}

    for node_type, node_name, block in _iter_create_blocks(text):
        node_type_l = (node_type or '').lower()
        if node_name:
            node_names.add(node_name)
        if node_name and node_type_l in POLY_GENERATOR_DEFAULT_SCALAR_ATTRS_BY_TYPE:
            for sm in re.finditer(r'\bsetAttr\b.*?;', block, re.S):
                attr_ref = find_attr_ref(sm.group(0))
                if not attr_ref:
                    continue
                _node, attr = resolve_node_and_attr(attr_ref[2], node_name)
                _remember_node_attr(poly_generator_attrs, node_name, attr)
        if node_name and ADV_EYELID_AIM_END_RE.match(node_name):
            tm = SETATTR_TRANSLATE_RE.search(block)
            if tm:
                values = [float(m.group(0)) for m in NUM_RE.finditer(tm.group(1))]
                if values:
                    aim_x_by_node[node_name] = values[0]
        if node_name and ADV_EYELID_MM_RE.match(node_name):
            for mm in SETATTR_MATRIX_RE.finditer(block):
                if normalize_attr(mm.group(1)) == '.i[]' and mm.group(1).startswith('.i[0]'):
                    values = [float(m.group(0)) for m in NUM_RE.finditer(mm.group(2))]
                    row0 = _invert_3x3_row0(values)
                    if row0:
                        mm_inv_x_by_node[node_name] = row0
                    break

    for cm in CONNECT_SKIN_INFLUENCE_RE.finditer(text):
        src_attr, skin_node, index_s = cm.groups()
        influence = short_node_name(src_attr)
        if influence:
            skin_influences[(short_node_name(skin_node) or skin_node, int(index_s))] = influence

    for cm in CONNECT_DEST_RE.finditer(text):
        dest = cm.group(1)
        node_name, attr = resolve_node_and_attr(dest, None)
        _remember_node_attr(connected_input_attrs, node_name, attr)

    return {
        'adv_eyelid_aim_x': aim_x_by_node,
        'adv_eyelid_mm_inv_x': mm_inv_x_by_node,
        'skin_influences': skin_influences,
        'node_names': node_names,
        'poly_generator_attrs': poly_generator_attrs,
        'connected_input_attrs': connected_input_attrs,
    }


def _adv_eyelid_related_nodes(influence: str) -> Optional[tuple[str, str]]:
    if not ADV_EYELID_MAIN_JOINT_RE.match(influence):
        return None
    if re.match(r'^upperLidMain(?:0|13)_[RL]$', influence):
        return None
    parts = _split_adv_side_name(influence)
    if not parts:
        return None
    base, side = parts
    return f'{base}AimEnd_{side}', f'{base}MM_{side}'


def correct_adv_eyelid_bind_pre_matrix(
    stmt: str,
    skin_node: str,
    attr: str,
    opts: Options,
    metadata: dict[str, Any],
) -> tuple[str, bool]:
    if opts.preset != 'adv' or not opts.fix_adv_eyelid_bind_pre_matrices:
        return stmt, False
    idx_match = re.search(r'\[(\d+)\]', attr)
    if not idx_match:
        return stmt, False
    influence = metadata.get('skin_influences', {}).get((skin_node, int(idx_match.group(1))))
    if not influence:
        return stmt, False
    related = _adv_eyelid_related_nodes(influence)
    if not related:
        return stmt, False
    aim_node, mm_node = related
    parts = _split_adv_side_name(influence)
    if not parts:
        return stmt, False
    base, side = parts
    if f'{base}AimMM_{side}' not in metadata.get('node_names', set()):
        return stmt, False
    aim_x = metadata.get('adv_eyelid_aim_x', {}).get(aim_node)
    inv_x = metadata.get('adv_eyelid_mm_inv_x', {}).get(mm_node)
    if aim_x is None or inv_x is None:
        return stmt, False

    marker = '-type "matrix"'
    pos = stmt.find(marker)
    if pos < 0:
        return stmt, False
    before = stmt[:pos + len(marker)]
    tail = stmt[pos + len(marker):]
    correction = [(opts.scale - 1.0) * aim_x * axis for axis in inv_x]
    number_index = 0
    changed = False

    def repl(match: re.Match[str]) -> str:
        nonlocal number_index, changed
        token = match.group(0)
        out = token
        if number_index in {12, 13, 14}:
            value = float(token) + correction[number_index - 12]
            out = fmt_scaled(str(value), 1.0)
            changed = True
        number_index += 1
        return out

    return before + NUM_RE.sub(repl, tail), changed


def _attr_seen_or_connected(attrs: set[str], canonical_attr: str) -> bool:
    aliases = POLY_GENERATOR_ATTR_ALIASES.get(canonical_attr, {canonical_attr})
    return bool(attrs & aliases)


def scaled_poly_generator_default_setattrs(
    node_name: Optional[str],
    node_type: Optional[str],
    opts: Options,
    report: Counter,
    metadata: dict[str, Any],
) -> str:
    node_type_l = (node_type or '').lower()
    defaults = POLY_GENERATOR_DEFAULT_SCALAR_ATTRS_BY_TYPE.get(node_type_l)
    if not node_name or not defaults:
        return ''

    seen = metadata.get('poly_generator_attrs', {}).get(node_name, set())
    connected = metadata.get('connected_input_attrs', {}).get(node_name, set())
    lines: list[str] = []
    for attr, default_value in defaults.items():
        if _attr_seen_or_connected(seen, attr) or _attr_seen_or_connected(connected, attr):
            continue
        scaled_value = fmt_scaled(default_value, opts.scale)
        lines.append(f'\tsetAttr "{attr}" {scaled_value};\n')
        report[f'{node_type_l}_default_{attr}_scalar_numbers'] += 1
    return ''.join(lines)

def process_setattr(
    stmt: str,
    current_node: Optional[str],
    current_type: Optional[str],
    node_types: dict[str, str],
    opts: Options,
    report: Counter,
    metadata: dict[str, Any],
) -> str:
    attr_ref = find_attr_ref(stmt)
    if not attr_ref:
        return stmt

    raw_attr = attr_ref[2]
    node_name, attr = resolve_node_and_attr(raw_attr, current_node)
    node_name_short = short_node_name(node_name)
    node_type = node_types.get(node_name or '', None) or node_types.get(node_name_short or '', None) or current_type
    node_type_l = (node_type or '').lower()
    node_name_s = node_name_short or current_node or ''
    base = normalize_attr(attr)

    if base == '.cc' and '-type "nurbsCurve"' in stmt:
        new, n = scale_nurbs_curve_cc(stmt, opts.scale)
        if n:
            report['nurbsCurve_cc_coordinate_numbers'] += n
        return new
    if base == '.cc' and '-type "nurbsSurface"' in stmt:
        new, n = scale_nurbs_surface_cc(stmt, opts.scale)
        if n:
            report['nurbsSurface_cc_coordinate_numbers'] += n
        return new

    if '-type "pointArray"' in stmt:
        new, n = scale_point_array_stmt(stmt, opts.scale)
        if n:
            report['pointArray_coordinate_numbers'] += n
        return new

    if '-type "matrix"' in stmt:
        if (
            node_type_l == 'skincluster'
            and base in SKIN_CLUSTER_BIND_PRE_MATRIX_ATTRS
            and not opts.scale_skin_bind_pre_matrices
        ):
            report['skinCluster_bindPreMatrix_skipped'] += 1
            return stmt
        new, n, kind = scale_matrix_stmt(stmt, opts.scale)
        if (
            node_type_l == 'skincluster'
            and base in SKIN_CLUSTER_BIND_PRE_MATRIX_ATTRS
            and opts.scale_skin_bind_pre_matrices
        ):
            fixed, did_fix = correct_adv_eyelid_bind_pre_matrix(new, node_name_s, attr, opts, metadata)
            if did_fix:
                new = fixed
                report['adv_eyelid_bindPreMatrix_corrected'] += 1
        if n:
            report[kind] += n
        return new

    if base in ARRAY_COORD_ATTRS:
        new, n = scale_tail_all_values(stmt, opts.scale)
        if n:
            report[f'{base}_coordinate_numbers'] += n
        return new

    if opts.preset == 'adv' and ADV_EYELID_AIM_END_RE.match(node_name_s):
        if base in {'.t', '.translate'}:
            new, n = scale_tail_number_indices(stmt, {1, 2}, opts.scale)
            if n:
                report['adv_eyelid_aimEnd_translate_yz_numbers'] += n
            return new
        if base in {'.tx', '.translatex'}:
            report['adv_eyelid_aimEnd_translate_x_skipped'] += 1
            return stmt
        if base in {'.ty', '.translatey', '.tz', '.translatez'}:
            new, n = scale_tail_all_values(stmt, opts.scale)
            if n:
                report[f'{base}_scalar_numbers'] += n
            return new

    poly_generator_attrs = POLY_GENERATOR_SCALAR_ATTRS_BY_TYPE.get(node_type_l)
    if poly_generator_attrs and base in poly_generator_attrs:
        new, n = scale_tail_all_values(stmt, opts.scale)
        if n:
            report[f'{node_type_l}_{base}_scalar_numbers'] += n
        return new

    vector_attrs = set(BASE_VECTOR_ATTRS) | opts.extra_vector_attrs
    if opts.scale_translate_limits:
        vector_attrs |= TRANSLATE_LIMIT_ATTRS
    if base in vector_attrs:
        new, n = scale_tail_all_values(stmt, opts.scale)
        if n:
            report[f'{base}_vector_numbers'] += n
        return new

    scalar_attrs = set(BASE_SCALAR_ATTRS) | opts.extra_scalar_attrs
    if base in scalar_attrs:
        new, n = scale_tail_all_values(stmt, opts.scale)
        if n:
            report[f'{base}_scalar_numbers'] += n
        return new

    if opts.scale_rest_constants and node_type_l in REST_NODE_TYPES and node_name_s and opts.rest_node_re.search(node_name_s):
        if base in REST_LENGTH_ATTRS:
            if opts.rest_vector_mode == 'all':
                new, n = scale_tail_all_values(stmt, opts.scale)
            else:
                new, n = scale_tail_first_value(stmt, opts.scale)
            if n:
                report[f'rest_length_utility_{opts.rest_vector_mode}_values'] += n
            return new

    if node_type_l == 'plusminusaverage' and base.startswith('.i3'):
        new, n = scale_tail_all_values(stmt, opts.scale)
        if n:
            report['plusMinusAverage_input3D_numbers'] += n
        return new

    if opts.preset == 'adv' and node_type_l == 'animcurveuu' and node_name_s:
        if re.search(r'^IKdistance.*Shape_(normal|antiPop)$', node_name_s) and base.startswith('.ktv'):
            new, n = scale_tail_all_values(stmt, opts.scale)
            if n:
                report['adv_IKdistance_animCurveUU_key_numbers'] += n
            return new

    if node_type_l == 'animcurveul' and base.startswith('.ktv') and opts.scale_sdk_linear_output:
        if opts.sdk_node_re.search(node_name_s):
            new, n = scale_tail_every_second_value(stmt, opts.scale)
            if n:
                report['animCurveUL_linear_output_key_values'] += n
            return new
        report['animCurveUL_skipped_by_name_filter'] += 1
        return stmt

    if node_type_l == 'animcurvetl' and base.startswith('.ktv') and opts.scale_linear_animation:
        new, n = scale_tail_every_second_value(stmt, opts.scale)
        if n:
            report['animCurveTL_translate_animation_key_values'] += n
        return new

    return stmt


def update_context_from_create(line: str, node_types: dict[str, str]) -> tuple[Optional[str], Optional[str]]:
    cm = CREATE_RE.match(line)
    if not cm:
        return None, None
    node_type = cm.group(1)
    nm = NAME_RE.search(cm.group(2))
    node_name = nm.group(1) if nm else None
    if node_name:
        node_types[node_name] = node_type
        node_types[short_node_name(node_name) or node_name] = node_type
    return node_name, node_type


def parse_select_context(line: str, node_types: dict[str, str]) -> tuple[Optional[str], Optional[str]]:
    """Best-effort parsing of select statements used by some .ma sections."""
    if not SELECT_RE.match(line):
        return None, None
    if ' -cl' in line or ' -clear' in line:
        return None, None
    quoted = [m.group(1) for m in QUOTED_RE.finditer(line)]
    target = quoted[-1] if quoted else None
    if not target:
        temp = line.strip().rstrip(';')
        parts = temp.split()
        candidates = [p for p in parts[1:] if not p.startswith('-')]
        if candidates:
            target = candidates[-1]
    target = short_node_name(target)
    return target, node_types.get(target or '')


def process_file(src: Path, dst: Path, opts: Options) -> Counter:
    report: Counter = Counter()
    metadata = build_scene_metadata(src)
    out_parts: list[str] = []
    node_types: dict[str, str] = {}
    current_node: Optional[str] = None
    current_type: Optional[str] = None
    injected_poly_default_nodes: set[str] = set()
    stmt_buf = ''
    in_stmt = False
    stmt_in_quote = False
    stmt_escaped = False

    def flush_poly_generator_defaults() -> None:
        if not current_node or current_node in injected_poly_default_nodes:
            return
        extra = scaled_poly_generator_default_setattrs(current_node, current_type, opts, report, metadata)
        if extra:
            out_parts.append(extra)
        injected_poly_default_nodes.add(current_node)

    def flush_stmt(statement: str) -> str:
        nonlocal current_node, current_type
        stripped = statement.lstrip()
        cm = CREATE_RE.match(statement)
        if cm:
            node_name, node_type = update_context_from_create(statement, node_types)
            current_node = node_name
            current_type = node_type
            return statement
        if stripped.startswith('addAttr'):
            new, n = scale_addattr_default(statement, opts.scale, opts.extra_addattr_names)
            if n:
                report['addAttr_spatial_default_values'] += n
            return new
        if stripped.startswith('setAttr'):
            return process_setattr(statement, current_node, current_type, node_types, opts, report, metadata)
        return statement

    with src.open('r', encoding='latin-1', newline='') as f:
        for line in f:
            if in_stmt:
                stmt_buf += line
                found_end, stmt_in_quote, stmt_escaped = update_statement_state(line, stmt_in_quote, stmt_escaped)
                if found_end:
                    out_parts.append(flush_stmt(stmt_buf))
                    stmt_buf = ''
                    in_stmt = False
                    stmt_in_quote = False
                    stmt_escaped = False
                continue

            stripped = line.lstrip()
            if stripped.startswith('setAttr') or stripped.startswith('addAttr'):
                stmt_buf = line
                stmt_in_quote = False
                stmt_escaped = False
                found_end, stmt_in_quote, stmt_escaped = update_statement_state(line, stmt_in_quote, stmt_escaped)
                if found_end:
                    out_parts.append(flush_stmt(stmt_buf))
                    stmt_buf = ''
                    stmt_in_quote = False
                    stmt_escaped = False
                else:
                    in_stmt = True
                continue

            cm = CREATE_RE.match(line)
            if cm:
                flush_poly_generator_defaults()
                current_node, current_type = update_context_from_create(line, node_types)
            elif SELECT_RE.match(line):
                flush_poly_generator_defaults()
                sel_node, sel_type = parse_select_context(line, node_types)
                if sel_node is not None:
                    current_node = sel_node
                    current_type = sel_type
            out_parts.append(line)

    if stmt_buf:
        out_parts.append(flush_stmt(stmt_buf))

    flush_poly_generator_defaults()

    report['total_scaled_numbers'] = sum(
        v for k, v in report.items()
        if k != 'total_scaled_numbers' and 'skipped' not in k.lower()
    )
    if not opts.dry_run:
        dst.write_text(''.join(out_parts), encoding='latin-1', newline='')
    return report


def make_report_text(src: Path, dst: Path, opts: Options, report: Counter) -> str:
    lines = [
        'Maya ASCII rig space scaling report',
        '===================================',
        f'Input: {src}',
        f'Output: {dst}',
        f'Scale factor: {opts.scale}',
        f'Preset: {opts.preset}',
        f'SDK mode requested: {opts.sdk_mode}',
        f'SDK mode effective: {opts.effective_sdk_mode}',
        f'SDK node regex: {opts.sdk_node_re.pattern}',
        f'Rest constants requested: {opts.rest_mode}',
        f'Rest constants effective: {opts.effective_rest_mode}',
        f'Rest vector mode: {opts.rest_vector_mode}',
        f'Scale translate limits: {opts.scale_translate_limits}',
        f'Scale animCurveTL translate animation: {opts.scale_linear_animation}',
        f'Scale skinCluster bindPreMatrix: {opts.scale_skin_bind_pre_matrices}',
        f'Fix ADV eyelid bindPreMatrix: {opts.fix_adv_eyelid_bind_pre_matrices}',
        f'Dry run: {opts.dry_run}',
        '',
        'Changed numeric values by category:',
    ]
    if report:
        for k, v in report.most_common():
            lines.append(f'  {k}: {v}')
    else:
        lines.append('  None')
    lines += [
        '',
        'Important skipped categories by design:',
        '  scale channels, rotations, jointOrient, preferredAngle, UVs, normals, colors, visibility,',
        '  skin weights, blend weights, unitless face-panel translate limits unless --scale-translate-limits is used.',
        '',
    ]
    return '\n'.join(lines)

