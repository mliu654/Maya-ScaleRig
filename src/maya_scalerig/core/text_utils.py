"""Text parsing and numeric replacement helpers for Maya ASCII statements."""

from __future__ import annotations

import re
from typing import Optional

from maya_scalerig.core.constants import (
    NUM_RE,
    QUOTED_RE,
    UNQUOTED_SETATTR_ATTR_RE,
)


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


def update_statement_state(line: str, in_quote: bool, escaped: bool) -> tuple[bool, bool, bool]:
    """Scan one line and return (found_semicolon_outside_quote, in_quote, escaped)."""
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
        if q.startswith('.'):
            return m
        if '.' in q and q.lower() not in {'double3', 'float3', 'matrix', 'string', 'nurbscurve', 'nurbssurface'}:
            tail = q.rsplit('.', 1)[-1]
            if tail and re.match(r'[a-zA-Z_]', tail):
                return m
    return None


def find_attr_ref(stmt: str) -> Optional[tuple[int, int, str]]:
    """Find a setAttr target attr, supporting quoted and simple unquoted forms."""
    m = find_attr_token(stmt)
    if m:
        return m.start(), m.end(), m.group(1)

    m2 = UNQUOTED_SETATTR_ATTR_RE.match(stmt)
    if not m2:
        return None
    attr = m2.group(1)
    if attr.startswith('.') or ('.' in attr and not attr.startswith('-')):
        return m2.start(1), m2.end(1), attr
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
    ref = find_attr_ref(stmt)
    if not ref:
        return None
    _start, end, attr = ref
    return stmt[:end], attr, stmt[end:]


def split_value_tail(stmt: str) -> Optional[tuple[str, str]]:
    """Return (prefix, payload_after_attr_and_optional_type_flag)."""
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
    """Scale every second number in ktv-style pairs."""
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

