"""Agent output pane — collapsible panel with result cards, mode dropdown, and prompt field."""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from .models import AgentMode, AgentResult


class AgentCard(QWidget):
    """A single result card in the agent pane."""

    def __init__(self, mode: AgentMode, query: str | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(8, 6, 8, 6)

        ts = datetime.now().strftime("%H:%M:%S")
        header = f"{ts} [{mode.value}]"
        if query:
            header += f" — {query}"

        header_label = QLabel(f"<b>{header}</b>")
        header_label.setWordWrap(True)
        self._layout.addWidget(header_label)

        self._content = QLabel("")
        self._content.setWordWrap(True)
        self._content.setTextFormat(Qt.PlainText)
        self._content.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._layout.addWidget(self._content)

        self._text_parts: list[str] = []

        self.setStyleSheet(
            "AgentCard { background: #1e1e2e; border: 1px solid #444; "
            "border-radius: 6px; margin: 2px 0; }"
        )

    def append_token(self, token: str) -> None:
        self._text_parts.append(token)
        self._content.setText("".join(self._text_parts))

    def set_response(self, text: str) -> None:
        self._text_parts = [text]
        self._content.setText(text)


class AgentControls(QWidget):
    """Mode dropdown + Ask Agent button + prompt field."""

    triggered = Signal(object, str)  # mode (AgentMode), query (empty for zero-input modes)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._mode = QComboBox()
        for m in AgentMode:
            self._mode.addItem(m.value, userData=m)
        self._mode.currentIndexChanged.connect(self._on_mode_changed)

        self._prompt = QLineEdit()
        self._prompt.setPlaceholderText("Ask a question...")
        self._prompt.returnPressed.connect(self._fire)
        self._prompt.setVisible(False)

        self._btn = QPushButton("🤖 Ask Agent")
        self._btn.clicked.connect(self._fire)

        layout.addWidget(self._mode)
        layout.addWidget(self._prompt, stretch=1)
        layout.addWidget(self._btn)

    def _current_mode(self) -> AgentMode:
        data = self._mode.currentData()
        if isinstance(data, AgentMode):
            return data
        # PySide6 may return userData as string — look up by display text
        text = self._mode.currentText()
        for m in AgentMode:
            if m.value == text:
                return m
        return AgentMode.SUMMARY

    _PERSUASION_MODES = (AgentMode.PERSUADE, AgentMode.DEBRIEF)

    def _on_mode_changed(self) -> None:
        mode = self._current_mode()
        self._prompt.setVisible(mode.needs_prompt)
        if mode in self._PERSUASION_MODES:
            self._prompt.setPlaceholderText("Set your goal (e.g. convince CTO to adopt Rust)…")
        else:
            self._prompt.setPlaceholderText("Ask a question…")

    def _fire(self) -> None:
        mode = self._current_mode()
        query = self._prompt.text().strip() if mode.needs_prompt else ""
        self.triggered.emit(mode, query)
        # Keep the goal text for persuasion modes so it persists across triggers
        if mode not in self._PERSUASION_MODES:
            self._prompt.clear()

    def focus_qa(self) -> None:
        """Switch to Q&A mode and focus the prompt field."""
        for i in range(self._mode.count()):
            if self._mode.itemData(i) == AgentMode.QA:
                self._mode.setCurrentIndex(i)
                break
        self._prompt.setFocus()

    def set_enabled(self, enabled: bool) -> None:
        self._mode.setEnabled(enabled)
        self._btn.setEnabled(enabled)
        self._prompt.setEnabled(enabled)


class AgentPane(QWidget):
    """Scrollable pane displaying agent result cards."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        header = QLabel("🤖 Agent")
        header.setStyleSheet("font-weight: bold; padding: 4px;")
        layout.addWidget(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self._container = QWidget()
        self._cards_layout = QVBoxLayout(self._container)
        self._cards_layout.setAlignment(Qt.AlignTop)
        self._cards_layout.setContentsMargins(4, 4, 4, 4)
        scroll.setWidget(self._container)
        layout.addWidget(scroll)

        self._scroll = scroll
        self._current_card: AgentCard | None = None

    def start_card(self, mode: AgentMode, query: str | None = None) -> None:
        card = AgentCard(mode, query)
        self._cards_layout.addWidget(card)
        self._current_card = card
        self._scroll_to_bottom()

    def append_token(self, token: str) -> None:
        if self._current_card is not None:
            self._current_card.append_token(token)
            self._scroll_to_bottom()

    def finalize(self, result: AgentResult) -> None:
        if self._current_card is not None:
            self._current_card.set_response(result.response)
            self._current_card = None

    def show_error(self, message: str) -> None:
        if self._current_card is not None:
            self._current_card.set_response(f"⚠ Error: {message}")
            self._current_card = None

    def _scroll_to_bottom(self) -> None:
        sb = self._scroll.verticalScrollBar()
        sb.setValue(sb.maximum())
