from dataclasses import dataclass
from typing import Literal

LayoutKind = Literal[
    "work-folders",
    "library-split",
    "workflow-status",
]


@dataclass(frozen=True)
class OrganizationProfile:
    profile_id: str
    display_name: str
    layout_kind: LayoutKind
    description: str


ORGANIZATION_PROFILES = (
    OrganizationProfile(
        profile_id="andrzej-borzym",
        display_name="Andrzej Borzym",
        layout_kind="work-folders",
        description=(
            "Osobny folder dla każdego utworu, z transkrypcją i podfolderem skanów."
        ),
    ),
    OrganizationProfile(
        profile_id="marta-lawrence",
        display_name="Marta Lawrence",
        layout_kind="library-split",
        description=(
            "Pliki transkrypcji luzem według bibliotek; "
            "skany rozpakowywane do osobnych folderów "
            "pakietów."
        ),
    ),
    OrganizationProfile(
        profile_id="andrzej-kubiczek",
        display_name="Andrzej Kubiczek",
        layout_kind="workflow-status",
        description=(
            "Transkrypcje luzem i źródła w osobnych folderach "
            "pakietów, według workflow, w katalogu "
            "<rok>/in progress."
        ),
    ),
)

PROFILE_ALIASES = {
    "legacy-v3": "andrzej-borzym",
}


def normalize_organization_profile_id(profile_id):
    return PROFILE_ALIASES.get(
        profile_id,
        profile_id,
    )


def list_organization_profiles():
    return ORGANIZATION_PROFILES


def get_organization_profile(profile_id):
    profile_id = normalize_organization_profile_id(profile_id)
    for profile in ORGANIZATION_PROFILES:
        if profile.profile_id == profile_id:
            return profile

    raise ValueError(f"Nieznany profil organizacji plików: {profile_id}")
