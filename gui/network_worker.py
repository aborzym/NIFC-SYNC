from PySide6.QtCore import QObject, Signal, Slot

from core.network import NetworkShareError


class NetworkTaskWorker(QObject):
    completed = Signal(object)
    failed = Signal(str)
    finished = Signal()

    def __init__(self, callback, *arguments):
        super().__init__()
        self.callback = callback
        self.arguments = arguments

    @Slot()
    def run(self):
        try:
            result = self.callback(*self.arguments)
            self.completed.emit(result)
        except NetworkShareError as error:
            self.failed.emit(str(error))
        except Exception:  # noqa: BLE001
            self.failed.emit("Wystąpił nieoczekiwany błąd operacji sieciowej.")
        finally:
            self.finished.emit()
