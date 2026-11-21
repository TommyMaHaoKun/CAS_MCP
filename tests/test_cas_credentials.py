"""Exercise multiple local CAS logins with an in-memory credential store."""

import os
import unittest
from unittest.mock import patch

from cas_credentials import save_credentials, school_credentials


class CredentialProfileTests(unittest.TestCase):
    def test_named_profiles_have_independent_logins_and_no_inherited_fallback(self):
        vault = {}
        with (
            patch.dict(os.environ, {"CAS_MONSTER_USERNAME": "default-user", "CAS_MONSTER_PASSWORD": "env-password"}),
            patch("cas_credentials.keyring.get_password", side_effect=lambda service, entry: vault.get((service, entry))),
            patch("cas_credentials.keyring.set_password", side_effect=lambda service, entry, value: vault.update({
                (service, entry): value,
            })),
        ):
            self.assertEqual(school_credentials(), ("default-user", "env-password"))
            with self.assertRaisesRegex(ValueError, "student.*has no school login"):
                school_credentials(profile="student")

            save_credentials("student-one", "password-one", profile="STUDENT")
            save_credentials("student-two", "password-two", profile="student-two")
            self.assertEqual(school_credentials(profile="student"), ("student-one", "password-one"))
            self.assertEqual(school_credentials(profile="student-two"), ("student-two", "password-two"))
            self.assertEqual(school_credentials(), ("default-user", "env-password"))
