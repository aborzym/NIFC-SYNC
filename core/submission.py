import os
from dataclasses import dataclass
from pathlib import Path

from core.destinations import resolve_asset_root


@dataclass(frozen=True)
class SubmissionInspection:
    actual_filename: str
    segment_name: str | None
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class ConfiguredSubmissionSearch:
    search_root: Path | None
    matches: tuple[Path, ...]


def inspect_submission_file(
    workflow_name,
    expected_filename,
    file_path,
):
    file_path = Path(file_path)

    if not file_path.is_file():
        raise FileNotFoundError(file_path)

    if workflow_name not in (
        "KRN-diplomatic",
        "KRN-modern",
        "XML",
    ):
        raise ValueError(f"Nieznany workflow: {workflow_name}")

    warnings = []

    if file_path.name != expected_filename:
        warnings.append(
            "Nazwa pliku lokalnego nie zgadza się "
            "z nazwą w workflow: "
            f"{file_path.name} != {expected_filename}."
        )

    segment_name = None

    if workflow_name.startswith("KRN-"):
        content = file_path.read_text(encoding="utf-8")

        for line in content.splitlines():
            if line.startswith("!!!!SEGMENT:"):
                value = line.removeprefix("!!!!SEGMENT:").strip()
                segment_name = value or None
                break

        if segment_name is None:
            warnings.append("W pliku KRN brak !!!!SEGMENT:.")
        elif segment_name != expected_filename:
            warnings.append(
                "Wartość !!!!SEGMENT: nie zgadza się "
                "z nazwą w workflow: "
                f"{segment_name} != {expected_filename}."
            )

    return SubmissionInspection(
        actual_filename=file_path.name,
        segment_name=segment_name,
        warnings=tuple(warnings),
    )


def find_submission_files(
    search_root,
    expected_filename,
):
    if not isinstance(expected_filename, str):
        raise TypeError("Nazwa pliku musi być typu str.")

    safe_filename = Path(expected_filename).name

    if (
        not expected_filename
        or safe_filename != expected_filename
        or safe_filename in (".", "..")
    ):
        raise ValueError("Nieprawidłowa nazwa pliku.")

    search_root = Path(search_root)

    if not search_root.is_dir():
        return ()

    matches = []

    for current_root, directory_names, filenames in os.walk(search_root):
        directory_names[:] = [
            name
            for name in directory_names
            if (name.casefold() != "skany" and not name.startswith(".skany_tmp_"))
        ]

        if expected_filename not in filenames:
            continue

        candidate = Path(current_root) / expected_filename

        if candidate.is_file():
            matches.append(candidate)

    return tuple(
        sorted(
            matches,
            key=lambda path: str(path).casefold(),
        )
    )


def find_configured_submission_files(
    configuration,
    workflow_name,
    expected_filename,
    year=None,
):
    search_root = resolve_asset_root(
        configuration,
        expected_filename,
        "transcriptions",
        workflow_name=workflow_name,
        year=year,
    )

    if search_root is None:
        return ConfiguredSubmissionSearch(
            search_root=None,
            matches=(),
        )

    search_root = Path(search_root)

    return ConfiguredSubmissionSearch(
        search_root=search_root,
        matches=find_submission_files(
            search_root,
            expected_filename,
        ),
    )
