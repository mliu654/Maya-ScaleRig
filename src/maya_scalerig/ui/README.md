# UI Package

This folder contains the optional PyQt6 desktop interface.

Current responsibilities:

- Add one or more input `.ma` files by typing paths or using file pickers.
- Switch the interface between Chinese and English.
- Remember the last used language, scale factor, output folder, and browse folders.
- Edit the scale factor.
- Choose an output folder by typing a path or selecting a folder.
- Customize output names per file. The default is `originalName_scale.ma`.
- Run batch scaling with a per-file progress bar.
- Show logs and generated core reports in the UI.
- Optionally write `*_report.txt` files next to the output `.ma` files.
- Keep technical rig-scaling switches out of the UI and use automatic defaults.

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

Current UI module split:

- `app.py`: main window layout and UI event handling.
- `config.py`: JSON-backed UI settings.
- `worker.py`: background batch processing worker.
- `i18n.py`: Chinese and English UI text.

On Windows, UI settings are saved under `%APPDATA%\MayaScaleRig\ui_settings.json`.

The UI imports PyQt6 only from this package. `maya_scalerig.core` and the CLI
continue to work without PyQt6 installed.
