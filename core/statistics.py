from datetime import date, datetime
from zoneinfo import ZoneInfo


def statistics_months(start_month, today=None):
    if not start_month:
        raise ValueError("Wybierz i zapisz miesiąc początkowy.")

    try:
        start = date.fromisoformat(start_month)
    except (TypeError, ValueError) as error:
        raise ValueError("Nieprawidłowy miesiąc początkowy.") from error

    today = today or datetime.now(ZoneInfo("Europe/Warsaw")).date()
    end = today.replace(day=1)
    if start > today:
        raise ValueError("Miesiąc początkowy nie może być w przyszłości.")

    months = []
    current = start.replace(day=1)
    while current <= end:
        months.append(current.isoformat())
        if current == end:
            break
        if current.month == 12:
            current = date(current.year + 1, 1, 1)
        else:
            current = date(current.year, current.month + 1, 1)

    return tuple(months)


def statistics_entries(monthly_data, start_date=None):
    cutoff = date.fromisoformat(start_date) if start_date else None
    entries = []
    for month, groups in monthly_data.items():
        if not isinstance(groups, list):
            raise TypeError(f"Nieprawidłowe statystyki za {month}.")

        for group in groups:
            if not isinstance(group, dict):
                raise TypeError("Nieprawidłowa grupa statystyk.")

            scheme = group.get("name")
            files = group.get("files")
            if not isinstance(scheme, str) or not scheme.strip():
                raise ValueError("Brak schematu transkrypcji.")
            if not isinstance(files, list):
                raise TypeError("Nieprawidłowa lista plików.")

            for item in files:
                if not isinstance(item, dict):
                    raise TypeError("Nieprawidłowa pozycja statystyk.")

                filename = item.get("file_name")
                submitted = item.get("submission_time")
                count = item.get("note_count")
                if not isinstance(filename, str) or not filename.strip():
                    raise ValueError("Brak nazwy pliku w statystykach.")
                if not isinstance(submitted, str) or not submitted:
                    raise ValueError(f"Brak daty dla {filename}.")
                if type(count) is not int:
                    raise TypeError(f"Nieprawidłowa liczba znaków: {filename}.")
                if count < 0:
                    raise ValueError(f"Ujemna liczba znaków: {filename}.")

                submitted_date = datetime.fromisoformat(submitted).date()
                if cutoff is not None and submitted_date < cutoff:
                    continue

                entries.append(
                    {
                        "month": month,
                        "scheme": scheme,
                        "file_name": filename,
                        "submission_time": submitted,
                        "note_count": count,
                    }
                )

    return tuple(entries)
