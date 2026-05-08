"""PySide6 desktop interface for VeyraLock."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .crypto import VeyraLockError, decrypt_file, encrypt_file, verify_encrypted_file
from .password import check_password_strength
from .utils import best_effort_delete_file, ensure_input_file, ensure_input_path

WINDOW_WIDTH = 760
WINDOW_HEIGHT = 540
WINDOW_MIN_WIDTH = 720
WINDOW_MIN_HEIGHT = 500
MAIN_MARGIN = 16
MAIN_SPACING = 8
TAB_MARGIN = 10
TAB_SPACING = 8
LABEL_WIDTH = 85
BUTTON_WIDTH = 90
BUTTON_HEIGHT = 30
LINE_EDIT_HEIGHT = 30
STATUS_HEIGHT = 90
STATUS_MAX_HEIGHT = 100
PROGRESS_HEIGHT = 14


def resource_path(relative_path: str) -> str:
    """Resolve resources for source runs and PyInstaller bundles."""
    if hasattr(sys, "_MEIPASS"):
        base_path = getattr(sys, "_MEIPASS")
    else:
        base_path = str(Path(__file__).resolve().parent.parent)
    return os.path.join(base_path, relative_path)


def load_app_icon() -> QIcon | None:
    """Load the optional application icon if it exists."""
    icon_path = Path(resource_path(os.path.join("assets", "veyralock.ico")))
    if not icon_path.is_file():
        return None

    icon = QIcon(str(icon_path))
    if icon.isNull():
        return None
    return icon


class EncryptionWorker(QObject):
    """Run encryption and decryption work off the UI thread."""

    finished = Signal(str)
    error = Signal(str)
    status = Signal(str)

    def __init__(
        self,
        *,
        operation: str,
        input_path: str,
        password: str,
        output_path: str | None,
        delete_original: bool = False,
        compress: bool = True,
    ) -> None:
        super().__init__()
        self.operation = operation
        self.input_path = input_path
        self.password = password
        self.output_path = output_path or None
        self.delete_original = delete_original
        self.compress = compress

    def run(self) -> None:
        """Execute the selected file operation."""
        try:
            if self.operation == "encrypt":
                self.status.emit("Preparing encryption job...")
                source = ensure_input_path(self.input_path)
                self.status.emit("Encrypting data...")
                result = encrypt_file(
                    source,
                    self.password,
                    output_path=self.output_path,
                    compress=self.compress,
                )
                self.status.emit("Verifying encrypted output...")
                verify_encrypted_file(result, self.password, expected_name=source.name)

                if self.delete_original:
                    self.status.emit("Deleting original data...")
                    if source.is_dir():
                        shutil.rmtree(source)
                    else:
                        best_effort_delete_file(source)

                self.finished.emit(str(result))
                return

            if self.operation == "decrypt":
                self.status.emit("Preparing decryption job...")
                self.status.emit("Decrypting data...")
                result = decrypt_file(
                    self.input_path,
                    self.password,
                    output_path=self.output_path,
                )
                self.finished.emit(str(result))
                return

            self.error.emit("Unknown operation selected.")
        except (FileNotFoundError, FileExistsError, ValueError, OSError, VeyraLockError) as exc:
            self.error.emit(str(exc))

    def clear_sensitive_data(self) -> None:
        """Best-effort in-process clearing of password state."""
        self.password = ""


class VeyraLockWindow(QMainWindow):
    """Main application window for VeyraLock."""

    def __init__(self) -> None:
        super().__init__()
        self.worker_thread: QThread | None = None
        self.worker: EncryptionWorker | None = None
        self.current_operation: str | None = None
        self.encrypt_buttons: list[QPushButton] = []
        self.decrypt_buttons: list[QPushButton] = []
        self._build_window()
        self._build_ui()
        self._apply_theme()

    def _build_window(self) -> None:
        self.setWindowTitle("VeyraLock")
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setMinimumSize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)

        icon = load_app_icon()
        if icon is not None:
            self.setWindowIcon(icon)

        self._center_window()

    def _center_window(self) -> None:
        """Center the window on the current screen when possible."""
        screen = self.screen() or QGuiApplication.primaryScreen()
        if screen is None:
            return

        frame = self.frameGeometry()
        frame.moveCenter(screen.availableGeometry().center())
        self.move(frame.topLeft())

    def _build_ui(self) -> None:
        central = QWidget(self)
        self.setCentralWidget(central)

        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(MAIN_MARGIN, MAIN_MARGIN, MAIN_MARGIN, MAIN_MARGIN)
        root_layout.setSpacing(MAIN_SPACING)

        root_layout.addLayout(self._build_header())

        self.tab_widget = QTabWidget()
        self.tab_widget.addTab(self._build_encrypt_tab(), "Encrypt")
        self.tab_widget.addTab(self._build_decrypt_tab(), "Decrypt")
        root_layout.addWidget(self.tab_widget, stretch=1)

        root_layout.addWidget(self._build_status_panel())

    def _build_header(self) -> QVBoxLayout:
        layout = QVBoxLayout()
        layout.setSpacing(1)

        title_label = QLabel("VeyraLock")
        title_label.setObjectName("titleLabel")
        subtitle_label = QLabel("Secure file and folder encryption")
        subtitle_label.setObjectName("subtitleLabel")

        layout.addWidget(title_label)
        layout.addWidget(subtitle_label)
        return layout

    def _build_encrypt_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(TAB_MARGIN, TAB_MARGIN, TAB_MARGIN, TAB_MARGIN)
        layout.setSpacing(TAB_SPACING)

        self.encrypt_source_edit = QLineEdit()
        self.set_line_edit_defaults(self.encrypt_source_edit)
        self.encrypt_source_edit.setPlaceholderText("Choose a file or folder")
        self.encrypt_file_button = QPushButton("File")
        self.encrypt_folder_button = QPushButton("Folder")
        self.style_button(self.encrypt_file_button)
        self.style_button(self.encrypt_folder_button)
        self.encrypt_file_button.clicked.connect(self._pick_encrypt_file)
        self.encrypt_folder_button.clicked.connect(self._pick_encrypt_folder)
        layout.addLayout(
            self.create_form_row(
                "Source",
                self.encrypt_source_edit,
                self.encrypt_file_button,
                self.encrypt_folder_button,
            )
        )

        self.encrypt_output_edit = QLineEdit()
        self.set_line_edit_defaults(self.encrypt_output_edit)
        self.encrypt_output_edit.setPlaceholderText("Optional .vlock output path")
        self.encrypt_output_button = QPushButton("Browse")
        self.style_button(self.encrypt_output_button)
        self.encrypt_output_button.clicked.connect(self._pick_encrypt_output)
        layout.addLayout(self.create_form_row("Output", self.encrypt_output_edit, self.encrypt_output_button))

        self.encrypt_password_edit = QLineEdit()
        self.set_line_edit_defaults(self.encrypt_password_edit)
        self.encrypt_password_edit.setEchoMode(QLineEdit.Password)
        self.encrypt_password_edit.setPlaceholderText("Enter password")
        layout.addLayout(self.create_form_row("Password", self.encrypt_password_edit))

        self.encrypt_confirm_edit = QLineEdit()
        self.set_line_edit_defaults(self.encrypt_confirm_edit)
        self.encrypt_confirm_edit.setEchoMode(QLineEdit.Password)
        self.encrypt_confirm_edit.setPlaceholderText("Confirm password")
        layout.addLayout(self.create_form_row("Confirm", self.encrypt_confirm_edit))

        self.encrypt_show_passwords_check = QCheckBox("Show passwords")
        self.encrypt_show_passwords_check.toggled.connect(self._toggle_encrypt_password_visibility)
        layout.addLayout(self.create_form_row("", self.encrypt_show_passwords_check))

        options_row = QHBoxLayout()
        options_row.setSpacing(TAB_SPACING)
        options_row.addSpacing(LABEL_WIDTH + TAB_SPACING)
        self.encrypt_delete_original_check = QCheckBox("Delete original")
        self.encrypt_no_compress_check = QCheckBox("No compression")
        options_row.addWidget(self.encrypt_delete_original_check)
        options_row.addWidget(self.encrypt_no_compress_check)
        options_row.addStretch(1)
        layout.addLayout(options_row)

        actions_row = QHBoxLayout()
        actions_row.setSpacing(TAB_SPACING)
        actions_row.addSpacing(LABEL_WIDTH + TAB_SPACING)
        self.encrypt_button = QPushButton("Encrypt")
        self.encrypt_clear_button = QPushButton("Clear")
        self.style_button(self.encrypt_button, primary=True)
        self.style_button(self.encrypt_clear_button)
        self.encrypt_button.clicked.connect(self._start_encrypt)
        self.encrypt_clear_button.clicked.connect(self._clear_encrypt_form)
        actions_row.addWidget(self.encrypt_button)
        actions_row.addWidget(self.encrypt_clear_button)
        actions_row.addStretch(1)
        layout.addLayout(actions_row)
        layout.addStretch(1)

        self.encrypt_buttons = [self.encrypt_button, self.encrypt_clear_button]
        return tab

    def _build_decrypt_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(TAB_MARGIN, TAB_MARGIN, TAB_MARGIN, TAB_MARGIN)
        layout.setSpacing(TAB_SPACING)

        self.decrypt_source_edit = QLineEdit()
        self.set_line_edit_defaults(self.decrypt_source_edit)
        self.decrypt_source_edit.setPlaceholderText("Choose a .vlock file")
        self.decrypt_file_button = QPushButton("Browse")
        self.style_button(self.decrypt_file_button)
        self.decrypt_file_button.clicked.connect(self._pick_decrypt_file)
        layout.addLayout(self.create_form_row("File", self.decrypt_source_edit, self.decrypt_file_button))

        self.decrypt_output_edit = QLineEdit()
        self.set_line_edit_defaults(self.decrypt_output_edit)
        self.decrypt_output_edit.setPlaceholderText("Optional restore path")
        self.decrypt_output_button = QPushButton("Browse")
        self.style_button(self.decrypt_output_button)
        self.decrypt_output_button.clicked.connect(self._pick_decrypt_output)
        layout.addLayout(self.create_form_row("Output", self.decrypt_output_edit, self.decrypt_output_button))

        self.decrypt_password_edit = QLineEdit()
        self.set_line_edit_defaults(self.decrypt_password_edit)
        self.decrypt_password_edit.setEchoMode(QLineEdit.Password)
        self.decrypt_password_edit.setPlaceholderText("Enter password")
        layout.addLayout(self.create_form_row("Password", self.decrypt_password_edit))

        self.decrypt_show_password_check = QCheckBox("Show password")
        self.decrypt_show_password_check.toggled.connect(self._toggle_decrypt_password_visibility)
        layout.addLayout(self.create_form_row("", self.decrypt_show_password_check))

        actions_row = QHBoxLayout()
        actions_row.setSpacing(TAB_SPACING)
        actions_row.addSpacing(LABEL_WIDTH + TAB_SPACING)
        self.decrypt_button = QPushButton("Decrypt")
        self.decrypt_clear_button = QPushButton("Clear")
        self.style_button(self.decrypt_button, primary=True)
        self.style_button(self.decrypt_clear_button)
        self.decrypt_button.clicked.connect(self._start_decrypt)
        self.decrypt_clear_button.clicked.connect(self._clear_decrypt_form)
        actions_row.addWidget(self.decrypt_button)
        actions_row.addWidget(self.decrypt_clear_button)
        actions_row.addStretch(1)
        layout.addLayout(actions_row)
        layout.addStretch(1)

        self.decrypt_buttons = [self.decrypt_button, self.decrypt_clear_button]
        return tab

    def _build_status_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("statusPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        title = QLabel("Status")
        title.setObjectName("sectionLabel")

        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(PROGRESS_HEIGHT)
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(1)

        self.status_area = QPlainTextEdit()
        self.status_area.setReadOnly(True)
        self.status_area.setFixedHeight(STATUS_HEIGHT)
        self.status_area.setMaximumHeight(STATUS_MAX_HEIGHT)
        self.status_area.setPlaceholderText("Operation status and results will appear here.")

        layout.addWidget(title)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.status_area)
        return panel

    def create_form_row(self, label_text: str, widget: QWidget, *buttons: QPushButton) -> QHBoxLayout:
        """Create a compact label-field row."""
        row = QHBoxLayout()
        row.setSpacing(TAB_SPACING)

        label = QLabel(label_text)
        label.setFixedWidth(LABEL_WIDTH)
        row.addWidget(label)

        widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        row.addWidget(widget, stretch=1)

        for button in buttons:
            row.addWidget(button)

        return row

    def style_button(self, button: QPushButton, primary: bool = False) -> None:
        """Apply consistent button sizing and style state."""
        button.setFixedSize(BUTTON_WIDTH, BUTTON_HEIGHT)
        button.setProperty("primary", primary)
        button.style().unpolish(button)
        button.style().polish(button)

    def set_line_edit_defaults(self, line_edit: QLineEdit) -> None:
        """Apply consistent line edit sizing."""
        line_edit.setFixedHeight(LINE_EDIT_HEIGHT)
        line_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def _apply_theme(self) -> None:
        self.setStyleSheet(
            """
            QWidget {
                background-color: #0d1117;
                color: #f5f7fa;
                font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif;
                font-size: 13px;
            }
            QMainWindow {
                background-color: #0d1117;
            }
            QLabel {
                background: transparent;
            }
            QLabel#titleLabel {
                font-size: 24px;
                font-weight: 700;
                color: #f5f7fa;
            }
            QLabel#subtitleLabel {
                font-size: 13px;
                color: #9fb3c8;
            }
            QLabel#sectionLabel {
                font-size: 13px;
                font-weight: 600;
                color: #dbe4ee;
            }
            QTabWidget::pane {
                border: 1px solid #26384a;
                border-radius: 8px;
                background-color: #111820;
                top: -1px;
            }
            QTabBar::tab {
                background-color: #111820;
                border: 1px solid #26384a;
                border-bottom: none;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                padding: 6px 12px;
                margin-right: 4px;
                color: #cfd9e3;
            }
            QTabBar::tab:selected {
                background-color: #162130;
                color: #f5f7fa;
            }
            QLineEdit,
            QPlainTextEdit {
                background-color: #090d13;
                border: 1px solid #26384a;
                border-radius: 6px;
                padding: 4px 8px;
                color: #f5f7fa;
                selection-background-color: #2f81f7;
            }
            QLineEdit:focus,
            QPlainTextEdit:focus {
                border-color: #2f81f7;
            }
            QPushButton {
                background-color: #1f6feb;
                border: 1px solid #327ee6;
                border-radius: 6px;
                padding: 2px 8px;
                color: #f5f7fa;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #2f81f7;
            }
            QPushButton:pressed {
                background-color: #1a5fc8;
            }
            QPushButton:disabled {
                background-color: #1a2531;
                border-color: #26384a;
                color: #7d8a99;
            }
            QPushButton[primary="true"] {
                background-color: #2f81f7;
                border-color: #58a6ff;
            }
            QCheckBox {
                spacing: 8px;
                color: #f5f7fa;
                padding: 0;
                margin: 0;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border: 1px solid #6b7c93;
                border-radius: 4px;
                background-color: #0b1016;
            }
            QCheckBox::indicator:hover {
                border: 1px solid #2f81f7;
            }
            QCheckBox::indicator:checked {
                background-color: #1f6feb;
                border: 1px solid #2f81f7;
            }
            QFrame#statusPanel {
                background-color: #111820;
                border: 1px solid #26384a;
                border-radius: 8px;
            }
            QProgressBar {
                background-color: #090d13;
                border: 1px solid #26384a;
                border-radius: 6px;
            }
            QProgressBar::chunk {
                background-color: #2f81f7;
                border-radius: 6px;
            }
            """
        )

    def _pick_encrypt_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select File")
        if path:
            self.encrypt_source_edit.setText(path)

    def _pick_encrypt_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select Folder")
        if path:
            self.encrypt_source_edit.setText(path)

    def _pick_encrypt_output(self) -> None:
        source = self.encrypt_source_edit.text().strip()
        suggested = source + ".vlock" if source else ""
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Select Output Path",
            suggested,
            "VeyraLock Files (*.vlock);;All Files (*)",
        )
        if path:
            self.encrypt_output_edit.setText(path)

    def _pick_decrypt_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Encrypted File",
            "",
            "VeyraLock Files (*.vlock);;All Files (*)",
        )
        if path:
            self.decrypt_source_edit.setText(path)

    def _pick_decrypt_output(self) -> None:
        source = self.decrypt_source_edit.text().strip()
        suggested = str(Path(source).with_suffix("")) if source else ""
        path, _ = QFileDialog.getSaveFileName(self, "Select Restore Path", suggested, "All Files (*)")
        if path:
            self.decrypt_output_edit.setText(path)

    def _toggle_encrypt_password_visibility(self, checked: bool) -> None:
        mode = QLineEdit.Normal if checked else QLineEdit.Password
        self.encrypt_password_edit.setEchoMode(mode)
        self.encrypt_confirm_edit.setEchoMode(mode)

    def _toggle_decrypt_password_visibility(self, checked: bool) -> None:
        mode = QLineEdit.Normal if checked else QLineEdit.Password
        self.decrypt_password_edit.setEchoMode(mode)

    def _set_busy(self, busy: bool) -> None:
        for button in self.encrypt_buttons + self.decrypt_buttons:
            button.setEnabled(not busy)

        self.tab_widget.tabBar().setEnabled(not busy)

        if busy:
            self.progress_bar.setRange(0, 0)
        else:
            self.progress_bar.setRange(0, 1)
            self.progress_bar.setValue(1)

    def _append_status(self, message: str) -> None:
        self.status_area.appendPlainText(message)

    def _clear_encrypt_password_fields(self) -> None:
        self.encrypt_password_edit.clear()
        self.encrypt_confirm_edit.clear()

    def _clear_decrypt_password_fields(self) -> None:
        self.decrypt_password_edit.clear()

    def _clear_encrypt_form(self) -> None:
        self.encrypt_source_edit.clear()
        self.encrypt_output_edit.clear()
        self.encrypt_delete_original_check.setChecked(False)
        self.encrypt_no_compress_check.setChecked(False)
        self.encrypt_show_passwords_check.setChecked(False)
        self._clear_encrypt_password_fields()

    def _clear_decrypt_form(self) -> None:
        self.decrypt_source_edit.clear()
        self.decrypt_output_edit.clear()
        self.decrypt_show_password_check.setChecked(False)
        self._clear_decrypt_password_fields()

    def _validate_encrypt_inputs(self) -> tuple[str, str, str | None] | None:
        source = self.encrypt_source_edit.text().strip()
        output = self.encrypt_output_edit.text().strip() or None
        password = self.encrypt_password_edit.text()
        confirm = self.encrypt_confirm_edit.text()

        if not source:
            self._show_error("Choose a file or folder to encrypt.")
            return None
        if not password:
            self._show_error("Enter an encryption password.")
            return None
        if not confirm:
            self._show_error("Confirm the encryption password.")
            return None
        if password != confirm:
            self._show_error("The confirmation password does not match.")
            return None

        try:
            ensure_input_path(source)
        except (FileNotFoundError, ValueError) as exc:
            self._show_error(str(exc))
            return None

        strength = check_password_strength(password)
        if strength.is_dangerously_short:
            self._show_error("Password is dangerously short. Use at least 8 characters.")
            return None

        if strength.warnings:
            warning_text = "\n".join(strength.warnings)
            response = QMessageBox.warning(
                self,
                "VeyraLock",
                f"{warning_text}\n\nContinue anyway?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if response != QMessageBox.Yes:
                return None

        return source, password, output

    def _validate_decrypt_inputs(self) -> tuple[str, str, str | None] | None:
        source = self.decrypt_source_edit.text().strip()
        output = self.decrypt_output_edit.text().strip() or None
        password = self.decrypt_password_edit.text()

        if not source:
            self._show_error("Choose a .vlock file to decrypt.")
            return None
        if not password:
            self._show_error("Enter the decryption password.")
            return None

        try:
            ensure_input_file(source)
        except (FileNotFoundError, ValueError) as exc:
            self._show_error(str(exc))
            return None

        return source, password, output

    def _start_encrypt(self) -> None:
        if self.worker_thread is not None and self.worker_thread.isRunning():
            self._show_error("Another operation is already running.")
            return

        validated = self._validate_encrypt_inputs()
        if validated is None:
            return

        source, password, output = validated
        self.current_operation = "encrypt"
        self.tab_widget.setCurrentIndex(0)
        self._append_status(f"Started encryption for: {Path(source).name}")
        self._launch_worker(
            operation="encrypt",
            input_path=source,
            password=password,
            output_path=output,
            delete_original=self.encrypt_delete_original_check.isChecked(),
            compress=not self.encrypt_no_compress_check.isChecked(),
        )

    def _start_decrypt(self) -> None:
        if self.worker_thread is not None and self.worker_thread.isRunning():
            self._show_error("Another operation is already running.")
            return

        validated = self._validate_decrypt_inputs()
        if validated is None:
            return

        source, password, output = validated
        self.current_operation = "decrypt"
        self.tab_widget.setCurrentIndex(1)
        self._append_status(f"Started decryption for: {Path(source).name}")
        self._launch_worker(
            operation="decrypt",
            input_path=source,
            password=password,
            output_path=output,
        )

    def _launch_worker(
        self,
        *,
        operation: str,
        input_path: str,
        password: str,
        output_path: str | None,
        delete_original: bool = False,
        compress: bool = True,
    ) -> None:
        self._set_busy(True)
        self.worker_thread = QThread(self)
        self.worker = EncryptionWorker(
            operation=operation,
            input_path=input_path,
            password=password,
            output_path=output_path,
            delete_original=delete_original,
            compress=compress,
        )
        self.worker.moveToThread(self.worker_thread)

        self.worker_thread.started.connect(self.worker.run)
        self.worker.status.connect(self._append_status)
        self.worker.finished.connect(self._handle_finished)
        self.worker.error.connect(self._handle_error)
        self.worker.finished.connect(self.worker_thread.quit)
        self.worker.error.connect(self.worker_thread.quit)
        self.worker_thread.finished.connect(self._cleanup_worker)

        self.worker_thread.start()

    def _handle_finished(self, result_path: str) -> None:
        self._set_busy(False)
        if self.current_operation == "encrypt":
            self._clear_encrypt_password_fields()
        elif self.current_operation == "decrypt":
            self._clear_decrypt_password_fields()
        self._append_status(f"Completed successfully: {result_path}")
        QMessageBox.information(self, "VeyraLock", f"Operation completed.\n\nOutput: {result_path}")
        self.current_operation = None

    def _handle_error(self, message: str) -> None:
        self._set_busy(False)
        if self.current_operation == "encrypt":
            self._clear_encrypt_password_fields()
        elif self.current_operation == "decrypt":
            self._clear_decrypt_password_fields()
        self._append_status(f"Error: {message}")
        self._show_error(message)
        self.current_operation = None

    def _cleanup_worker(self) -> None:
        if self.worker is not None:
            self.worker.clear_sensitive_data()
            self.worker.deleteLater()
        if self.worker_thread is not None:
            self.worker_thread.deleteLater()
        self.worker = None
        self.worker_thread = None

    def _show_error(self, message: str) -> None:
        QMessageBox.warning(self, "VeyraLock", message)


def main() -> int:
    """Launch the VeyraLock GUI application."""
    app = QApplication(sys.argv)
    app.setApplicationName("VeyraLock")
    app.setOrganizationName("VeyraLock")

    icon = load_app_icon()
    if icon is not None:
        app.setWindowIcon(icon)

    window = VeyraLockWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
