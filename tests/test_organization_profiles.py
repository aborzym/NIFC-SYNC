import unittest

from core.organization_profiles import (
    get_organization_profile,
    list_organization_profiles,
)


class OrganizationProfilesTest(unittest.TestCase):
    def test_lists_builtin_profiles(self):
        profiles = list_organization_profiles()

        self.assertEqual(
            tuple(profile.profile_id for profile in profiles),
            (
                "andrzej-borzym",
                "marta-lawrence",
                "andrzej-kubiczek",
            ),
        )
        self.assertEqual(
            tuple(profile.display_name for profile in profiles),
            (
                "Andrzej Borzym",
                "Marta Lawrence",
                "Andrzej Kubiczek",
            ),
        )

    def test_resolves_legacy_profile_alias(self):
        profile = get_organization_profile("legacy-v3")

        self.assertEqual(
            profile.profile_id,
            "andrzej-borzym",
        )

    def test_rejects_unknown_profile(self):
        with self.assertRaisesRegex(
            ValueError,
            "Nieznany profil",
        ):
            get_organization_profile("profil-z-kosmosu")


if __name__ == "__main__":
    unittest.main()
