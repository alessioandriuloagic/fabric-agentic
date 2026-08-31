import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from fabric_agentic.github_app_auth import (
    GitHubAppAuthError,
    create_app_jwt,
    create_installation_token,
    load_private_key,
)


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None

    def read(self, *_):
        return json.dumps(self.payload).encode("utf-8")


class GitHubAppAuthTests(unittest.TestCase):
    def test_rejects_a_too_small_pem_without_reading_it(self) -> None:
        with TemporaryDirectory() as directory:
            key_path = Path(directory) / "key.pem"
            key_path.write_text("too-small", encoding="utf-8")

            with self.assertRaisesRegex(GitHubAppAuthError, "too small"):
                load_private_key(key_path)

    @patch("fabric_agentic.github_app_auth.jwt.encode", return_value="app-jwt")
    def test_creates_a_short_lived_app_jwt(self, encode_mock) -> None:
        self.assertEqual(create_app_jwt("4672750", "private-key", now=1000), "app-jwt")
        claims = encode_mock.call_args.args[0]
        self.assertEqual(claims, {"iat": 940, "exp": 1540, "iss": "4672750"})

    @patch("fabric_agentic.github_app_auth.load_private_key", return_value="private-key")
    @patch("fabric_agentic.github_app_auth.create_app_jwt", return_value="app-jwt")
    def test_returns_token_without_printing_it(self, _, __) -> None:
        requests = []

        def opener(request):
            requests.append(request)
            return FakeResponse({"token": "installation-token", "expires_at": "2026-08-21T15:00:00Z"})

        result = create_installation_token("4672750", "155470382", Path("unused"), opener)

        self.assertEqual(result.token, "installation-token")
        self.assertEqual(result.expires_at, "2026-08-21T15:00:00Z")
        self.assertEqual(requests[0].method, "POST")
        self.assertIn("/app/installations/155470382/access_tokens", requests[0].full_url)


if __name__ == "__main__":
    unittest.main()