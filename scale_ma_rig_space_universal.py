#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scale_ma_rig_space_universal.py

Uniformly scale scene-space data inside a Maya ASCII (.ma) rig file without adding
an external scale group and without changing controller .scale channels.

This script is intentionally conservative: it scales values that represent scene
length/position, and skips values that are usually unitless or directional.

Recommended for the tested AdvancedSkeleton-style case:
    python scale_ma_rig_space_universal.py input.ma output_2p5.ma 2.5 --preset adv --sdk-mode linear-output --report output_2p5_report.txt

More conservative generic mode:
    python scale_ma_rig_space_universal.py input.ma output_2p5.ma 2.5 --preset generic --sdk-mode none --report report.txt

Important:
- Always keep a backup.
- Open the result in Maya and test FK, IK, stretch, face controls, constraints, and export.
- No text scaler can guarantee every custom rig. Use the options below to tune per-rig behavior.
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Optional

# -----------------------------
# Regex helpers
# -----------------------------

NUM_PATTERN = r'[-+]?(?:\d+\.\d*|\.\d+|\d+)(?:[eE][-+]?\d+)?'
NUM_RE = re.compile(NUM_PATTERN)
TOKEN_RE = re.compile(NUM_PATTERN + r'|\byes\b|\bno\b', re.I)
CREATE_RE = re.compile(r'^\s*createNode\s+(\S+)(.*?)\s*;')
NAME_RE = re.compile(r'-n\s+"([^"]+)"')
QUOTED_RE = re.compile(r'"((?:[^"\\]|\\.)*)"')
ADD_SN_RE = re.compile(r'-sn\s+"([^"]+)"')
ADD_LN_RE = re.compile(r'-ln\s+"([^"]+)"')
DV_RE = re.compile(r'(-dv\s+)(' + NUM_PATTERN + r')')
SELECT_RE = re.compile(r'^\s*select\b')

# -----------------------------
# Built-in attr rules
# -----------------------------

# Vector attributes that usually represent scene-space positions or offsets.
# NOTE: translate limits (.mntl/.mxtl) are intentionally excluded by default.
BASE_VECTOR_ATTRS = {
    '.t', '.translate',
    '.rp', '.rotatepivot',
    '.sp', '.scalepivot',
    '.rpt', '.rotatepivottranslate',
    '.spt', '.scalepivottranslate',
    '.tp', '.templateposition',
    '.pvt', '.pivot',
    '.lp', '.localposition',
    '.lt', '.localtranslate',
    '.cbn', '.boundingboxmin',
    '.cbx', '.boundingboxmax',
    '.rst', '.restposition',
    '.tg[].tot', '.target[].targetoffsettranslate',
}

TRANSLATE_LIMIT_ATTRS = {
    '.mntl', '.mintranslimit',
    '.mxtl', '.maxtranslimit',
}

# Scalar attributes that usually represent a length/radius/height/width.
BASE_SCALAR_ATTRS = {
    '.tx', '.ty', '.tz',
    '.translatex', '.translatey', '.translatez',
    '.height', '.fat', '.fatyabs', '.fatfrontabs', '.fatwidthabs',
    '.falloffradius', '.radi', '.radius', '.coi', '.centerofinterest', '.ow',
}

# Component arrays whose value payload is XYZ-style coordinate data.
ARRAY_COORD_ATTRS = {
    '.vt[]', '.pt[]', '.cv[]', '.pnts[]', '.pnt[]',
}

# Custom addAttr defaults that are normally spatial in AdvancedSkeleton-style rigs.
SPATIAL_ADDATTR_NAMES = {
    'fat', 'fatyabs', 'fatfrontabs', 'fatwidthabs', 'falloffradius', 'height', 'radius',
}

# Node names matching these words often store rest distances/limb lengths in utility nodes.
# These are optional and enabled by preset/mode.
DEFAULT_REST_NODE_REGEX = (
    r'(distance|lenght|length|measure|messure|curveinfo.*normalize|normalize.*curveinfo|'
    r'stretchy|stretch)'
)

# Attributes on utility nodes that can store distance constants.
REST_LENGTH_ATTRS = {
    '.i1', '.i2', '.i1x', '.i2x', '.i1y', '.i2y', '.i1z', '.i2z',
    '.input1', '.input2', '.input1x', '.input2x', '.input1y', '.input2y', '.input1z', '.input2z',
    '.mx', '.max', '.maxr', '.mxr', '.mnr', '.minr',
}
REST_NODE_TYPES = {'multiplydivide', 'clamp', 'multdoublelinear', 'plusminusaverage'}

# matrix "xform" numeric indices that are linear positions, based on Maya matrix xform syntax:
#   0-2 scale, 3-5 rotate, 6 rotateOrder, 7-9 translate, 10-12 shear,
#   13-15 scalePivot, 16-18 scalePivotTranslation,
#   19-21 rotatePivot, 22-24 rotatePivotTranslation,
#   25-28 rotateOrient quat, 29-32 jointOrient quat, 33-35 inverseParentScale, 36 bool.
XFORM_LINEAR_INDICES = set(range(7, 10)) | set(range(13, 25))

# Regular 4x4 Maya matrix payload translation components.
REGULAR_MATRIX_TRANSLATE_INDICES = {12, 13, 14}


# -----------------------------
# Formatting / parsing helpers
# -----------------------------

def fmt_scaled(s: str, scale: float) -> str:
    """Scale a numeric string and return a compact Maya-friendly representation."""
    try:
        v = float(s) * scale
    except Exception:
        return s
    if abs(v) < 1e-14:
        v = 0.0
    return format(v, '.12g')


def normalize_attr(attr: str) -> str:
    """Normalize attr paths for rule matching.

    Examples:
        .vt[0:4]       -> .vt[]
        .tg[0].tot     -> .tg[].tot
        .input2X       -> .input2x
    """
    attr = attr.strip().lower()
    attr = re.sub(r'\[[^\]]+\]', '[]', attr)
    return attr


def short_node_name(node: Optional[str]) -> Optional[str]:
    if not node:
        return node
    return node.split('|')[-1]


def statement_has_end(text: str) -> bool:
    """Return True if text contains a semicolon outside quotes."""
    in_quote = False
    escaped = False
    for ch in text:
        if escaped:
            escaped = False
            continue
        if ch == '\\':
            escaped = True
            continue
        if ch == '"':
            in_quote = not in_quote
            continue
        if ch == ';' and not in_quote:
            return True
    return False




def update_statement_state(line: str, in_quote: bool, escaped: bool) -> tuple[bool, bool, bool]:
    """Scan only one new line. Return (found_semicolon_outside_quote, in_quote, escaped)."""
    for ch in line:
        if escaped:
            escaped = False
            continue
        if ch == '\\':
            escaped = True
            continue
        if ch == '"':
            in_quote = not in_quote
            continue
        if ch == ';' and not in_quote:
            return True, in_quote, escaped
    return False, in_quote, escaped


def find_attr_token(stmt: str) -> Optional[re.Match[str]]:
    """Find the quoted setAttr attribute token, not quoted type names."""
    for m in QUOTED_RE.finditer(stmt):
        q = m.group(1)
        # Maya setAttr target is usually ".attr". Reference edits may use "node.attr".
        if q.startswith('.'):
            return m
        # Avoid obvious type names and string payloads; accept node.attr-like tokens.
        if '.' in q and not q.lower() in {'double3', 'float3', 'matrix', 'string', 'nurbscurve', 'nurbssurface'}:
            # Require the last dotted part to look attr-like.
            tail = q.rsplit('.', 1)[-1]
            if tail and re.match(r'[a-zA-Z_]', tail):
                return m
    return None


def resolve_node_and_attr(attr_string: str, current_node: Optional[str]) -> tuple[Optional[str], str]:
    """Resolve a setAttr token into (node_name, attr_path)."""
    if attr_string.startswith('.'):
        return current_node, attr_string
    if '.' in attr_string:
        node, attr = attr_string.rsplit('.', 1)
        return short_node_name(node), '.' + attr
    return current_node, attr_string


def split_at_attr(stmt: str) -> Optional[tuple[str, str, str]]:
    m = find_attr_token(stmt)
    if not m:
        return None
    attr = m.group(1)
    return stmt[:m.end()], attr, stmt[m.end():]


def split_value_tail(stmt: str) -> Optional[tuple[str, str]]:
    """Return (prefix, payload_after_attr_and_optional_type_flag).

    The prefix contains command flags and the attribute token. The payload contains
    only actual values. This prevents scaling numbers in attr ranges, -s counts, or
    type names like "double3".
    """
    sp = split_at_attr(stmt)
    if not sp:
        return None
    prefix, _attr, tail = sp
    type_m = re.search(r'-type\s+"[^"]+"', tail)
    if type_m:
        return prefix + tail[:type_m.end()], tail[type_m.end():]
    return prefix, tail


def replace_numbers_by_indices(text: str, indices_to_scale: set[int], scale: float) -> tuple[str, int]:
    out: list[str] = []
    last = 0
    num_index = 0
    changed = 0
    for m in NUM_RE.finditer(text):
        out.append(text[last:m.start()])
        token = m.group(0)
        if num_index in indices_to_scale:
            out.append(fmt_scaled(token, scale))
            changed += 1
        else:
            out.append(token)
        last = m.end()
        num_index += 1
    out.append(text[last:])
    return ''.join(out), changed


def replace_all_numbers(text: str, scale: float) -> tuple[str, int]:
    changed = 0

    def repl(m: re.Match[str]) -> str:
        nonlocal changed
        changed += 1
        return fmt_scaled(m.group(0), scale)

    return NUM_RE.sub(repl, text), changed


def replace_every_second_number(text: str, scale: float, scale_odd_indices: bool = True) -> tuple[str, int]:
    """Scale every second number in ktv-style pairs.

    For .ktv arrays, numbers are usually time/input, value, time/input, value...
    scale_odd_indices=True scales the output values only.
    """
    out: list[str] = []
    last = 0
    idx = 0
    changed = 0
    for m in NUM_RE.finditer(text):
        out.append(text[last:m.start()])
        token = m.group(0)
        should_scale = (idx % 2 == 1) if scale_odd_indices else (idx % 2 == 0)
        if should_scale:
            out.append(fmt_scaled(token, scale))
            changed += 1
        else:
            out.append(token)
        last = m.end()
        idx += 1
    out.append(text[last:])
    return ''.join(out), changed


def replace_first_number(text: str, scale: float) -> tuple[str, int]:
    changed = 0

    def repl(m: re.Match[str]) -> str:
        nonlocal changed
        if changed:
            return m.group(0)
        changed = 1
        return fmt_scaled(m.group(0), scale)

    return NUM_RE.sub(repl, text, count=1), changed


def scale_tail_all_values(stmt: str, scale: float) -> tuple[str, int]:
    sp = split_value_tail(stmt)
    if not sp:
        return stmt, 0
    prefix, value_tail = sp
    new_tail, n = replace_all_numbers(value_tail, scale)
    return prefix + new_tail, n


def scale_tail_first_value(stmt: str, scale: float) -> tuple[str, int]:
    sp = split_value_tail(stmt)
    if not sp:
        return stmt, 0
    prefix, value_tail = sp
    new_tail, n = replace_first_number(value_tail, scale)
    return prefix + new_tail, n


def scale_tail_every_second_value(stmt: str, scale: float) -> tuple[str, int]:
    sp = split_value_tail(stmt)
    if not sp:
        return stmt, 0
    prefix, value_tail = sp
    new_tail, n = replace_every_second_number(value_tail, scale, scale_odd_indices=True)
    return prefix + new_tail, n


# -----------------------------
# Data-block scaling
# -----------------------------

def scale_matrix_stmt(stmt: str, scale: float) -> tuple[str, int, str]:
    marker = '-type "matrix"'
    pos = stmt.find(marker)
    if pos < 0:
        return stmt, 0, ''
    before = stmt[:pos + len(marker)]
    tail = stmt[pos + len(marker):]
    if '"xform"' in tail:
        xform_pos = tail.find('"xform"')
        before2 = tail[:xform_pos + len('"xform"')]
        after = tail[xform_pos + len('"xform"'):]
        new_after, n = replace_numbers_by_indices(after, XFORM_LINEAR_INDICES, scale)
        return before + before2 + new_after, n, 'matrix_xform_translation_numbers'
    new_tail, n = replace_numbers_by_indices(tail, REGULAR_MATRIX_TRANSLATE_INDICES, scale)
    return before + new_tail, n, 'matrix_regular_translation_numbers'


def scale_nurbs_curve_cc(stmt: str, scale: float) -> tuple[str, int]:
    marker = '-type "nurbsCurve"'
    pos = stmt.find(marker)
    if pos < 0:
        return stmt, 0
    before = stmt[:pos + len(marker)]
    data = stmt[pos + len(marker):]
    tokens = list(TOKEN_RE.finditer(data))
    if len(tokens) < 10:
        return stmt, 0
    values = [t.group(0) for t in tokens]
    numeric_token_to_num_index: dict[int, int] = {}
    num_index = 0
    for i, val in enumerate(values):
        if NUM_RE.fullmatch(val):
            numeric_token_to_num_index[i] = num_index
            num_index += 1
    try:
        idx = 0
        _degree = int(float(values[idx])); idx += 1
        _spans = int(float(values[idx])); idx += 1
        _form = int(float(values[idx])); idx += 1
        rational = values[idx].lower() == 'yes'; idx += 1
        dimension = int(float(values[idx])); idx += 1
        knot_count = int(float(values[idx])); idx += 1
        idx += knot_count
        cv_count = int(float(values[idx])); idx += 1
        stride = 4 if rational else dimension
        coord_num_indices: set[int] = set()
        for c in range(cv_count):
            for j in range(stride):
                tok_idx = idx + c * stride + j
                if tok_idx >= len(values):
                    break
                # Scale X/Y/Z; do not scale rational weights.
                if (not rational) or j < 3:
                    if tok_idx in numeric_token_to_num_index:
                        coord_num_indices.add(numeric_token_to_num_index[tok_idx])
        if not coord_num_indices:
            return stmt, 0
        new_data, n = replace_numbers_by_indices(data, coord_num_indices, scale)
        return before + new_data, n
    except Exception:
        return stmt, 0


def scale_nurbs_surface_cc(stmt: str, scale: float) -> tuple[str, int]:
    marker = '-type "nurbsSurface"'
    pos = stmt.find(marker)
    if pos < 0:
        return stmt, 0
    before = stmt[:pos + len(marker)]
    data = stmt[pos + len(marker):]
    tokens = list(TOKEN_RE.finditer(data))
    if len(tokens) < 12:
        return stmt, 0
    values = [t.group(0) for t in tokens]
    numeric_token_to_num_index: dict[int, int] = {}
    num_index = 0
    for i, val in enumerate(values):
        if NUM_RE.fullmatch(val):
            numeric_token_to_num_index[i] = num_index
            num_index += 1
    try:
        idx = 0
        _degree_u = int(float(values[idx])); idx += 1
        _degree_v = int(float(values[idx])); idx += 1
        _form_u = int(float(values[idx])); idx += 1
        _form_v = int(float(values[idx])); idx += 1
        rational = values[idx].lower() == 'yes'; idx += 1
        knot_u_count = int(float(values[idx])); idx += 1
        idx += knot_u_count
        knot_v_count = int(float(values[idx])); idx += 1
        idx += knot_v_count
        cv_count = int(float(values[idx])); idx += 1
        stride = 4 if rational else 3
        coord_num_indices: set[int] = set()
        for c in range(cv_count):
            for j in range(stride):
                tok_idx = idx + c * stride + j
                if tok_idx >= len(values):
                    break
                if (not rational) or j < 3:
                    if tok_idx in numeric_token_to_num_index:
                        coord_num_indices.add(numeric_token_to_num_index[tok_idx])
        if not coord_num_indices:
            return stmt, 0
        new_data, n = replace_numbers_by_indices(data, coord_num_indices, scale)
        return before + new_data, n
    except Exception:
        return stmt, 0


def scale_addattr_default(stmt: str, scale: float, extra_names: set[str]) -> tuple[str, int]:
    sn = ADD_SN_RE.search(stmt)
    ln = ADD_LN_RE.search(stmt)
    names: set[str] = set()
    if sn:
        names.add(sn.group(1).lower())
    if ln:
        names.add(ln.group(1).lower())
    if not (names & (SPATIAL_ADDATTR_NAMES | extra_names)):
        return stmt, 0
    changed = 0

    def repl(m: re.Match[str]) -> str:
        nonlocal changed
        changed += 1
        return m.group(1) + fmt_scaled(m.group(2), scale)

    return DV_RE.sub(repl, stmt), changed


# -----------------------------
# Main scaling logic
# -----------------------------

class Options:
    def __init__(self, args: argparse.Namespace):
        self.scale: float = args.scale
        self.preset: str = args.preset
        self.sdk_mode: str = args.sdk_mode
        self.rest_mode: str = args.rest_mode
        self.scale_translate_limits: bool = args.scale_translate_limits
        self.scale_linear_animation: bool = args.scale_linear_animation
        self.dry_run: bool = args.dry_run
        self.extra_vector_attrs: set[str] = {normalize_attr(a) for a in args.extra_vector_attr}
        self.extra_scalar_attrs: set[str] = {normalize_attr(a) for a in args.extra_scalar_attr}
        self.extra_addattr_names: set[str] = {a.lower() for a in args.extra_addattr_name}
        rest_regex = args.rest_node_regex or DEFAULT_REST_NODE_REGEX
        if args.extra_rest_regex:
            rest_regex = f'(?:{rest_regex})|(?:{args.extra_rest_regex})'
        self.rest_node_re = re.compile(rest_regex, re.I)

        if self.sdk_mode == 'auto':
            self.effective_sdk_mode = 'linear-output' if self.preset == 'adv' else 'none'
        else:
            self.effective_sdk_mode = self.sdk_mode

        if self.rest_mode == 'auto':
            self.effective_rest_mode = 'on' if self.preset == 'adv' else 'off'
        else:
            self.effective_rest_mode = self.rest_mode

    @property
    def scale_sdk_linear_output(self) -> bool:
        return self.effective_sdk_mode == 'linear-output'

    @property
    def scale_rest_constants(self) -> bool:
        return self.effective_rest_mode == 'on'


def process_setattr(
    stmt: str,
    current_node: Optional[str],
    current_type: Optional[str],
    node_types: dict[str, str],
    opts: Options,
    report: Counter,
) -> str:
    token_m = find_attr_token(stmt)
    if not token_m:
        return stmt

    raw_attr = token_m.group(1)
    node_name, attr = resolve_node_and_attr(raw_attr, current_node)
    node_name_short = short_node_name(node_name)
    node_type = node_types.get(node_name or '', None) or node_types.get(node_name_short or '', None) or current_type
    node_type_l = (node_type or '').lower()
    node_name_s = node_name_short or current_node or ''
    base = normalize_attr(attr)

    # 1) NURBS control-curve/surface blobs. Scale CV coordinates only.
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

    # 2) Matrices. Scale translation/pivot parts only, not basis vectors or quaternions.
    if '-type "matrix"' in stmt:
        new, n, kind = scale_matrix_stmt(stmt, opts.scale)
        if n:
            report[kind] += n
        return new

    # 3) Mesh/component positions.
    if base in ARRAY_COORD_ATTRS:
        new, n = scale_tail_all_values(stmt, opts.scale)
        if n:
            report[f'{base}_coordinate_numbers'] += n
        return new

    # 4) Transform-like vectors. Translate limits are skipped unless explicitly requested.
    vector_attrs = set(BASE_VECTOR_ATTRS) | opts.extra_vector_attrs
    if opts.scale_translate_limits:
        vector_attrs |= TRANSLATE_LIMIT_ATTRS
    if base in vector_attrs:
        new, n = scale_tail_all_values(stmt, opts.scale)
        if n:
            report[f'{base}_vector_numbers'] += n
        return new

    # 5) Spatial scalar attrs.
    scalar_attrs = set(BASE_SCALAR_ATTRS) | opts.extra_scalar_attrs
    if base in scalar_attrs:
        new, n = scale_tail_all_values(stmt, opts.scale)
        if n:
            report[f'{base}_scalar_numbers'] += n
        return new

    # 6) Utility-node rest-distance constants. Enabled mainly for ADV-like generated rigs.
    # Only scale the first numeric component to avoid changing ratio filler values like 1,1.
    if opts.scale_rest_constants and node_type_l in REST_NODE_TYPES and node_name_s and opts.rest_node_re.search(node_name_s):
        if base in REST_LENGTH_ATTRS:
            new, n = scale_tail_first_value(stmt, opts.scale)
            if n:
                report['rest_length_utility_first_values'] += n
            return new

    # 7) plusMinusAverage 3D offsets often store spatial offsets.
    # Keep this enabled for both presets because the attr type itself is spatial.
    if node_type_l == 'plusminusaverage' and base.startswith('.i3'):
        new, n = scale_tail_all_values(stmt, opts.scale)
        if n:
            report['plusMinusAverage_input3D_numbers'] += n
        return new

    # 8) ADV IK distance normal/antiPop curves: unitless animCurveUU but both axes are distance.
    if opts.preset == 'adv' and node_type_l == 'animcurveuu' and node_name_s:
        if re.search(r'^IKdistance.*Shape_(normal|antiPop)$', node_name_s) and base.startswith('.ktv'):
            new, n = scale_tail_all_values(stmt, opts.scale)
            if n:
                report['adv_IKdistance_animCurveUU_key_numbers'] += n
            return new

    # 9) Linear-output animation curves.
    # animCurveUL: unitless input -> linear output, common for SDK translating shapes/controls.
    # animCurveTL: time input -> linear output, common for translate animation keys.
    if node_type_l == 'animcurveul' and base.startswith('.ktv') and opts.scale_sdk_linear_output:
        new, n = scale_tail_every_second_value(stmt, opts.scale)
        if n:
            report['animCurveUL_linear_output_key_values'] += n
        return new

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
        # Fall back to the last bare token that is not a flag or flag value.
        temp = line.strip().rstrip(';')
        parts = temp.split()
        candidates = [p for p in parts[1:] if not p.startswith('-')]
        if candidates:
            target = candidates[-1]
    target = short_node_name(target)
    return target, node_types.get(target or '')


def process_file(src: Path, dst: Path, opts: Options) -> Counter:
    report: Counter = Counter()
    out_parts: list[str] = []
    node_types: dict[str, str] = {}
    current_node: Optional[str] = None
    current_type: Optional[str] = None
    stmt_buf = ''
    in_stmt = False
    stmt_in_quote = False
    stmt_escaped = False

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
            return process_setattr(statement, current_node, current_type, node_types, opts, report)
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
                current_node, current_type = update_context_from_create(line, node_types)
            elif SELECT_RE.match(line):
                sel_node, sel_type = parse_select_context(line, node_types)
                if sel_node is not None:
                    current_node = sel_node
                    current_type = sel_type
            out_parts.append(line)

    if stmt_buf:
        out_parts.append(flush_stmt(stmt_buf))

    report['total_scaled_numbers'] = sum(v for k, v in report.items() if k != 'total_scaled_numbers')
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
        f'Rest constants requested: {opts.rest_mode}',
        f'Rest constants effective: {opts.effective_rest_mode}',
        f'Scale translate limits: {opts.scale_translate_limits}',
        f'Scale animCurveTL translate animation: {opts.scale_linear_animation}',
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


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description='Uniformly scale scene-space data inside a Maya ASCII rig file.',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument('input', type=Path, help='Input .ma file')
    p.add_argument('output', type=Path, help='Output .ma file')
    p.add_argument('scale', type=float, nargs='?', default=2.5, help='Uniform scale factor')
    p.add_argument('--preset', choices=['adv', 'generic'], default='adv', help='Heuristic profile')
    p.add_argument('--sdk-mode', choices=['auto', 'none', 'linear-output'], default='auto',
                   help='Scale animCurveUL output values. auto=linear-output for adv, none for generic')
    p.add_argument('--rest-mode', choices=['auto', 'off', 'on'], default='auto',
                   help='Scale named rest-distance constants in utility nodes. auto=on for adv, off for generic')
    p.add_argument('--scale-translate-limits', action='store_true',
                   help='Scale .mntl/.mxtl translate limits. Usually OFF for face/UI slider panels')
    p.add_argument('--scale-linear-animation', action='store_true',
                   help='Scale animCurveTL translate animation output values')
    p.add_argument('--extra-vector-attr', action='append', default=[],
                   help='Additional vector attr to scale, e.g. .myOffset. Can be repeated')
    p.add_argument('--extra-scalar-attr', action='append', default=[],
                   help='Additional scalar attr to scale, e.g. .myRadius. Can be repeated')
    p.add_argument('--extra-addattr-name', action='append', default=[],
                   help='Additional addAttr short/long name whose -dv default is spatial. Can be repeated')
    p.add_argument('--rest-node-regex', default=DEFAULT_REST_NODE_REGEX,
                   help='Regex for utility nodes containing rest-distance constants')
    p.add_argument('--extra-rest-regex', default='',
                   help='Extra regex OR-ed with --rest-node-regex')
    p.add_argument('--report', type=Path, default=None, help='Optional report .txt path')
    p.add_argument('--dry-run', action='store_true', help='Analyze and report without writing output file')
    return p


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    src: Path = args.input
    dst: Path = args.output
    if not src.exists():
        print(f'ERROR: input not found: {src}', file=sys.stderr)
        return 1
    if src.resolve() == dst.resolve() and not args.dry_run:
        print('ERROR: input and output must be different files. Keep a backup.', file=sys.stderr)
        return 1
    opts = Options(args)
    report = process_file(src, dst, opts)
    text = make_report_text(src, dst, opts, report)
    if args.report:
        args.report.write_text(text, encoding='utf-8')
    print(text)
    if not opts.dry_run:
        print(f'Saved: {dst}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
