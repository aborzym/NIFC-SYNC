from PySide6.QtCore import QThread, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from core.network import (
    connect_and_list_smb_shares,
    discover_smb_servers,
    mount_smb_share,
)
from gui.network_worker import NetworkTaskWorker


class NetworkBrowserDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.task_thread = None
        self.task_worker = None
        self.selected_share = None
        self.current_username = ""
        self.current_password = ""
        self.current_domain = "WORKGROUP"
        self._accept_when_idle = False

        self.setWindowTitle("Przeglądaj zasoby sieciowe")
        self.setMinimumWidth(620)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        title = QLabel("Połącz z udziałem SMB")
        title_font = title.font()
        title_font.setPointSize(title_font.pointSize() + 3)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)

        description = QLabel(
            "Wybierz wykryty komputer, zaloguj się, "
            "a następnie wskaż udostępniony folder."
        )
        description.setWordWrap(True)
        layout.addWidget(description)

        layout.addWidget(self._create_server_group())
        layout.addWidget(self._create_credentials_group())
        layout.addWidget(self._create_share_group())

        self.status_label = QLabel("Gotowy")
        self.status_label.setObjectName("subtitle")
        layout.addWidget(self.status_label)

        buttons = QDialogButtonBox(QDialogButtonBox.Cancel)
        self.cancel_button = buttons.button(QDialogButtonBox.Cancel)
        self.cancel_button.setText("Anuluj")
        self.cancel_button.setIcon(QIcon())
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        QTimer.singleShot(0, self._discover_servers)

    def _create_server_group(self):
        group = QGroupBox("Komputer w sieci")
        layout = QHBoxLayout(group)

        self.server_combo = QComboBox()
        self.server_combo.setEnabled(False)

        self.refresh_button = QPushButton("Odśwież")
        self.refresh_button.clicked.connect(self._discover_servers)

        layout.addWidget(self.server_combo, stretch=1)
        layout.addWidget(self.refresh_button)

        return group

    def _create_credentials_group(self):
        group = QGroupBox("Logowanie SMB")
        layout = QVBoxLayout(group)

        self.username_edit = QLineEdit()
        self.username_edit.setPlaceholderText("Użytkownik")
        self.username_edit.setClearButtonEnabled(True)

        self.domain_edit = QLineEdit("WORKGROUP")
        self.domain_edit.setPlaceholderText("Domena")

        self.password_edit = QLineEdit()
        self.password_edit.setPlaceholderText("Hasło")
        self.password_edit.setEchoMode(QLineEdit.Password)
        self.password_edit.setClearButtonEnabled(True)

        self.connect_button = QPushButton("Zaloguj i pokaż udziały")
        self.connect_button.setObjectName("primaryButton")
        self.connect_button.setEnabled(False)
        self.connect_button.clicked.connect(self._connect_to_server)

        layout.addWidget(self.username_edit)
        layout.addWidget(self.domain_edit)
        layout.addWidget(self.password_edit)
        layout.addWidget(self.connect_button)

        return group

    def _create_share_group(self):
        group = QGroupBox("Udostępniony folder")
        layout = QHBoxLayout(group)

        self.share_combo = QComboBox()
        self.share_combo.setEnabled(False)

        self.mount_button = QPushButton("Zamontuj wybrany folder")
        self.mount_button.setEnabled(False)
        self.mount_button.clicked.connect(self._mount_selected_share)

        layout.addWidget(self.share_combo, stretch=1)
        layout.addWidget(self.mount_button)

        return group

    def _run_task(
        self,
        callback,
        arguments,
        success_handler,
        status,
    ):
        if self.task_thread is not None:
            return

        self.status_label.setText(status)
        self._set_busy(True)

        self.task_thread = QThread(self)
        self.task_worker = NetworkTaskWorker(
            callback,
            *arguments,
        )
        self.task_worker.moveToThread(self.task_thread)

        self.task_thread.started.connect(self.task_worker.run)
        self.task_worker.completed.connect(success_handler)
        self.task_worker.failed.connect(self._task_failed)
        self.task_worker.finished.connect(self.task_thread.quit)
        self.task_worker.finished.connect(self.task_worker.deleteLater)
        self.task_thread.finished.connect(self.task_thread.deleteLater)
        self.task_thread.finished.connect(self._task_finished)
        self.task_thread.start()

    def _discover_servers(self):
        self.server_combo.clear()
        self.share_combo.clear()
        self.selected_share = None

        self._run_task(
            discover_smb_servers,
            (),
            self._servers_loaded,
            "Wyszukiwanie komputerów w sieci…",
        )

    def _servers_loaded(self, servers):
        for server in servers:
            self.server_combo.addItem(
                server.display_name,
                server,
            )

        if servers:
            self.status_label.setText("Wybierz komputer i podaj dane logowania.")
        else:
            self.status_label.setText("Nie znaleziono serwerów SMB.")

    def _connect_to_server(self):
        server = self.server_combo.currentData()
        username = self.username_edit.text().strip()
        password = self.password_edit.text()
        domain = self.domain_edit.text().strip() or "WORKGROUP"

        if server is None:
            QMessageBox.warning(
                self,
                "Nie wybrano komputera",
                "Wybierz komputer z listy.",
            )
            return

        if not username or not password:
            QMessageBox.warning(
                self,
                "Brak danych logowania",
                "Podaj użytkownika i hasło SMB.",
            )
            return

        self.current_username = username
        self.current_password = password
        self.current_domain = domain
        self.share_combo.clear()

        self._run_task(
            connect_and_list_smb_shares,
            (
                server.uri,
                username,
                password,
                domain,
            ),
            self._shares_loaded,
            "Logowanie i pobieranie listy udziałów…",
        )

    def _shares_loaded(self, shares):
        for share in shares:
            self.share_combo.addItem(
                share.display_name,
                share,
            )

        if shares:
            self.status_label.setText("Wybierz folder do zamontowania.")
        else:
            self.status_label.setText("Nie znaleziono udostępnionych folderów.")

    def _mount_selected_share(self):
        share = self.share_combo.currentData()

        if share is None:
            return

        self.selected_share = share
        self._run_task(
            mount_smb_share,
            (
                share.uri,
                self.current_username,
                self.current_password,
                self.current_domain,
            ),
            self._share_mounted,
            "Montowanie wybranego folderu…",
        )

    def _share_mounted(self, _result):
        self.status_label.setText("Folder został zamontowany.")
        self._accept_when_idle = True

    def _task_failed(self, message):
        self.status_label.setText("Operacja nie powiodła się.")
        QMessageBox.warning(
            self,
            "Błąd połączenia sieciowego",
            message,
        )

    def _task_finished(self):
        self.task_thread = None
        self.task_worker = None
        self._set_busy(False)

        if self._accept_when_idle:
            self._accept_when_idle = False
            QTimer.singleShot(0, self.accept)

    def _set_busy(self, busy):
        self.server_combo.setEnabled(not busy and self.server_combo.count() > 0)
        self.refresh_button.setEnabled(not busy)
        self.username_edit.setEnabled(not busy)
        self.domain_edit.setEnabled(not busy)
        self.password_edit.setEnabled(not busy)
        self.connect_button.setEnabled(not busy and self.server_combo.count() > 0)
        self.share_combo.setEnabled(not busy and self.share_combo.count() > 0)
        self.mount_button.setEnabled(not busy and self.share_combo.count() > 0)
        self.cancel_button.setEnabled(not busy)

    def reject(self):
        if self.task_thread is not None:
            return

        super().reject()

    def closeEvent(self, event):
        if self.task_thread is not None:
            event.ignore()
            return

        super().closeEvent(event)
