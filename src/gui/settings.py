from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class SettingsDialog(QDialog):
    def __init__(
        self,
        include_state: bool,
        model_path: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Configurações")
        self.fetch_requested = False
        self.model_path = model_path

        self.include_state_check = QCheckBox("Salvar o state JSON nos planos")
        self.include_state_check.setChecked(include_state)

        path_edit = QLineEdit(model_path)
        path_edit.setReadOnly(True)
        fetch_button = QPushButton("Baixar modelo")
        fetch_button.clicked.connect(self._request_fetch)
        path_row = QHBoxLayout()
        path_row.addWidget(path_edit)
        path_row.addWidget(fetch_button)

        form = QFormLayout()
        form.addRow("Privacidade:", self.include_state_check)
        form.addRow("Modelo:", path_row)
        form.addRow(QLabel("A pasta é escolhida pelo modelo, sem abstenção."))

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def _request_fetch(self) -> None:
        self.fetch_requested = True
        self.accept()

    def values(self) -> bool:
        return self.include_state_check.isChecked()
