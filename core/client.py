import base64
from io import BytesIO
from pathlib import Path

import requests

BASE_URL = "http://transkrypcje.nifc.pl"


def load_credentials(credentials_file):
    credentials = {}

    with Path(credentials_file).open() as file:
        for line in file:
            key, value = line.strip().split("=", 1)
            credentials[key] = value

    return credentials


class SubmissionBody(BytesIO):
    def __init__(self, payload, progress_callback):
        super().__init__(payload)
        self.total_size = len(payload)
        self.progress_callback = progress_callback

    def read(self, size=-1):
        chunk = super().read(size)
        if chunk:
            self.progress_callback(self.tell(), self.total_size)
        return chunk


class NifcClient:
    def __init__(
        self,
        session=None,
        base_url=BASE_URL,
        timeout=30,
    ):
        self.session = session or requests.Session()
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def login(self, login, password):
        return self.session.post(
            f"{self.base_url}/api/user/login",
            json={
                "login": login,
                "password": password,
            },
            timeout=self.timeout,
        )

    def get_files(self):
        return self.session.get(
            f"{self.base_url}/api/files",
            timeout=self.timeout,
        )

    def get_statistics(self, month):
        return self.session.get(
            f"{self.base_url}/api/files/statistics",
            params={
                "month": month,
                "all": "false",
            },
            timeout=self.timeout,
        )

    def submit_file(
        self,
        workflow_key,
        filename,
        content,
        progress_callback=None,
    ):
        if not isinstance(content, bytes):
            raise TypeError("Zawartość pliku musi być typu bytes.")

        encoded_content = base64.b64encode(content)
        url = f"{self.base_url}/api/files/content/{workflow_key}/{filename}"

        if progress_callback is None:
            return self.session.post(
                url,
                json={"content": encoded_content.decode("ascii")},
                timeout=self.timeout,
            )

        payload = b'{"content":"' + encoded_content + b'"}'
        with SubmissionBody(payload, progress_callback) as body:
            return self.session.post(
                url,
                data=body,
                headers={"Content-Type": "application/json"},
                timeout=self.timeout,
            )
