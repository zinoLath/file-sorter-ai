from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Callable

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QCloseEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QToolBar,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.api import ApplyResult, FileSorter, FolderNode, Plan
from gui.settings import SettingsDialog
from gui.worker import Worker

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "example.xml"


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("File Sorter AI")
        self.resize(1180, 760)
        settings = FileSorter.load_settings()
        env_include = FileSorter.env_bool("FSORT_INCLUDE_STATE")
        self.include_state = (
            env_include
            if env_include is not None
            else bool(settings.get("include_state", False))
        )
        model_value = (
            os.environ.get("FSORT_MODEL_PATH")
            or settings.get("model_path")
            or FileSorter.default_model_path()
        )
        self.model_path = Path(str(model_value)).expanduser()
        self.sorter = self._make_sorter()
        self.schema_path: Path | None = None
        self.current_plan: Plan | None = None
        self._worker: Worker | None = None
        self._updating = False
        self._dirty = False
        self._schema_ok = True
        self._budget_timer = QTimer(self)
        self._budget_timer.setSingleShot(True)
        self._budget_timer.setInterval(250)
        self._budget_timer.timeout.connect(self._update_validation)
        self._build_toolbar()
        self._build_central()
        self._load_schema_file(DEFAULT_SCHEMA)

    def _make_sorter(self) -> FileSorter:
        return FileSorter(
            model_path=self.model_path,
        )

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("principal")
        self.addToolBar(toolbar)
        for label, handler in (
            ("Novo", self._new_schema),
            ("Abrir…", self._open_schema),
            ("Salvar", self._save_schema),
        ):
            action = QAction(label, self)
            action.triggered.connect(handler)
            toolbar.addAction(action)
        toolbar.addSeparator()
        for label, handler in (
            ("Adicionar pasta", self._add_root_folder),
            ("Adicionar subpasta", self._add_child_folder),
            ("Remover", self._remove_selected),
        ):
            action = QAction(label, self)
            action.triggered.connect(handler)
            toolbar.addAction(action)
        toolbar.addSeparator()
        settings_action = QAction("Configurações…", self)
        settings_action.triggered.connect(self._open_settings)
        toolbar.addAction(settings_action)

    def _build_central(self) -> None:
        splitter = QSplitter(Qt.Horizontal)
        self.setCentralWidget(splitter)

        self.tree = QTreeWidget()
        self.tree.setColumnCount(2)
        self.tree.setHeaderLabels(["Pasta", "Prompt"])
        self.tree.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed)
        self.tree.itemChanged.connect(self._on_item_changed)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(4, 4, 4, 4)
        hint = QLabel(
            "Duplo clique edita pasta e prompt. O prompt de cada pasta é usado como "
            "critério de classificação dos arquivos."
        )
        hint.setWordWrap(True)
        left_layout.addWidget(hint)
        left_layout.addWidget(self.tree)
        self.budget_label = QLabel()
        self.budget_label.setWordWrap(True)
        left_layout.addWidget(self.budget_label)
        splitter.addWidget(left)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(4, 4, 4, 4)

        form = QFormLayout()
        self.source_edit = QLineEdit()
        source_browse = QPushButton("…")
        source_browse.setFixedWidth(32)
        source_browse.clicked.connect(self._browse_source)
        source_row = QHBoxLayout()
        source_row.addWidget(self.source_edit)
        source_row.addWidget(source_browse)
        form.addRow("Pasta de origem:", source_row)

        self.target_edit = QLineEdit()
        target_browse = QPushButton("…")
        target_browse.setFixedWidth(32)
        target_browse.clicked.connect(self._browse_target)
        target_row = QHBoxLayout()
        target_row.addWidget(self.target_edit)
        target_row.addWidget(target_browse)
        form.addRow("Raiz de destino:", target_row)

        self.dry_run_check = QCheckBox("Simular (não mover arquivos)")
        self.dry_run_check.setChecked(True)
        form.addRow(self.dry_run_check)

        self.model_status_label = QLabel()
        form.addRow("Modelo:", self.model_status_label)
        right_layout.addLayout(form)

        self.plan_button = QPushButton("Analisar arquivos")
        self.plan_button.clicked.connect(self._plan)
        right_layout.addWidget(self.plan_button)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Origem", "Destino", "Confiança", "Motivo"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        right_layout.addWidget(self.table)

        self.execute_button = QPushButton("Executar movimentações")
        self.execute_button.setEnabled(False)
        self.execute_button.clicked.connect(self._execute)
        right_layout.addWidget(self.execute_button)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        right_layout.addWidget(self.log)

        splitter.addWidget(right)
        splitter.setSizes([430, 750])

    def _populate_tree(self, roots: list[FolderNode]) -> None:
        self._updating = True
        self.tree.clear()
        for root in roots:
            self._insert_node(root)
        self.tree.expandAll()
        self._updating = False
        self._update_validation()

    def _insert_node(self, node: FolderNode, parent: QTreeWidgetItem | None = None) -> QTreeWidgetItem:
        item = QTreeWidgetItem([node.name, node.prompt])
        item.setFlags(item.flags() | Qt.ItemIsEditable)
        if parent is None:
            self.tree.addTopLevelItem(item)
        else:
            parent.addChild(item)
        for child in node.children:
            self._insert_node(child, item)
        return item

    def _node_from_item(self, item: QTreeWidgetItem) -> FolderNode:
        node = FolderNode(name=item.text(0), prompt=item.text(1))
        for index in range(item.childCount()):
            node.children.append(self._node_from_item(item.child(index)))
        return node

    def _folders_from_tree(self) -> list[FolderNode]:
        return [
            self._node_from_item(self.tree.topLevelItem(index))
            for index in range(self.tree.topLevelItemCount())
        ]

    def _on_item_changed(self, item: QTreeWidgetItem, column: int) -> None:
        if self._updating:
            return
        if column == 0:
            sanitized = self.sorter.sanitize_name(item.text(0))
            if sanitized != item.text(0):
                self._updating = True
                item.setText(0, sanitized)
                self._updating = False
        self._mark_dirty()
        self._budget_timer.start()

    def _mark_dirty(self) -> None:
        if not self._dirty:
            self._dirty = True
            self._update_title()

    def _update_title(self) -> None:
        suffix = " *" if self._dirty else ""
        self.setWindowTitle(f"File Sorter AI{suffix}")

    def _load_schema_file(self, path: Path) -> None:
        try:
            roots = self.sorter.load_schema(path)
        except Exception:
            self.schema_path = None
            self._populate_tree([FolderNode("documentos", "Documentos importantes")])
            return
        self.schema_path = path
        self._populate_tree(roots)
        self._dirty = False
        self._update_title()
        self._update_model_status()

    def _new_schema(self) -> None:
        self.schema_path = None
        self._populate_tree([FolderNode("documentos", "")])
        self._mark_dirty()

    def _open_schema(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Abrir schema", "", "Schema XML (*.xml)")
        if path:
            self._load_schema_file(Path(path))

    def _save_schema(self) -> None:
        self._ensure_schema_saved()

    def _ensure_schema_saved(self) -> bool:
        if self.schema_path is None:
            path, _ = QFileDialog.getSaveFileName(
                self, "Salvar schema", str(DEFAULT_SCHEMA.parent / "meu-schema.xml"), "Schema XML (*.xml)"
            )
            if not path:
                return False
            self.schema_path = Path(path)
        self.sorter.save_schema(self.schema_path, self._folders_from_tree())
        self._dirty = False
        self._update_title()
        self._log(f"Schema salvo em {self.schema_path}")
        return True

    def _add_root_folder(self) -> None:
        self._insert_node(FolderNode(self.sorter.sanitize_name("nova_pasta"), ""))
        self.tree.expandAll()
        self._mark_dirty()
        self._budget_timer.start()

    def _add_child_folder(self) -> None:
        current = self.tree.currentItem()
        if current is None:
            self._add_root_folder()
            return
        child = self._insert_node(FolderNode(self.sorter.sanitize_name("nova_subpasta"), ""), current)
        current.setExpanded(True)
        self.tree.setCurrentItem(child)
        self._mark_dirty()
        self._budget_timer.start()

    def _remove_selected(self) -> None:
        current = self.tree.currentItem()
        if current is None:
            return
        self._updating = True
        parent = current.parent()
        if parent is None:
            index = self.tree.indexOfTopLevelItem(current)
            self.tree.takeTopLevelItem(index)
        else:
            parent.removeChild(current)
        if self.tree.topLevelItemCount() == 0:
            self._insert_node(FolderNode("documentos", ""))
        self._updating = False
        self._mark_dirty()
        self._budget_timer.start()

    def _browse_source(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Pasta de origem")
        if path:
            self.source_edit.setText(path)
            if not self.target_edit.text():
                self.target_edit.setText(path)

    def _browse_target(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Raiz de destino")
        if path:
            self.target_edit.setText(path)

    def _update_validation(self) -> None:
        roots = self._folders_from_tree()
        issues = self.sorter.validate_schema(roots)
        errors = [issue for issue in issues if issue.severity == "error"]
        warnings = [issue for issue in issues if issue.severity == "warning"]
        try:
            report = self.sorter.budget_report(roots)
            overflow = bool(report.option_overflows) or report.combined_overflows
            budget = report.summary()
        except Exception as error:
            overflow = False
            budget = f"orçamento indisponível: {error}"
        if errors:
            text = "Erro: " + errors[0].message
            color = "#b00020"
        elif overflow:
            text = f"Orçamento estourado — {budget}"
            color = "#b00020"
        else:
            text = budget
            color = "#555555"
            if warnings:
                text += f" · aviso: {warnings[0].message}"
        self.budget_label.setText(text)
        self.budget_label.setStyleSheet(f"color: {color};")
        self._schema_ok = not errors and not overflow
        self.plan_button.setEnabled(self._schema_ok and self._worker is None)

    def _update_model_status(self) -> None:
        self.model_status_label.setText(self.sorter.model_status())

    def _open_settings(self) -> None:
        dialog = SettingsDialog(
            self.include_state,
            str(self.model_path),
            self,
        )
        if dialog.exec() != SettingsDialog.Accepted:
            return
        include_state = dialog.values()
        self.include_state = include_state
        self.sorter = self._make_sorter()
        settings = FileSorter.load_settings()
        settings.update(
            {
                "include_state": self.include_state,
                "model_path": str(self.model_path),
            }
        )
        FileSorter.save_settings(settings)
        self._log("Configurações salvas.")
        self._update_model_status()
        self._update_validation()
        if dialog.fetch_requested:
            self._fetch_model()

    def _fetch_model(self) -> None:
        self.model_status_label.setText("baixando")

        def job(progress):
            return self.sorter.fetch_model(progress=progress)

        self._start_worker(job, self._fetch_done)

    def _fetch_done(self, path: Path) -> None:
        self._worker_cleanup()
        self._log(f"Modelo disponível em {path}")
        self._update_model_status()

    def _log(self, message: str) -> None:
        self.log.appendPlainText(message)

    def _start_worker(
        self, job: Callable[[Callable[[str], None]], object], on_done: Callable[[object], None]
    ) -> None:
        if self._worker is not None:
            QMessageBox.information(self, "Ocupado", "Já existe uma operação em andamento.")
            return
        worker = Worker(job, self)
        worker.progress.connect(self.log.appendPlainText)
        worker.done.connect(on_done)
        worker.failed.connect(self._worker_failed)
        worker.finished.connect(worker.deleteLater)
        self._worker = worker
        self.plan_button.setEnabled(False)
        self.execute_button.setEnabled(False)
        worker.start()

    def _worker_cleanup(self) -> None:
        self._worker = None
        self.plan_button.setEnabled(self._schema_ok)

    def _worker_failed(self, message: str) -> None:
        self._worker_cleanup()
        self.model_status_label.setText("erro")
        self._log(f"Erro: {message}")
        QMessageBox.critical(self, "Erro", message)

    def _plan(self) -> None:
        source = Path(self.source_edit.text().expanduser())
        if not source.is_dir():
            QMessageBox.warning(self, "Origem inválida", "Escolha uma pasta de origem existente.")
            return
        if not self._schema_ok:
            QMessageBox.warning(self, "Schema inválido", "Corrija os erros do schema antes de analisar.")
            return
        if not self._ensure_schema_saved():
            return
        target = self.target_edit.text().strip() or str(source)
        schema = self.schema_path
        if not self.sorter.is_model_loaded():
            self.model_status_label.setText("carregando")

        def job(progress):
            return self.sorter.plan(
                schema,
                source,
                target_root=target,
                include_state=self.include_state,
                progress=progress,
            )

        self._log("Analisando arquivos…")
        self._start_worker(job, self._plan_done)

    def _plan_done(self, plan: Plan) -> None:
        self._worker_cleanup()
        self.current_plan = plan
        self.table.setRowCount(0)
        for entry in plan.entries:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(entry.source))
            self.table.setItem(row, 1, QTableWidgetItem(entry.target))
            self.table.setItem(row, 2, QTableWidgetItem(f"{entry.confidence:.0%}"))
            reason = QTableWidgetItem(entry.reason)
            reason.setToolTip(json.dumps(entry.route, ensure_ascii=False))
            self.table.setItem(row, 3, reason)
        self.execute_button.setEnabled(bool(plan.entries) and not self.dry_run_check.isChecked())
        message = f"{len(plan.entries)} arquivo(s) classificado(s)."
        if plan.skipped:
            message += f" {len(plan.skipped)} pulado(s)."
            for skipped in plan.skipped:
                self._log(f"Pulado: {skipped.source} ({skipped.reason}: {skipped.detail})")
        if self.dry_run_check.isChecked():
            message += " (simulação: nada foi movido)"
        self._log(message)
        self._update_model_status()

    def _execute(self) -> None:
        if self.current_plan is None:
            return

        def job(progress):
            return self.sorter.apply_plan(self.current_plan, progress=progress)

        self._start_worker(job, self._execute_done)

    def _execute_done(self, result: ApplyResult) -> None:
        self._worker_cleanup()
        plan_id = self.current_plan.id if self.current_plan is not None else None
        positions = {
            self.table.item(row, 0).text(): row
            for row in range(self.table.rowCount())
            if self.table.item(row, 0) is not None
        }
        for moved in result.moved:
            row = positions.get(moved.source)
            if row is not None:
                self.table.setItem(row, 1, QTableWidgetItem(moved.target))
        for failure in result.failed:
            self._log(f"Falhou: {failure.source}: {failure.error}")
        if any(failure.retryable for failure in result.failed) and plan_id is not None:
            self._log(f"Tente com privilégio: sudo fsort apply --plan {plan_id}")
        self.execute_button.setEnabled(False)
        self.current_plan = None
        self._log(f"{len(result.moved)} arquivo(s) movido(s).")

    def closeEvent(self, event: QCloseEvent) -> None:
        if not self._dirty:
            event.accept()
            return
        choice = QMessageBox.question(
            self,
            "Salvar schema?",
            "O schema tem alterações não salvas.",
            QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
            QMessageBox.Save,
        )
        if choice == QMessageBox.Save:
            if self._ensure_schema_saved():
                event.accept()
            else:
                event.ignore()
        elif choice == QMessageBox.Discard:
            event.accept()
        else:
            event.ignore()
