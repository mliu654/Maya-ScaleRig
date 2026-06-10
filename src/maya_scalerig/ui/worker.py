"""Background processing worker for the PyQt6 UI."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

from PyQt6.QtCore import QObject, pyqtSignal

from maya_scalerig.core.options import Options
from maya_scalerig.core.processor import make_report_text, process_file
from maya_scalerig.ui.i18n import translate


def default_output_name(input_path: Path, scale: float) -> str:
    scale_text = f'{scale:g}'
    return f'{input_path.stem}_{scale_text}{input_path.suffix or ".ma"}'


def report_path_for(output_path: Path) -> Path:
    return output_path.with_name(f'{output_path.stem}_report.txt')


class ScaleWorker(QObject):
    progress_changed = pyqtSignal(int, int)
    row_status_changed = pyqtSignal(int, str)
    log_message = pyqtSignal(str)
    finished = pyqtSignal(bool)

    def __init__(self, jobs: list[dict[str, Any]], options_data: dict[str, Any], language: str):
        super().__init__()
        self.jobs = jobs
        self.options_data = options_data
        self.language = language
        self.cancel_requested = False

    def tr(self, key: str, **kwargs: object) -> str:
        return translate(self.language, key, **kwargs)

    def cancel(self) -> None:
        self.cancel_requested = True

    def run(self) -> None:
        total = len(self.jobs)
        ok = True
        self.progress_changed.emit(0, total)

        for index, job in enumerate(self.jobs, start=1):
            if self.cancel_requested:
                self.log_message.emit(self.tr('log_cancelled_before_remaining'))
                ok = False
                break

            row = job['row']
            src: Path = job['input']
            dst: Path = job['output']
            self.row_status_changed.emit(row, self.tr('status_running'))
            self.log_message.emit(self.tr('log_processing', index=index, total=total, path=src))

            try:
                if not src.exists():
                    raise FileNotFoundError(self.tr('log_input_not_found', path=src))
                if src.resolve() == dst.resolve() and not self.options_data['dry_run']:
                    raise ValueError(self.tr('error_input_output_same'))
                if not self.options_data['dry_run'] or self.options_data['write_report']:
                    dst.parent.mkdir(parents=True, exist_ok=True)

                opts = Options(SimpleNamespace(**self.options_data))
                report = process_file(src, dst, opts)
                report_text = make_report_text(src, dst, opts, report)

                if self.options_data['write_report']:
                    report_path_for(dst).write_text(report_text, encoding='utf-8')

                total_scaled = report.get('total_scaled_numbers', 0)
                self.row_status_changed.emit(row, self.tr('status_done', total=total_scaled))
                self.log_message.emit(report_text)
                if not opts.dry_run:
                    self.log_message.emit(self.tr('log_saved', path=dst))
                if self.options_data['write_report']:
                    self.log_message.emit(self.tr('log_report', path=report_path_for(dst)))
            except Exception as exc:  # pragma: no cover - UI runtime path
                ok = False
                self.row_status_changed.emit(row, self.tr('status_error'))
                self.log_message.emit(self.tr('log_error', path=src, error=exc))

            self.progress_changed.emit(index, total)

        self.finished.emit(ok)
