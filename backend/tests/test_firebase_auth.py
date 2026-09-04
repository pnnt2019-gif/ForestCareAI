import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from routes.auth import verify_firebase_token


class FirebaseTokenVerificationTests(unittest.TestCase):
    def test_verify_firebase_token_without_token_returns_none(self):
        self.assertIsNone(verify_firebase_token(""))

    def test_verify_firebase_token_without_firebase_config_returns_none(self):
        self.assertIsNone(verify_firebase_token("mock-token"))


if __name__ == "__main__":
    unittest.main()
