"""Command-line interface for Maya ScaleRig."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional

from maya_scalerig.core.constants import (
    DEFAULT_REST_NODE_REGEX,
    DEFAULT_SDK_LINEAR_NODE_REGEX,
)
from maya_scalerig.core.options import Options
from maya_scalerig.core.processor import make_report_text, process_file


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
    p.add_argument('--sdk-node-regex', default=DEFAULT_SDK_LINEAR_NODE_REGEX,
                   help='Only scale animCurveUL nodes whose names match this regex. Use ".*" to scale all')
    p.add_argument('--rest-mode', choices=['auto', 'off', 'on'], default='auto',
                   help='Scale named rest-distance constants in utility nodes. auto=on for adv, off for generic')
    p.add_argument('--rest-vector-mode', choices=['first', 'all'], default='first',
                   help='For named rest-distance vector attrs, scale only the first component or all components')
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

