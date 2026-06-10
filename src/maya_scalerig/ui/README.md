# UI Package

This folder contains the optional PyQt6 desktop interface.

Current responsibilities:

- Add one or more input `.ma` files by typing paths or using file pickers.
- Edit the scale factor.
- Choose an output folder by typing a path or selecting a folder.
- Customize output names per file. The default is `originalName_scale.ma`.
- Run batch scaling with a per-file progress bar.
- Show logs and generated core reports in the UI.
- Optionally write `*_report.txt` files next to the output `.ma` files.

Run without installing the package:

```powershell
$env:PYTHONPATH = ".\src"
python -m maya_scalerig.ui
```

Run after editable install:

```powershell
python -m pip install -e ".[ui]"
maya-scalerig-ui
```

The UI imports PyQt6 only from this package. `maya_scalerig.core` and the CLI
continue to work without PyQt6 installed.
