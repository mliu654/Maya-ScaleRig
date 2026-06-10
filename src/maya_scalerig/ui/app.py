"""PyQt6 desktop UI for Maya ScaleRig."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Optional

try:
    from PyQt6.QtCore import QObject, Qt, QThread, pyqtSignal
    from PyQt6.QtWidgets import (
        QApplication,
        QCheckBox,
        QComboBox,
        QFileDialog,
        QGridLayout,
        QGroupBox,
        QHBoxLayout,
        QHeaderView,
        QLabel,
        QLineEdit,
        QMainWindow,
        QMessageBox,
        QPushButton,
        QProgressBar,
        QTableWidget,
        QTableWidgetItem,
        QTextEdit,
        QVBoxLayout,
        QWidget,
        QDoubleSpinBox,
    )
except ImportError as exc:  # pragma: no cover - depends on optional UI extra
    raise SystemExit(
        'PyQt6 is required for the UI. Install it with: python -m pip install -e ".[ui]"'
    ) from exc

from maya_scalerig.core.constants import DEFAULT_REST_NODE_REGEX, DEFAULT_SDK_LINEAR_NODE_REGEX
from maya_scalerig.core.options import Options
from maya_scalerig.core.processor import make_report_text, process_file


INPUT_COL = 0
OUTPUT_COL = 1
STATUS_COL = 2


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

    def __init__(self, jobs: list[dict[str, Any]], options_data: dict[str, Any]):
        super().__init__()
        self.jobs = jobs
        self.options_data = options_data
        self.cancel_requested = False

    def cancel(self) -> None:
        self.cancel_requested = True

    def run(self) -> None:
        total = len(self.jobs)
        ok = True
        self.progress_changed.emit(0, total)

        for index, job in enumerate(self.jobs, start=1):
            if self.cancel_requested:
                self.log_message.emit('Cancelled before remaining files were processed.')
                ok = False
                break

            row = job['row']
            src: Path = job['input']
            dst: Path = job['output']
            self.row_status_changed.emit(row, 'Running')
            self.log_message.emit(f'[{index}/{total}] Processing: {src}')

            try:
                if not src.exists():
                    raise FileNotFoundError(f'Input not found: {src}')
                if src.resolve() == dst.resolve() and not self.options_data['dry_run']:
                    raise ValueError('Input and output must be different files.')
                if not self.options_data['dry_run'] or self.options_data['write_report']:
                    dst.parent.mkdir(parents=True, exist_ok=True)

                opts = Options(SimpleNamespace(**self.options_data))
                report = process_file(src, dst, opts)
                report_text = make_report_text(src, dst, opts, report)

                if self.options_data['write_report']:
                    report_path_for(dst).write_text(report_text, encoding='utf-8')

                total_scaled = report.get('total_scaled_numbers', 0)
                self.row_status_changed.emit(row, f'Done ({total_scaled})')
                self.log_message.emit(report_text)
                if not opts.dry_run:
                    self.log_message.emit(f'Saved: {dst}')
                if self.options_data['write_report']:
                    self.log_message.emit(f'Report: {report_path_for(dst)}')
            except Exception as exc:  # pragma: no cover - UI runtime path
                ok = False
                self.row_status_changed.emit(row, 'Error')
                self.log_message.emit(f'ERROR: {src}\n{exc}')

            self.progress_changed.emit(index, total)

        self.finished.emit(ok)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle('Maya ScaleRig')
        self.resize(980, 720)

        self.worker: Optional[ScaleWorker] = None
        self.thread: Optional[QThread] = None
        self.updating_table = False

        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)

        layout.addWidget(self._build_file_group())
        layout.addWidget(self._build_options_group())
        layout.addWidget(self._build_table())
        layout.addWidget(self._build_run_group())

        self._connect_signals()

    def _build_file_group(self) -> QGroupBox:
        group = QGroupBox('Files')
        layout = QGridLayout(group)

        self.input_edit = QLineEdit()
        self.input_edit.setPlaceholderText('Input .ma path, or multiple paths separated by ;')
        self.browse_input_btn = QPushButton('Browse')
        self.add_input_btn = QPushButton('Add')
        self.add_multiple_btn = QPushButton('Add Files')

        self.output_dir_edit = QLineEdit()
        self.output_dir_edit.setPlaceholderText('Output folder. Empty = same folder as input')
        self.browse_output_btn = QPushButton('Browse')

        self.selected_output_name_edit = QLineEdit()
        self.selected_output_name_edit.setPlaceholderText('Output name for selected row')

        layout.addWidget(QLabel('Input'), 0, 0)
        layout.addWidget(self.input_edit, 0, 1)
        layout.addWidget(self.browse_input_btn, 0, 2)
        layout.addWidget(self.add_input_btn, 0, 3)
        layout.addWidget(self.add_multiple_btn, 0, 4)

        layout.addWidget(QLabel('Output folder'), 1, 0)
        layout.addWidget(self.output_dir_edit, 1, 1, 1, 3)
        layout.addWidget(self.browse_output_btn, 1, 4)

        layout.addWidget(QLabel('Selected output name'), 2, 0)
        layout.addWidget(self.selected_output_name_edit, 2, 1, 1, 4)

        return group

    def _build_options_group(self) -> QGroupBox:
        group = QGroupBox('Options')
        layout = QGridLayout(group)

        self.scale_spin = QDoubleSpinBox()
        self.scale_spin.setRange(0.0001, 1000000.0)
        self.scale_spin.setDecimals(4)
        self.scale_spin.setValue(2.5)
        self.scale_spin.setSingleStep(0.1)

        self.preset_combo = QComboBox()
        self.preset_combo.addItems(['adv', 'generic'])

        self.sdk_combo = QComboBox()
        self.sdk_combo.addItems(['auto', 'none', 'linear-output'])

        self.rest_combo = QComboBox()
        self.rest_combo.addItems(['auto', 'off', 'on'])

        self.rest_vector_combo = QComboBox()
        self.rest_vector_combo.addItems(['first', 'all'])

        self.scale_translate_limits_check = QCheckBox('Scale translate limits')
        self.scale_linear_animation_check = QCheckBox('Scale animCurveTL translate animation')
        self.dry_run_check = QCheckBox('Dry run')
        self.write_report_check = QCheckBox('Write report txt')
        self.write_report_check.setChecked(True)

        layout.addWidget(QLabel('Scale'), 0, 0)
        layout.addWidget(self.scale_spin, 0, 1)
        layout.addWidget(QLabel('Preset'), 0, 2)
        layout.addWidget(self.preset_combo, 0, 3)
        layout.addWidget(QLabel('SDK mode'), 0, 4)
        layout.addWidget(self.sdk_combo, 0, 5)

        layout.addWidget(QLabel('Rest mode'), 1, 0)
        layout.addWidget(self.rest_combo, 1, 1)
        layout.addWidget(QLabel('Rest vector'), 1, 2)
        layout.addWidget(self.rest_vector_combo, 1, 3)
        layout.addWidget(self.scale_translate_limits_check, 1, 4, 1, 2)

        layout.addWidget(self.scale_linear_animation_check, 2, 0, 1, 2)
        layout.addWidget(self.dry_run_check, 2, 2)
        layout.addWidget(self.write_report_check, 2, 3)

        return group

    def _build_table(self) -> QTableWidget:
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(['Input file', 'Output name', 'Status'])
        self.table.horizontalHeader().setSectionResizeMode(INPUT_COL, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(OUTPUT_COL, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(STATUS_COL, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        return self.table

    def _build_run_group(self) -> QWidget:
        box = QWidget()
        layout = QVBoxLayout(box)

        button_row = QHBoxLayout()
        self.refresh_names_btn = QPushButton('Refresh Default Names')
        self.remove_selected_btn = QPushButton('Remove Selected')
        self.clear_btn = QPushButton('Clear')
        self.run_btn = QPushButton('Run')
        self.cancel_btn = QPushButton('Cancel')
        self.cancel_btn.setEnabled(False)
        button_row.addWidget(self.refresh_names_btn)
        button_row.addWidget(self.remove_selected_btn)
        button_row.addWidget(self.clear_btn)
        button_row.addStretch(1)
        button_row.addWidget(self.cancel_btn)
        button_row.addWidget(self.run_btn)

        self.progress = QProgressBar()
        self.progress.setValue(0)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setPlaceholderText('Logs and reports will appear here.')

        layout.addLayout(button_row)
        layout.addWidget(self.progress)
        layout.addWidget(self.log)
        return box

    def _connect_signals(self) -> None:
        self.browse_input_btn.clicked.connect(self.browse_single_input)
        self.add_input_btn.clicked.connect(self.add_paths_from_edit)
        self.add_multiple_btn.clicked.connect(self.browse_multiple_inputs)
        self.browse_output_btn.clicked.connect(self.browse_output_dir)
        self.refresh_names_btn.clicked.connect(self.refresh_default_names)
        self.remove_selected_btn.clicked.connect(self.remove_selected)
        self.clear_btn.clicked.connect(self.clear_files)
        self.run_btn.clicked.connect(self.start_processing)
        self.cancel_btn.clicked.connect(self.cancel_processing)
        self.table.itemSelectionChanged.connect(self.sync_selected_output_name)
        self.table.itemChanged.connect(self.handle_table_item_changed)
        self.selected_output_name_edit.editingFinished.connect(self.apply_selected_output_name)

    def browse_single_input(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, 'Select Maya ASCII file', '', 'Maya ASCII (*.ma);;All Files (*)')
        if path:
            self.input_edit.setText(path)

    def browse_multiple_inputs(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(self, 'Select Maya ASCII files', '', 'Maya ASCII (*.ma);;All Files (*)')
        if paths:
            self.add_input_paths([Path(p) for p in paths])

    def browse_output_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(self, 'Select output folder')
        if path:
            self.output_dir_edit.setText(path)

    def add_paths_from_edit(self) -> None:
        raw = self.input_edit.text().strip()
        if not raw:
            return
        paths = [Path(part.strip().strip('"')) for part in raw.split(';') if part.strip()]
        self.add_input_paths(paths)

    def add_input_paths(self, paths: list[Path]) -> None:
        self.updating_table = True
        try:
            for path in paths:
                row = self.table.rowCount()
                self.table.insertRow(row)

                input_item = QTableWidgetItem(str(path))
                input_item.setFlags(input_item.flags() & ~Qt.ItemFlag.ItemIsEditable)

                output_item = QTableWidgetItem(default_output_name(path, self.scale_spin.value()))
                output_item.setData(Qt.ItemDataRole.UserRole, False)

                status_item = QTableWidgetItem('Pending')
                status_item.setFlags(status_item.flags() & ~Qt.ItemFlag.ItemIsEditable)

                self.table.setItem(row, INPUT_COL, input_item)
                self.table.setItem(row, OUTPUT_COL, output_item)
                self.table.setItem(row, STATUS_COL, status_item)

                if not self.output_dir_edit.text().strip() and path.parent:
                    self.output_dir_edit.setText(str(path.parent))
        finally:
            self.updating_table = False
        if self.table.rowCount() and self.table.currentRow() < 0:
            self.table.selectRow(0)

    def sync_selected_output_name(self) -> None:
        row = self.table.currentRow()
        item = self.table.item(row, OUTPUT_COL) if row >= 0 else None
        self.selected_output_name_edit.setText(item.text() if item else '')

    def apply_selected_output_name(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            return
        name = self.selected_output_name_edit.text().strip()
        if not name:
            return
        item = self.table.item(row, OUTPUT_COL)
        if item:
            item.setText(name)
            item.setData(Qt.ItemDataRole.UserRole, True)

    def handle_table_item_changed(self, item: QTableWidgetItem) -> None:
        if self.updating_table or item.column() != OUTPUT_COL:
            return
        item.setData(Qt.ItemDataRole.UserRole, True)
        if item.row() == self.table.currentRow():
            self.selected_output_name_edit.setText(item.text())

    def refresh_default_names(self) -> None:
        self.updating_table = True
        try:
            for row in range(self.table.rowCount()):
                input_item = self.table.item(row, INPUT_COL)
                output_item = self.table.item(row, OUTPUT_COL)
                if input_item and output_item:
                    output_item.setText(default_output_name(Path(input_item.text()), self.scale_spin.value()))
                    output_item.setData(Qt.ItemDataRole.UserRole, False)
        finally:
            self.updating_table = False
        self.sync_selected_output_name()

    def remove_selected(self) -> None:
        row = self.table.currentRow()
        if row >= 0:
            self.table.removeRow(row)
            self.sync_selected_output_name()

    def clear_files(self) -> None:
        self.table.setRowCount(0)
        self.selected_output_name_edit.clear()
        self.progress.setValue(0)

    def set_running(self, running: bool) -> None:
        self.run_btn.setEnabled(not running)
        self.cancel_btn.setEnabled(running)
        self.add_input_btn.setEnabled(not running)
        self.add_multiple_btn.setEnabled(not running)
        self.remove_selected_btn.setEnabled(not running)
        self.clear_btn.setEnabled(not running)

    def build_options_data(self) -> dict[str, Any]:
        return {
            'scale': self.scale_spin.value(),
            'preset': self.preset_combo.currentText(),
            'sdk_mode': self.sdk_combo.currentText(),
            'sdk_node_regex': DEFAULT_SDK_LINEAR_NODE_REGEX,
            'rest_mode': self.rest_combo.currentText(),
            'rest_vector_mode': self.rest_vector_combo.currentText(),
            'scale_translate_limits': self.scale_translate_limits_check.isChecked(),
            'scale_linear_animation': self.scale_linear_animation_check.isChecked(),
            'dry_run': self.dry_run_check.isChecked(),
            'extra_vector_attr': [],
            'extra_scalar_attr': [],
            'extra_addattr_name': [],
            'rest_node_regex': DEFAULT_REST_NODE_REGEX,
            'extra_rest_regex': '',
            'write_report': self.write_report_check.isChecked(),
        }

    def build_jobs(self) -> list[dict[str, Any]]:
        output_dir_text = self.output_dir_edit.text().strip()
        jobs: list[dict[str, Any]] = []
        for row in range(self.table.rowCount()):
            input_item = self.table.item(row, INPUT_COL)
            output_item = self.table.item(row, OUTPUT_COL)
            if not input_item or not output_item:
                continue
            src = Path(input_item.text())
            output_dir = Path(output_dir_text) if output_dir_text else src.parent
            output_name = output_item.text().strip() or default_output_name(src, self.scale_spin.value())
            jobs.append({'row': row, 'input': src, 'output': output_dir / output_name})
        return jobs

    def start_processing(self) -> None:
        jobs = self.build_jobs()
        if not jobs:
            QMessageBox.warning(self, 'No files', 'Add at least one input .ma file.')
            return

        self.log.clear()
        self.progress.setRange(0, len(jobs))
        self.progress.setValue(0)
        for job in jobs:
            self.set_row_status(job['row'], 'Pending')

        self.worker = ScaleWorker(jobs, self.build_options_data())
        self.thread = QThread(self)
        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)
        self.worker.progress_changed.connect(self.update_progress)
        self.worker.row_status_changed.connect(self.set_row_status)
        self.worker.log_message.connect(self.append_log)
        self.worker.finished.connect(self.processing_finished)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)

        self.set_running(True)
        self.thread.start()

    def cancel_processing(self) -> None:
        if self.worker:
            self.worker.cancel()
            self.append_log('Cancel requested. Current file will finish first.')

    def update_progress(self, current: int, total: int) -> None:
        self.progress.setRange(0, total)
        self.progress.setValue(current)

    def set_row_status(self, row: int, status: str) -> None:
        item = self.table.item(row, STATUS_COL)
        if item:
            item.setText(status)

    def append_log(self, message: str) -> None:
        self.log.append(message)

    def processing_finished(self, ok: bool) -> None:
        self.set_running(False)
        self.append_log('Finished.' if ok else 'Finished with errors or cancellation.')
        self.worker = None
        self.thread = None


def main() -> int:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == '__main__':
    raise SystemExit(main())
