from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QThread, Signal

ProgressFn = Callable[[str], None]


class Worker(QThread):
    progress = Signal(str)
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, fn: Callable[[ProgressFn], object], parent=None) -> None:
        super().__init__(parent)
        self._fn = fn

    def run(self) -> None:
        try:
            self.done.emit(self._fn(self.progress.emit))
        except Exception as error:
            self.failed.emit(str(error))
