import base64
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

    def submit_file(
        self,
        workflow_key,
        filename,
        content,
    ):
        if not isinstance(content, bytes):
            raise TypeError("Zawartość pliku musi być typu bytes.")

        encoded_content = base64.b64encode(content).decode("ascii")

        return self.session.post(
            (f"{self.base_url}/api/files/content/{workflow_key}/{filename}"),
            json={
                "content": encoded_content,
            },
            timeout=self.timeout,
        )
