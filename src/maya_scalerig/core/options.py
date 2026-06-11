"""Runtime options for Maya ScaleRig."""

from __future__ import annotations

import argparse
import re

from maya_scalerig.core.constants import (
    DEFAULT_REST_NODE_REGEX,
    DEFAULT_SDK_LINEAR_NODE_REGEX,
)
from maya_scalerig.core.text_utils import normalize_attr


class Options:
    """Normalized processing options shared by CLI and future UI callers."""

    def __init__(self, args: argparse.Namespace):
        self.scale: float = args.scale
        self.preset: str = args.preset
        self.sdk_mode: str = args.sdk_mode
        self.rest_mode: str = args.rest_mode
        self.rest_vector_mode: str = args.rest_vector_mode
        self.scale_translate_limits: bool = args.scale_translate_limits
        self.scale_linear_animation: bool = args.scale_linear_animation
        self.scale_skin_bind_pre_matrices: bool = getattr(args, 'scale_skin_bind_pre_matrices', True)
        self.fix_adv_eyelid_bind_pre_matrices: bool = getattr(args, 'fix_adv_eyelid_bind_pre_matrices', True)
        self.dry_run: bool = args.dry_run
        self.extra_vector_attrs: set[str] = {normalize_attr(a) for a in args.extra_vector_attr}
        self.extra_scalar_attrs: set[str] = {normalize_attr(a) for a in args.extra_scalar_attr}
        self.extra_addattr_names: set[str] = {a.lower() for a in args.extra_addattr_name}

        rest_regex = args.rest_node_regex or DEFAULT_REST_NODE_REGEX
        if args.extra_rest_regex:
            rest_regex = f'(?:{rest_regex})|(?:{args.extra_rest_regex})'
        self.rest_node_re = re.compile(rest_regex, re.I)
        self.sdk_node_re = re.compile(args.sdk_node_regex or DEFAULT_SDK_LINEAR_NODE_REGEX, re.I)

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

