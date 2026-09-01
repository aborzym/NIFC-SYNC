from core.scans import (
    extract_scan_url,
    get_scan_group_key,
    normalize_scan_url,
)


ALLOWED_WORKFLOWS = (
    "XML",
    "KRN-diplomatic",
    "KRN-modern",
)


def get_available_workflows(data):
    return [
        workflow
        for workflow in data["workflows"]
        if workflow["name"] in ALLOWED_WORKFLOWS
    ]


def build_scan_indexes(workflows):
    scan_urls_by_group = {}
    scan_sources_by_url = {}

    for workflow in workflows:
        for api_file in workflow["files"]:
            scan_url = extract_scan_url(api_file)

            if not scan_url:
                continue

            group_key = get_scan_group_key(api_file["name"])
            normalized_url = normalize_scan_url(scan_url)

            scan_urls_by_group.setdefault(
                group_key,
                set(),
            ).add(normalized_url)

            source = scan_sources_by_url.setdefault(
                normalized_url,
                {
                    "url": scan_url,
                    "groups": set(),
                },
            )

            source["groups"].add(group_key)

    return scan_urls_by_group, scan_sources_by_url
