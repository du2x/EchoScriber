from __future__ import annotations

import shutil
from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .agent_pane import AgentControls, AgentPane
from .audio.devices import AudioDevice, list_mics, list_monitors
from .config import load_settings, save_settings
from .models import AgentMode, AgentResult, SourceMode, TranscriptSegment
from .services import SessionConfig
from .session import SessionController

_ACTIVITY_THRESHOLD_DB = -40.0


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("EchoScriber")
        self.resize(980, 620)

        self.pipeline = SessionController()
        self.pipeline.partial_emitted.connect(self._on_partial)
        self.pipeline.final_emitted.connect(self._on_final)
        self.pipeline.status_changed.connect(self._set_status)
        self.pipeline.metrics_updated.connect(self._on_metrics)
        self.pipeline.error.connect(self._on_error)

        self._agent = None
        self._partial_row = ""
        self._build_ui()
        self._setup_hotkeys()
        self._load_settings()
        self._load_agent_plugin()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

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
        self.monitor_device = QComboBox()
        self.language = QComboBox()
        self.language.addItems(["en", "pt-BR"])
        self.model = QComboBox()
        self.model.addItems(["tiny", "base", "small", "medium", "large-v3"])
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

        self.agent_pane = AgentPane()
        self.agent_controls = AgentControls()
        self.agent_controls.triggered.connect(self._on_agent_triggered)

        self._splitter = QSplitter(Qt.Vertical)
        self._splitter.addWidget(self.transcript)
        self._splitter.addWidget(self.agent_pane)
        self._splitter.setSizes([650, 350])
        self.agent_pane.setVisible(False)

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
        bottom.addWidget(self.agent_controls)
        bottom.addWidget(copy_btn)
        bottom.addWidget(clear_btn)
        bottom.addWidget(save_btn)

        self._dep_bar = self._build_dep_bar()

        layout.addLayout(top_row)
        layout.addWidget(self._dep_bar)
        layout.addWidget(options)
        layout.addWidget(self._splitter)
        layout.addLayout(bottom)

        self.setCentralWidget(root)
        self._refresh_devices()
        self._check_dependencies()

    # ------------------------------------------------------------------
    # Dependency checks
    # ------------------------------------------------------------------

    @staticmethod
    def _build_dep_bar() -> QFrame:
        bar = QFrame()
        bar.setFrameShape(QFrame.StyledPanel)
        bar.setStyleSheet("background: #fff3cd; color: #856404; padding: 4px;")
        lbl = QLabel(bar)
        lbl.setObjectName("dep_label")
        row = QHBoxLayout(bar)
        row.setContentsMargins(6, 2, 6, 2)
        row.addWidget(lbl)
        bar.hide()
        return bar

    def _check_dependencies(self) -> None:
        missing = [cmd for cmd in ("parec",) if not shutil.which(cmd)]
        if missing:
            cmds = ", ".join(missing)
            label = self._dep_bar.findChild(QLabel, "dep_label")
            label.setText(
                f"Missing system tool(s): {cmds}. "
                "Install pulseaudio-utils (sudo apt install pulseaudio-utils) then restart."
            )
            self._dep_bar.show()
            self.start_btn.setEnabled(False)
            self.start_btn.setToolTip(f"Cannot start: {cmds} not found")

    # ------------------------------------------------------------------
    # Device enumeration (#10)
    # ------------------------------------------------------------------

    def _refresh_devices(self) -> None:
        mics = list_mics()
        monitors = list_monitors()
        self._populate_combo(self.mic_device, mics, "No microphone found")
        self._populate_combo(self.monitor_device, monitors, "No monitor source found")
        self.start_btn.setEnabled(bool(mics) or bool(monitors))

    @staticmethod
    def _populate_combo(combo: QComboBox, devices: list[AudioDevice], placeholder: str) -> None:
        combo.clear()
        if devices:
            for dev in devices:
                combo.addItem(dev.description, userData=dev)
        else:
            combo.addItem(placeholder)
            combo.setEnabled(False)

    def _selected_device_name(self, combo: QComboBox) -> str:
        dev = combo.currentData()
        if isinstance(dev, AudioDevice):
            return dev.name
        return combo.currentText()

    # ------------------------------------------------------------------
    # Session control
    # ------------------------------------------------------------------

    def start_session(self) -> None:
        if not shutil.which("parec"):
            QMessageBox.critical(
                self,
                "Missing dependency",
                "parec not found.\n\nInstall it with:\n  sudo apt install pulseaudio-utils",
            )
            return
        self._refresh_devices()
        config = SessionConfig(
            source_mode=SourceMode(self.source_mode.currentText()),
            mic_device=self._selected_device_name(self.mic_device),
            monitor_device=self._selected_device_name(self.monitor_device),
            echo_cancellation=self.aec.isChecked(),
            language=self.language.currentText(),
            model=self.model.currentText(),
        )
        self.pipeline.start(config)
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self._save_settings()

    def stop_session(self) -> None:
        self.pipeline.stop()
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.health.setText("Audio activity: idle")
        self.latency.setText("Latency: -- ms")
        self._save_settings()

    # ------------------------------------------------------------------
    # Signal handlers
    # ------------------------------------------------------------------

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

    def _on_metrics(self, latency_ms: int, rms_db: float) -> None:
        self.latency.setText(f"Latency: {latency_ms} ms")
        active = rms_db > _ACTIVITY_THRESHOLD_DB
        self.health.setText(f"Audio activity: {'active' if active else 'idle'}")

    def _on_error(self, message: str) -> None:
        self.statusBar().showMessage(f"Error: {message}", 8000)
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self._set_status("Error")
        self.health.setText("Audio activity: idle")
        self.latency.setText("Latency: -- ms")

    # ------------------------------------------------------------------
    # Transcript actions
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Settings persistence (#13)
    # ------------------------------------------------------------------

    def _load_settings(self) -> None:
        s = load_settings()
        self._set_combo_by_text(self.source_mode, s.get("source_mode"))
        self._set_combo_by_device_name(self.mic_device, s.get("mic_device"))
        self._set_combo_by_device_name(self.monitor_device, s.get("monitor_device"))
        self._set_combo_by_text(self.language, s.get("language"))
        self._set_combo_by_text(self.model, s.get("model"))
        if "echo_cancellation" in s:
            self.aec.setChecked(bool(s["echo_cancellation"]))

    def _save_settings(self) -> None:
        existing = load_settings()
        existing.update({
            "source_mode": self.source_mode.currentText(),
            "mic_device": self._selected_device_name(self.mic_device),
            "monitor_device": self._selected_device_name(self.monitor_device),
            "language": self.language.currentText(),
            "model": self.model.currentText(),
            "echo_cancellation": self.aec.isChecked(),
        })
        save_settings(existing)

    @staticmethod
    def _set_combo_by_text(combo: QComboBox, value: str | None) -> None:
        if value is None:
            return
        idx = combo.findText(value)
        if idx >= 0:
            combo.setCurrentIndex(idx)

    @staticmethod
    def _set_combo_by_device_name(combo: QComboBox, name: str | None) -> None:
        if name is None:
            return
        for i in range(combo.count()):
            dev = combo.itemData(i)
            if isinstance(dev, AudioDevice) and dev.name == name:
                combo.setCurrentIndex(i)
                return

    # ------------------------------------------------------------------
    # Agent plugin (#agent)
    # ------------------------------------------------------------------

    def _load_agent_plugin(self) -> None:
        settings = load_settings()
        plugin_module = settings.get("agent_plugin", "echoscriber.agents.echo_agent")
        try:
            import importlib

            mod = importlib.import_module(plugin_module)
            plugin = mod.create_plugin()
            plugin.attach(self.pipeline.store)

            agent_cfg = settings.get("agent", {})
            if hasattr(plugin, "configure"):
                plugin.configure(
                    provider=agent_cfg.get("provider", "anthropic"),
                    model=agent_cfg.get("model", "claude-sonnet-4-20250514"),
                    api_key=agent_cfg.get("api_key"),
                    base_url=agent_cfg.get("base_url"),
                    token_budget=agent_cfg.get("token_budget", 8000),
                )

            plugin.token_received.connect(self.agent_pane.append_token)
            plugin.completed.connect(self._on_agent_completed)
            plugin.error.connect(self._on_agent_error)

            self._agent = plugin
        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning("Agent plugin unavailable: %s", exc)
            self.agent_controls.set_enabled(False)

    def _setup_hotkeys(self) -> None:
        trigger = QShortcut(QKeySequence("Ctrl+Shift+A"), self)
        trigger.activated.connect(lambda: self.agent_controls._fire())

        qa = QShortcut(QKeySequence("Ctrl+Shift+Q"), self)
        qa.activated.connect(lambda: self.agent_controls.focus_qa())

    def _on_agent_triggered(self, mode: AgentMode, query: str) -> None:
        if self._agent is None:
            return
        self.agent_pane.setVisible(True)
        self.agent_pane.start_card(mode, query or None)
        self.agent_controls.set_enabled(False)
        self._agent.run(mode, query or None)

    def _on_agent_completed(self, result: AgentResult) -> None:
        self.agent_pane.finalize(result)
        self.agent_controls.set_enabled(True)

    def _on_agent_error(self, message: str) -> None:
        self.agent_pane.show_error(message)
        self.agent_controls.set_enabled(True)


__all__ = ["MainWindow"]
