from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .models import SourceMode, TranscriptSegment
from .services import MockRealtimePipeline, SessionConfig


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("EchoScriber")
        self.resize(980, 620)

        self.pipeline = MockRealtimePipeline()
        self.pipeline.partial_emitted.connect(self._on_partial)
        self.pipeline.final_emitted.connect(self._on_final)
        self.pipeline.status_changed.connect(self._set_status)

        self._partial_row = ""
        self._build_ui()

    def _build_ui(self) -> None:
        root = QWidget()
        layout = QVBoxLayout(root)

        top_row = QHBoxLayout()
        self.source_mode = QComboBox()
        self.source_mode.addItems([mode.value for mode in SourceMode])
        self.start_btn = QPushButton("Start")
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setEnabled(False)
        self.status_label = QLabel("Stopped")
        self.status_label.setStyleSheet("font-weight: bold; color: #a00;")

        self.start_btn.clicked.connect(self.start_session)
        self.stop_btn.clicked.connect(self.stop_session)

        top_row.addWidget(QLabel("Source mode:"))
        top_row.addWidget(self.source_mode)
        top_row.addStretch(1)
        top_row.addWidget(self.start_btn)
        top_row.addWidget(self.stop_btn)
        top_row.addWidget(QLabel("Status:"))
        top_row.addWidget(self.status_label)

        options = QWidget()
        options_layout = QGridLayout(options)
        self.mic_device = QComboBox()
        self.mic_device.addItems(["Default Microphone", "USB Mic"])
        self.monitor_device = QComboBox()
        self.monitor_device.addItems(["Default Monitor", "alsa_output.monitor"])
        self.language = QComboBox()
        self.language.addItems(["en", "pt-BR"])
        self.model = QComboBox()
        self.model.addItems(["small", "medium", "large"])
        self.aec = QCheckBox("Echo cancellation")
        self.aec.setChecked(True)

        options_layout.addWidget(QLabel("Mic device"), 0, 0)
        options_layout.addWidget(self.mic_device, 0, 1)
        options_layout.addWidget(QLabel("System loopback"), 1, 0)
        options_layout.addWidget(self.monitor_device, 1, 1)
        options_layout.addWidget(QLabel("Language"), 2, 0)
        options_layout.addWidget(self.language, 2, 1)
        options_layout.addWidget(QLabel("Model"), 3, 0)
        options_layout.addWidget(self.model, 3, 1)
        options_layout.addWidget(self.aec, 4, 0, 1, 2)

        self.transcript = QTextEdit()
        self.transcript.setReadOnly(True)
        self.transcript.setPlaceholderText("Transcript output appears here…")

        bottom = QHBoxLayout()
        self.latency = QLabel("Latency: -- ms")
        self.health = QLabel("Audio activity: idle")
        copy_btn = QPushButton("Copy")
        clear_btn = QPushButton("Clear")
        save_btn = QPushButton("Save")
        copy_btn.clicked.connect(self.transcript.copy)
        clear_btn.clicked.connect(self._clear_transcript)
        save_btn.clicked.connect(self._save_transcript)

        bottom.addWidget(self.latency)
        bottom.addWidget(self.health)
        bottom.addStretch(1)
        bottom.addWidget(copy_btn)
        bottom.addWidget(clear_btn)
        bottom.addWidget(save_btn)

        layout.addLayout(top_row)
        layout.addWidget(options)
        layout.addWidget(self.transcript)
        layout.addLayout(bottom)

        self.setCentralWidget(root)

    def start_session(self) -> None:
        config = SessionConfig(
            source_mode=SourceMode(self.source_mode.currentText()),
            mic_device=self.mic_device.currentText(),
            monitor_device=self.monitor_device.currentText(),
            echo_cancellation=self.aec.isChecked(),
            language=self.language.currentText(),
            model=self.model.currentText(),
        )
        self.pipeline.start(config)
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.health.setText("Audio activity: active")
        self.latency.setText("Latency: ~650 ms")

    def stop_session(self) -> None:
        self.pipeline.stop()
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.health.setText("Audio activity: idle")
        self.latency.setText("Latency: -- ms")

    def _on_partial(self, segment: TranscriptSegment) -> None:
        self._partial_row = f"[{segment.source.value}] {segment.text}"
        self._render_text()

    def _on_final(self, segment: TranscriptSegment) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        self.transcript.append(f"{ts} [{segment.source.value}] {segment.text}")
        self._partial_row = ""
        self._render_text()

    def _render_text(self) -> None:
        if self._partial_row:
            self.statusBar().showMessage(f"Partial: {self._partial_row}")
        else:
            self.statusBar().clearMessage()

    def _set_status(self, value: str) -> None:
        self.status_label.setText(value)
        color = "#0a0" if value == "Running" else "#a00"
        self.status_label.setStyleSheet(f"font-weight: bold; color: {color};")

    def _clear_transcript(self) -> None:
        self.transcript.clear()
        self._partial_row = ""
        self._render_text()

    def _save_transcript(self) -> None:
        file_name, _ = QFileDialog.getSaveFileName(
            self,
            "Save transcript",
            "transcript.txt",
            "Text files (*.txt);;Markdown files (*.md)",
        )
        if not file_name:
            return
        text = self.transcript.toPlainText().strip()
        if not text:
            QMessageBox.information(self, "Nothing to save", "No transcript text to save yet.")
            return
        with open(file_name, "w", encoding="utf-8") as handle:
            handle.write(text + "\n")


__all__ = ["MainWindow"]
