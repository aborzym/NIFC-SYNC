import re
import subprocess
from dataclasses import dataclass
from urllib.parse import quote


class NetworkShareError(RuntimeError):
    pass


@dataclass(frozen=True)
class SmbResource:
    display_name: str
    uri: str


def _run_gio(
    arguments,
    *,
    input_text=None,
    timeout=20,
    error_message,
):
    try:
        result = subprocess.run(
            ["gio", *arguments],
            input=input_text,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError:
        raise NetworkShareError("System nie udostępnia narzędzia GIO.") from None
    except subprocess.TimeoutExpired:
        raise NetworkShareError("Operacja sieciowa przekroczyła limit czasu.") from None

    if result.returncode != 0:
        raise NetworkShareError(error_message)

    return result.stdout


def discover_smb_servers():
    output = _run_gio(
        [
            "list",
            "-a",
            ("standard::display-name,standard::target-uri"),
            "network:///",
        ],
        error_message=("Nie udało się wyszukać urządzeń sieciowych."),
    )
    resources = []

    for line in output.splitlines():
        match = re.search(
            r"standard::display-name=(.*?) "
            r"standard::target-uri=(\S+)",
            line,
        )

        if match is None:
            continue

        display_name, uri = match.groups()

        if not uri.lower().startswith("smb://"):
            continue

        resources.append(
            SmbResource(
                display_name=display_name,
                uri=uri,
            )
        )

    return tuple(resources)


def authenticate_smb(
    uri,
    username,
    password,
    domain="WORKGROUP",
):
    values = (username, password, domain)

    if any("\n" in value or "\r" in value for value in values):
        raise NetworkShareError("Dane logowania zawierają niedozwolony znak.")

    _run_gio(
        ["mount", uri],
        input_text=(f"{username}\n{domain}\n{password}\n"),
        timeout=60,
        error_message=("Logowanie do udziału SMB nie powiodło się."),
    )


def list_smb_shares(server_uri):
    output = _run_gio(
        [
            "list",
            "-a",
            "standard::display-name",
            server_uri,
        ],
        error_message=("Nie udało się pobrać listy udziałów SMB."),
    )
    resources = []
    base_uri = server_uri.rstrip("/")

    for line in output.splitlines():
        name, separator, attributes = line.partition("\t")

        if not separator:
            continue

        marker = "standard::display-name="
        marker_position = attributes.find(marker)

        if marker_position == -1:
            display_name = name
        else:
            display_name = attributes[marker_position + len(marker) :]

        resources.append(
            SmbResource(
                display_name=display_name,
                uri=f"{base_uri}/{quote(name, safe='')}",
            )
        )

    return tuple(resources)


def mount_smb_share(
    share_uri,
    username,
    password,
    domain="WORKGROUP",
):
    authenticate_smb(
        share_uri,
        username,
        password,
        domain,
    )
