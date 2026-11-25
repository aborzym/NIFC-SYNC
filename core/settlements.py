import re

from pypdf import PdfReader

ROW_PATTERN = re.compile(
    r"^\s*(\d+)\s+(KRN-diplomatic|KRN-modern|XML)\s+"
    r"(.+?)\s+(-?\d+)\s*$"
)


def parse_settlement_text(text):
    totals = re.findall(
        r"łączna liczba znaków:\s*(-?[0-9][0-9 \u00a0]*)",
        text,
        flags=re.IGNORECASE,
    )
    if len(totals) != 1:
        raise ValueError("Nie znaleziono jednoznacznej sumy znaków w PDF-ie.")

    declared_total = int("".join(totals[0].split()))
    performer = re.search(r"Wykonawca:\s*([^\r\n]+)", text)
    if performer is None:
        raise ValueError("Nie znaleziono wykonawcy w PDF-ie.")

    performer_name = re.split(r"\s{2,}", performer.group(1).strip())[0]
    entries = []

    for line in text.splitlines():
        match = ROW_PATTERN.fullmatch(line)
        if match:
            tranche, scheme, filename, count = match.groups()
            entries.append(
                {
                    "tranche": int(tranche),
                    "scheme": scheme,
                    "file_name": filename.strip(),
                    "note_count": int(count),
                }
            )
        elif re.match(r"^\s*\d+\s+(?:KRN-|XML\b)", line):
            raise ValueError(f"Nie udało się odczytać pozycji: {line.strip()}")

    if not entries:
        raise ValueError("Nie znaleziono pozycji rozliczenia.")

    calculated_total = sum(item["note_count"] for item in entries)
    if calculated_total != declared_total:
        raise ValueError(
            f"Suma pozycji ({calculated_total}) różni się od sumy "
            f"w dokumencie ({declared_total}). Import przerwany."
        )

    return {
        "performer": performer_name,
        "total": declared_total,
        "entries": entries,
    }


def read_settlement_pdf(path):
    reader = PdfReader(path)
    text = "\n".join(
        page.extract_text(extraction_mode="layout") or "" for page in reader.pages
    )
    return parse_settlement_text(text)


def _comparison_filename(item):
    name = item["file_name"]
    if item["scheme"] == "KRN-modern" and name.endswith(".krn-modern"):
        return name.removesuffix("-modern")
    return name


def _compare_exact_statistics(entries, paid_entries):
    statistics = {}
    settlements = {}

    for item in entries:
        key = (item["scheme"], _comparison_filename(item))
        statistics.setdefault(key, []).append(item)

    for item in paid_entries:
        key = (item["scheme"], _comparison_filename(item))
        settlements.setdefault(key, []).append(item)

    paid = []
    unpaid = []
    unresolved = []
    outside = []

    for key, items in statistics.items():
        matches = settlements.get(key, [])

        if not matches:
            unpaid.extend(items)
        elif len(items) == 1 and len(matches) == 1:
            if items[0]["note_count"] == matches[0]["note_count"]:
                paid.extend(items)
            else:
                # Jednoznaczna para z różną liczbą znaków:
                # przekaż ją do ręcznego rozstrzygnięcia.
                unpaid.extend(items)
                outside.extend(matches)
        elif len(items) == 1:
            # Kilka pozycji PDF dla jednej pozycji NIFC:
            # zapisane zatwierdzenie wskaże właściwą parę.
            unpaid.extend(items)
            outside.extend(matches)
        else:
            unresolved.extend(items)

    outside.extend(
        item
        for key, items in settlements.items()
        if key not in statistics
        for item in items
    )

    return {
        "paid": tuple(paid),
        "unpaid": tuple(unpaid),
        "unresolved": tuple(unresolved),
        "outside": tuple(outside),
        "paid_total": sum(item["note_count"] for item in paid),
        "unpaid_total": sum(item["note_count"] for item in unpaid),
        "unresolved_total": sum(item["note_count"] for item in unresolved),
    }


def _matching_filename(item):
    name = item["file_name"].removeprefix("***").strip()
    return name.removesuffix(".musicxml")


def compare_statistics(entries, paid_entries, approved=(), accepted_revisions=()):
    regular_entries = tuple(item for item in entries if item["note_count"] >= 0)
    result = _compare_exact_statistics(regular_entries, paid_entries)
    paid = list(result["paid"])
    unpaid = list(result["unpaid"])
    unresolved = list(result["unresolved"])
    outside = list(result["outside"])
    differences = []
    approved_differences = []

    for item in tuple(unpaid):
        name = _matching_filename(item)
        candidates = [other for other in outside if _matching_filename(other) == name]
        statistics_candidates = [
            other for other in unpaid if _matching_filename(other) == name
        ]
        if not candidates:
            continue

        if len(statistics_candidates) != 1:
            unpaid.remove(item)
            unresolved.append(item)
            continue

        if len(candidates) == 1:
            other = candidates[0]
        else:
            chosen = [
                candidate
                for candidate in candidates
                if (
                    item["scheme"],
                    item["file_name"],
                    item["submission_time"],
                    item["note_count"],
                    candidate["scheme"],
                    candidate["file_name"],
                    candidate["note_count"],
                )
                in approved
            ]
            if len(chosen) != 1:
                unpaid.remove(item)
                unresolved.append(item)
                continue
            other = chosen[0]

        identity = (
            item["scheme"],
            item["file_name"],
            item["submission_time"],
            item["note_count"],
            other["scheme"],
            other["file_name"],
            other["note_count"],
        )
        unpaid.remove(item)
        outside.remove(other)

        if identity in approved:
            paid.append(item)
            if item["note_count"] != other["note_count"]:
                approved_differences.append(
                    {
                        "identity": identity,
                        "statistics": item,
                        "settlement": other,
                        "difference": item["note_count"] - other["note_count"],
                    }
                )
        else:
            unresolved.append(item)
            differences.append(
                {
                    "identity": identity,
                    "statistics": item,
                    "settlement": other,
                }
            )

    corrections = [item for item in entries if item["note_count"] < 0]
    pending_corrections = []
    settled_corrections = []

    for correction in corrections:
        matches = [
            item
            for item in outside
            if item["scheme"] == correction["scheme"]
            and _comparison_filename(item) == _comparison_filename(correction)
            and item["note_count"] == correction["note_count"]
        ]
        duplicates = [
            item
            for item in corrections
            if item["scheme"] == correction["scheme"]
            and _comparison_filename(item) == _comparison_filename(correction)
            and item["note_count"] == correction["note_count"]
        ]

        if len(matches) == 1 and len(duplicates) == 1:
            outside.remove(matches[0])
            settled_corrections.append(correction)
        else:
            pending_corrections.append(correction)
    implicit_corrections = []
    linked_differences = []
    for difference in approved_differences:
        if difference["difference"] <= 0:
            continue

        score = difference["statistics"]
        project_id = score["file_name"].split("_", 1)[0]
        matching = [
            correction
            for correction in pending_corrections
            if correction["scheme"] == score["scheme"]
            and correction["note_count"] == -difference["difference"]
            and f"-{project_id}-" in correction["file_name"]
        ]
        competing = [
            other
            for other in approved_differences
            if other["statistics"]["scheme"] == score["scheme"]
            and other["statistics"]["file_name"].split("_", 1)[0] == project_id
            and other["difference"] == difference["difference"]
        ]
        if len(matching) == 1 and len(competing) == 1:
            correction = matching[0]
            pending_corrections.remove(correction)
            settled_corrections.append(correction)
            implicit_corrections.append(correction)
            linked_differences.append(difference["identity"])

    gross_shortfall = sum(max(0, item["difference"]) for item in approved_differences)
    shortfall = sum(
        max(0, item["difference"])
        for item in approved_differences
        if item["identity"] not in linked_differences
    )
    overpayment = sum(max(0, -item["difference"]) for item in approved_differences)
    accepted_revision_ids = set(accepted_revisions)
    accepted_revision_entries = [
        item
        for item in outside
        if item.get("_pdf_id") in accepted_revision_ids
        and ".krn-revision" in item["file_name"].casefold()
    ]
    outside = [item for item in outside if item not in accepted_revision_entries]
    accepted_revision_total = sum(
        item["note_count"] for item in accepted_revision_entries
    )
    return {
        "paid": tuple(paid),
        "unpaid": tuple(unpaid),
        "unresolved": tuple(unresolved),
        "outside": tuple(outside),
        "accepted_revisions": tuple(accepted_revision_entries),
        "accepted_revision_total": accepted_revision_total,
        "differences": tuple(differences),
        "approved_differences": tuple(approved_differences),
        "paid_total": (
            sum(item["note_count"] for item in paid)
            - gross_shortfall
            + overpayment
            + accepted_revision_total
        ),
        "shortfall_total": shortfall,
        "implicit_corrections": tuple(implicit_corrections),
        "overpayment_total": overpayment,
        "pending_corrections": tuple(pending_corrections),
        "settled_corrections": tuple(settled_corrections),
        "unpaid_total": (
            sum(item["note_count"] for item in unpaid)
            + sum(item["note_count"] for item in pending_corrections)
            + shortfall
        ),
        "unresolved_total": sum(item["note_count"] for item in unresolved),
    }
