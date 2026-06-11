"""Statement-level scalers for Maya ASCII data blocks."""

from __future__ import annotations

import re

from maya_scalerig.core.constants import (
    ADD_LN_RE,
    ADD_SN_RE,
    DV_RE,
    NUM_RE,
    REGULAR_MATRIX_TRANSLATE_INDICES,
    SPATIAL_ADDATTR_NAMES,
    TOKEN_RE,
    XFORM_LINEAR_INDICES,
)
from maya_scalerig.core.text_utils import (
    fmt_scaled,
    replace_all_numbers,
    replace_first_number,
    replace_numbers_by_indices,
    split_value_tail,
)


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


def scale_point_array_stmt(stmt: str, scale: float) -> tuple[str, int]:
    """Scale Maya pointArray XYZ payloads while preserving count and weights."""
    marker = '-type "pointArray"'
    pos = stmt.find(marker)
    if pos < 0:
        return stmt, 0
    before = stmt[:pos + len(marker)]
    data = stmt[pos + len(marker):]
    tokens = list(NUM_RE.finditer(data))
    if len(tokens) < 5:
        return stmt, 0
    try:
        point_count = int(float(tokens[0].group(0)))
    except Exception:
        return stmt, 0

    coord_indices: set[int] = set()
    idx = 1
    for _ in range(point_count):
        for j in range(4):
            if idx >= len(tokens):
                break
            if j < 3:
                coord_indices.add(idx)
            idx += 1
    if not coord_indices:
        return stmt, 0
    new_data, n = replace_numbers_by_indices(data, coord_indices, scale)
    return before + new_data, n


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


def scale_tail_all_values(stmt: str, scale: float) -> tuple[str, int]:
    sp = split_value_tail(stmt)
    if not sp:
        return stmt, 0
    prefix, value_tail = sp
    new_tail, n = replace_all_numbers(value_tail, scale)
    return prefix + new_tail, n


def scale_tail_number_indices(stmt: str, indices: set[int], scale: float) -> tuple[str, int]:
    sp = split_value_tail(stmt)
    if not sp:
        return stmt, 0
    prefix, value_tail = sp
    new_tail, n = replace_numbers_by_indices(value_tail, indices, scale)
    return prefix + new_tail, n


def scale_tail_first_value(stmt: str, scale: float) -> tuple[str, int]:
    sp = split_value_tail(stmt)
    if not sp:
        return stmt, 0
    prefix, value_tail = sp
    new_tail, n = replace_first_number(value_tail, scale)
    return prefix + new_tail, n

