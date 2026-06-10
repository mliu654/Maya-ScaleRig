"""Shared constants and regexes for Maya ASCII scaling."""

from __future__ import annotations

import re

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
UNQUOTED_SETATTR_ATTR_RE = re.compile(
    r'^\s*setAttr\b(?:\s+-\S+(?:\s+(?:"[^"]*"|\S+))?)*\s+([^\s;]+)'
)

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

BASE_SCALAR_ATTRS = {
    '.tx', '.ty', '.tz',
    '.translatex', '.translatey', '.translatez',
    '.height', '.fat', '.fatyabs', '.fatfrontabs', '.fatwidthabs',
    '.falloffradius', '.radi', '.radius', '.coi', '.centerofinterest', '.ow',
}

ARRAY_COORD_ATTRS = {
    '.vt[]', '.pt[]', '.cv[]', '.pnts[]', '.pnt[]',
}

SPATIAL_ADDATTR_NAMES = {
    'fat', 'fatyabs', 'fatfrontabs', 'fatwidthabs', 'falloffradius', 'height', 'radius',
}

DEFAULT_REST_NODE_REGEX = (
    r'(distance|lenght|length|measure|messure|curveinfo.*normalize|normalize.*curveinfo|'
    r'stretchy|stretch)'
)

DEFAULT_SDK_LINEAR_NODE_REGEX = (
    r'(translate|position|offset|distance|lenght|length|height|width|radius|falloff)'
)

REST_LENGTH_ATTRS = {
    '.i1', '.i2', '.i1x', '.i2x', '.i1y', '.i2y', '.i1z', '.i2z',
    '.input1', '.input2', '.input1x', '.input2x', '.input1y', '.input2y', '.input1z', '.input2z',
    '.mx', '.max', '.maxr', '.mxr', '.mnr', '.minr',
}
REST_NODE_TYPES = {'multiplydivide', 'clamp', 'multdoublelinear', 'plusminusaverage'}

XFORM_LINEAR_INDICES = set(range(7, 10)) | set(range(13, 25))
REGULAR_MATRIX_TRANSLATE_INDICES = {12, 13, 14}

