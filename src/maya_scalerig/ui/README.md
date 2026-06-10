# UI Package

This folder is reserved for the future PyQt6 interface.

Planned responsibilities:

- File picker for input and output `.ma` paths.
- Preset selection for AdvancedSkeleton and generic rigs.
- Advanced options for SDK, rest-length, and custom attribute rules.
- Dry-run report preview.
- One-click export of the scaled `.ma` file and report.

Keep UI code separate from `maya_scalerig.core` so the command-line scaler can
continue to run without PyQt6 installed.

