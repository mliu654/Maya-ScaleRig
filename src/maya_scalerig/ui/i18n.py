"""Small runtime translation table for the PyQt6 UI."""

from __future__ import annotations


DEFAULT_LANGUAGE = 'zh_CN'

LANGUAGE_NAMES = {
    'zh_CN': '中文',
    'en_US': 'English',
}

TRANSLATIONS = {
    'en_US': {
        'app_title': 'Maya ScaleRig',
        'language': 'Language',
        'files_group': 'Files',
        'options_group': 'Process Settings',
        'input': 'Input',
        'input_placeholder': 'Input .ma path, or multiple paths separated by ;',
        'browse': 'Browse',
        'add': 'Add',
        'add_files': 'Add Files',
        'output_folder': 'Output folder',
        'output_placeholder': 'Output folder. Empty = same folder as input',
        'selected_output_name': 'Output name',
        'output_name_placeholder': 'Output name for selected row',
        'scale': 'Scale',
        'dry_run': 'Dry run',
        'write_report': 'Save report',
        'table_input_file': 'Input file',
        'table_output_name': 'Output name',
        'table_status': 'Status',
        'refresh_default_names': 'Refresh Names',
        'remove_selected': 'Remove Selected',
        'clear': 'Clear',
        'run': 'Run',
        'cancel': 'Cancel',
        'log_placeholder': 'Logs and reports will appear here.',
        'select_maya_ascii_file': 'Select Maya ASCII file',
        'select_maya_ascii_files': 'Select Maya ASCII files',
        'select_output_folder': 'Select output folder',
        'file_filter': 'Maya ASCII (*.ma);;All Files (*)',
        'no_files_title': 'No files',
        'no_files_message': 'Add at least one input .ma file.',
        'status_pending': 'Pending',
        'status_running': 'Running',
        'status_done': 'Done ({total})',
        'status_error': 'Error',
        'log_cancelled_before_remaining': 'Cancelled before remaining files were processed.',
        'log_processing': '[{index}/{total}] Processing: {path}',
        'log_input_not_found': 'Input not found: {path}',
        'error_input_output_same': 'Input and output must be different files.',
        'log_saved': 'Saved: {path}',
        'log_report': 'Report: {path}',
        'log_error': 'ERROR: {path}\n{error}',
        'log_cancel_requested': 'Cancel requested. Current file will finish first.',
        'log_finished': 'Finished.',
        'log_finished_with_errors': 'Finished with errors or cancellation.',
    },
    'zh_CN': {
        'app_title': 'Maya ScaleRig',
        'language': '语言',
        'files_group': '文件',
        'options_group': '处理设置',
        'input': '输入',
        'input_placeholder': '输入 .ma 路径；多个路径可用 ; 分隔',
        'browse': '浏览',
        'add': '添加',
        'add_files': '批量添加',
        'output_folder': '输出文件夹',
        'output_placeholder': '输出文件夹。留空则使用输入文件所在文件夹',
        'selected_output_name': '输出名称',
        'output_name_placeholder': '当前选中行的输出文件名',
        'scale': '缩放比例',
        'dry_run': '仅分析',
        'write_report': '保存报告',
        'table_input_file': '输入文件',
        'table_output_name': '输出名称',
        'table_status': '状态',
        'refresh_default_names': '刷新默认名称',
        'remove_selected': '移除选中',
        'clear': '清空',
        'run': '开始',
        'cancel': '取消',
        'log_placeholder': '日志和报告会显示在这里。',
        'select_maya_ascii_file': '选择 Maya ASCII 文件',
        'select_maya_ascii_files': '选择 Maya ASCII 文件',
        'select_output_folder': '选择输出文件夹',
        'file_filter': 'Maya ASCII (*.ma);;所有文件 (*)',
        'no_files_title': '没有文件',
        'no_files_message': '请至少添加一个输入 .ma 文件。',
        'status_pending': '等待',
        'status_running': '处理中',
        'status_done': '完成 ({total})',
        'status_error': '错误',
        'log_cancelled_before_remaining': '已取消，剩余文件不会继续处理。',
        'log_processing': '[{index}/{total}] 正在处理：{path}',
        'log_input_not_found': '找不到输入文件：{path}',
        'error_input_output_same': '输入和输出不能是同一个文件。',
        'log_saved': '已保存：{path}',
        'log_report': '报告：{path}',
        'log_error': '错误：{path}\n{error}',
        'log_cancel_requested': '已请求取消。当前文件会先处理完。',
        'log_finished': '处理完成。',
        'log_finished_with_errors': '处理结束，但有错误或取消。',
    },
}


def translate(language: str, key: str, **kwargs: object) -> str:
    text = TRANSLATIONS.get(language, TRANSLATIONS[DEFAULT_LANGUAGE]).get(key)
    if text is None:
        text = TRANSLATIONS['en_US'].get(key, key)
    if kwargs:
        return text.format(**kwargs)
    return text
