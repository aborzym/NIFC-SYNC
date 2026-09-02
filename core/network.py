import os
import re
import subprocess
from dataclasses import dataclass
from urllib.parse import quote

import pexpect


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


def _run_gio_mount(
    uri,
    username,
    password,
    domain,
    timeout=60,
):
    environment = os.environ.copy()
    environment["LANG"] = "C"
    environment["LC_ALL"] = "C"

    try:
        child = pexpect.spawn(
            "gio",
            ["mount", uri],
            encoding="utf-8",
            timeout=timeout,
            env=environment,
        )
    except pexpect.ExceptionPexpect:
        raise NetworkShareError("Nie udało się uruchomić montowania GIO.") from None

    user_prompt = r"User(?: \[[^\]]*\])?:"
    domain_prompt = r"Domain(?: \[[^\]]*\])?:"
    password_prompt = r"Password:"

    try:
        first_prompt = child.expect([user_prompt, pexpect.EOF])

        if first_prompt == 0:
            child.sendline(username)
            child.expect(domain_prompt)
            child.sendline(domain)
            child.expect(password_prompt)
            child.sendline(password)

            result = child.expect(
                [
                    pexpect.EOF,
                    user_prompt,
                    password_prompt,
                ]
            )

            if result != 0:
                raise NetworkShareError("Logowanie do udziału SMB nie powiodło się.")

        child.close()
    except pexpect.TIMEOUT:
        child.close(force=True)
        raise NetworkShareError(
            "Logowanie do udziału SMB przekroczyło limit czasu."
        ) from None
    except pexpect.EOF:
        child.close(force=True)
        raise NetworkShareError("Logowanie do udziału SMB nie powiodło się.") from None
    finally:
        if child.isalive():
            child.close(force=True)

    if child.exitstatus not in (0, None):
        raise NetworkShareError("Logowanie do udziału SMB nie powiodło się.")


def authenticate_smb(
    uri,
    username,
    password,
    domain="WORKGROUP",
):
    values = (username, password, domain)

    if any("\n" in value or "\r" in value for value in values):
        raise NetworkShareError("Dane logowania zawierają niedozwolony znak.")

    _run_gio_mount(
        uri,
        username,
        password,
        domain,
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


def connect_and_list_smb_shares(
    server_uri,
    username,
    password,
    domain="WORKGROUP",
):
    try:
        return list_smb_shares(server_uri)
    except NetworkShareError:
        authenticate_smb(
            server_uri,
            username,
            password,
            domain,
        )

    return list_smb_shares(server_uri)


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
