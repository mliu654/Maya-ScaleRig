# Maya ScaleRig

Scale scene-space data inside a Maya ASCII rig file without adding an external
scale group and without changing controller scale channels.

This tool is intended for rigs that need to become physically larger or smaller
at the file-data level. It edits only values that are likely to represent
positions, lengths, pivots, bind matrices, curve CVs, mesh vertices, and selected
rig rest-length constants.

## Project Layout

```text
Maya-ScaleRig/
+-- src/
|   +-- maya_scalerig/
|       +-- core/
|       |   +-- cli.py
|       |   +-- constants.py
|       |   +-- options.py
|       |   +-- processor.py
|       |   +-- scalers.py
|       |   +-- text_utils.py
|       +-- ui/
|           +-- app.py
|           +-- config.py
|           +-- i18n.py
|           +-- style.py
|           +-- worker.py
|           +-- assets/
|           +-- README.md
+-- tests/
|   +-- fixtures/
|       +-- README.md
|       +-- input.ma
|       +-- input_2.ma
|       +-- input_2_correct.ma
|       +-- input_2_adv_eye_fix.ma
+-- docs/
|   +-- MA_rig_space_scale_logic_summary.md
+-- README.md
+-- pyproject.toml
+-- .gitignore
```

The project is a standalone Python tool. It does not need to be installed into
Maya's scripts, plug-ins, or modules folders. The optional PyQt6 interface lives
under `src/maya_scalerig/ui/` and calls the same core scaler used by the command
line.

## Why This Exists

Scaling a rig by parenting it under a `scale = 2.5` group is quick, but it can
break rebuild workflows, exports, constraints, or tools that expect controller
scale channels to stay at `1, 1, 1`.

This script instead rewrites the `.ma` file so the rig's scene-space data is
scaled directly:

- Mesh vertex positions are scaled.
- Joint and transform translations are scaled.
- Bind matrices and dagPose matrix translations are scaled.
- NURBS curve and surface CV coordinates are scaled.
- AdvancedSkeleton-style IK rest lengths and distance curves can be scaled.
- Controller `scale`, rotations, joint orient, weights, UVs, normals, colors,
  visibility, and face-panel UI limits are intentionally left alone.

## Quick Start

Run a dry run first:

```powershell
$env:PYTHONPATH = ".\src"
python -m maya_scalerig .\tests\fixtures\input.ma .\output_2p5.ma 2.5 --dry-run
```

Generate a scaled file and report:

```powershell
$env:PYTHONPATH = ".\src"
python -m maya_scalerig .\tests\fixtures\input.ma .\output_2p5.ma 2.5 --preset adv --report .\output_2p5_report.txt
```

Use the more conservative generic profile:

```powershell
$env:PYTHONPATH = ".\src"
python -m maya_scalerig .\tests\fixtures\input.ma .\output_generic_2p5.ma 2.5 --preset generic --sdk-mode none --report .\generic_report.txt
```

Never overwrite the source file directly. The script refuses to write to the
same path as the input, but you should still keep a separate backup.

You can also install the package in editable mode:

```powershell
python -m pip install -e .
maya-scalerig .\tests\fixtures\input.ma .\output_2p5.ma 2.5 --dry-run
```

For module execution without installation:

```powershell
$env:PYTHONPATH = ".\src"
python -m maya_scalerig .\tests\fixtures\input.ma .\output_2p5.ma 2.5 --dry-run
```

## UI Quick Start

Install the optional UI dependency:

```powershell
python -m pip install -e ".[ui]"
maya-scalerig-ui
```

Run the UI without installing the package:

```powershell
$env:PYTHONPATH = ".\src"
python -m maya_scalerig.ui
```

The UI supports Chinese/English switching, typed input paths, file pickers,
editable output folders and output names, scale factor input, batch processing,
progress display, dry run, report writing, and a log panel. It runs the core
scaler with the automatic rig profile: skinCluster bind pre-matrices and the ADV
eyelid compensation are enabled by default, while low-level debug switches remain
available from the CLI.

## Main Options

`--preset adv`

Enables AdvancedSkeleton-oriented heuristics by default, including named
rest-length constants and SDK linear-output curves.

`--preset generic`

Uses safer defaults for unknown rigs. Rest constants and SDK linear-output curves
are not scaled unless you explicitly enable them.

`--sdk-mode auto|none|linear-output`

Controls `animCurveUL` handling. In `adv` mode, `auto` becomes
`linear-output`; in `generic` mode, `auto` becomes `none`.

`--sdk-node-regex REGEX`

Limits which `animCurveUL` nodes are treated as linear spatial outputs. The
default matches names containing words such as `translate`, `position`,
`offset`, `distance`, `length`, `height`, `width`, or `radius`. Use `".*"` if
you deliberately want the older broad behavior.

`--rest-mode auto|off|on`

Controls named utility-node rest-distance constants. In `adv` mode, `auto`
becomes `on`; in `generic` mode, `auto` becomes `off`.

`--rest-vector-mode first|all`

Controls named rest-distance vector attrs. `first` scales only the first numeric
component, which matches many AdvancedSkeleton IK length nodes. `all` is useful
for rigs that store spatial lengths in multiple vector components.

`--scale-translate-limits`

Scales `.mntl` and `.mxtl`. This is off by default because many face panels use
translate limits as UI slider ranges rather than world-space distances.

`--scale-linear-animation`

Scales `animCurveTL` output values. Use this only if the file contains translate
animation keys that should follow the new rig size.

`--scale-skin-bind-pre-matrices`

Scales `skinCluster.pm[]` / `bindPreMatrix[]` cached inverse bind matrices. This
is on by default because bind matrices must usually stay consistent with scaled
vertices, joints, and dagPose data. Use `--skip-skin-bind-pre-matrices` only as a
debug option.

`--fix-adv-eyelid-bind-pre-matrices`

ADV preset only. Keeps AdvancedSkeleton eyelid `AimEnd` local X lengths from
being treated as world-space scale offsets, then compensates the related eyelid
`skinCluster.pm[]` values. This fixes the eye/eyelid deformation case where
skin is enabled but the unbound mesh looks correct. It is enabled by default;
use `--skip-adv-eyelid-bind-pre-matrices` only for comparison tests.

`--extra-vector-attr ATTR`

Adds a vector attribute to the scale whitelist. Can be repeated.

Example:

```powershell
maya-scalerig in.ma out.ma 2.5 --extra-vector-attr .los
```

`--extra-scalar-attr ATTR`

Adds a scalar attribute to the scale whitelist. Can be repeated.

`--extra-addattr-name NAME`

Scales the `-dv` default value for matching `addAttr` short or long names.

`--extra-rest-regex REGEX`

Adds node-name patterns for custom utility nodes that store rest distances.

## What Is Scaled

The script scales:

- Transform position-like attrs such as `.t`, `.tx`, `.ty`, `.tz`, pivots, pivot
  translations, bounding box attrs, and selected custom spatial attrs.
- Mesh and component coordinate arrays such as `.vt[]`, `.pt[]`, `.pnts[]`.
- NURBS curve and NURBS surface `.cc` CV coordinates.
- `pointArray` XYZ payloads, such as blendShape/tweak target deltas, while
  preserving point count and rational weights.
- Matrix translation components, including regular 4x4 matrices and Maya
  `"xform"` matrix syntax.
- AdvancedSkeleton-style IK distance animCurveUU keys where both axes represent
  distance.
- Filtered `animCurveUL` SDK outputs that look like spatial translate/position
  curves.

## What Is Not Scaled

The script intentionally skips:

- Transform scale channels.
- Rotation, jointOrient, preferredAngle, and angle animation curves.
- Skin weights, blendShape weights, blend weights, and visibility.
- UVs, normals, colors, enum values, bool values, and ratio-style controls.
- Translate limits unless `--scale-translate-limits` is explicitly enabled.
- MEL/Python strings and scriptNode command payloads.

## Recommended Maya Validation

After generating the output, open it in Maya and test before replacing any
production file.

Check top-level scale channels:

```python
import maya.cmds as cmds

for node in ["Group", "FitSkeleton", "MotionSystem", "MainSystem", "Main", "DeformationSystem", "Geometry"]:
    if cmds.objExists(node):
        print(node, cmds.getAttr(node + ".scale")[0])
```

They should remain close to:

```text
1, 1, 1
```

Check the new model size:

```python
import maya.cmds as cmds

if cmds.objExists("Geometry"):
    bbox = cmds.exactWorldBoundingBox("Geometry")
    print("height:", bbox[4] - bbox[1])
```

Then test:

- FK arms, legs, spine, fingers, hair, and extra controls.
- IK arms and legs.
- IK/FK switching.
- Stretch and anti-pop.
- Space switching.
- Face controls and face-panel slider ranges.
- Rebuild workflows if the rig system supports rebuilding.
- FBX or engine export if the file is meant for runtime.

## Known Limits

No text-based `.ma` scaler can infer every numeric value's meaning in every rig.
The main unresolved cases are:

- Custom plugin nodes with spatial values hidden in custom attrs.
- MEL or Python strings that store meaningful non-zero positions.
- External references or cache files.
- Rig-specific utility networks with unusual naming.
- Unitless custom attrs that are actually scene-space distances.

Use `--dry-run`, inspect the report, open the result in Maya, and add
rig-specific options only when the validation points to a real missing rule.

## Development Notes

The script is dependency-free Python and reads/writes Maya ASCII as text. It uses
`latin-1` for `.ma` IO so files with non-UTF-8 code pages can round-trip without
decode failures.

Before publishing a change, run:

```powershell
python -c "from pathlib import Path; [compile(p.read_text(encoding='utf-8'), str(p), 'exec') for p in Path('src').rglob('*.py')]; print('syntax ok')"
$env:PYTHONPATH = ".\src"
python -m maya_scalerig .\tests\fixtures\input.ma .\output_2p5.ma 2.5 --dry-run
```

The inline compile command avoids creating `__pycache__` files.
