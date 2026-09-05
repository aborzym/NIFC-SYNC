import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import (
    quote,
    unquote,
    urlparse,
)

import pexpect


class NetworkShareError(RuntimeError):
    pass


@dataclass(frozen=True)
class SmbResource:
    display_name: str
    uri: str


def find_mounted_smb_path(
    share_uri,
    gvfs_root=None,
):
    parsed_uri = urlparse(share_uri)

    if parsed_uri.scheme.casefold() != "smb" or parsed_uri.hostname is None:
        return None

    path_parts = tuple(unquote(part) for part in parsed_uri.path.split("/") if part)

    if not path_parts:
        return None

    share_name = path_parts[0]
    root = (
        Path(gvfs_root)
        if gvfs_root is not None
        else (Path("/run/user") / str(os.getuid()) / "gvfs")
    )

    try:
        mount_paths = tuple(root.iterdir())
    except OSError:
        return None

    for mount_path in mount_paths:
        mount_type, separator, raw_attributes = mount_path.name.partition(":")

        if not separator or mount_type != "smb-share":
            continue

        attributes = {}

        for raw_attribute in raw_attributes.split(","):
            key, attribute_separator, value = raw_attribute.partition("=")

            if attribute_separator:
                attributes[key] = unquote(value)

        mounted_server = attributes.get("server", "")
        mounted_share = attributes.get("share", "")

        if (
            mounted_server.casefold() == parsed_uri.hostname.casefold()
            and mounted_share.casefold() == share_name.casefold()
        ):
            return mount_path.joinpath(*path_parts[1:])

    return None


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
