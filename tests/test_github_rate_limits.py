# SPDX-FileCopyrightText: 2026 Carlos Garcia (BananaNanners) and NAnnersVRhub contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Dev3 follow-up: GitHub rate-limit handling, cache, error integrity."""
import io
import json
import urllib.error
import unittest
from unittest import mock

from vrhub import updates


class GithubQuotaTests(unittest.TestCase):
    def setUp(self):
        saved_cache = dict(updates._github_recent)
        saved_limit = updates._github_retry_after
        updates._github_recent.clear()
        updates._github_retry_after = 0.0
        self.addCleanup(lambda: updates._github_recent.clear())
        self.addCleanup(lambda: updates._github_recent.update(saved_cache))
        self.addCleanup(lambda: setattr(updates, "_github_retry_after", saved_limit))

    @staticmethod
    def reply(tag="v1.2.3"):
        body = json.dumps({
            "tag_name": tag,
            "published_at": "2026-11-17T10:00:00Z",
            "html_url": "https://github.com/test/org/releases/tag/" + tag,
        }).encode()
        return io.BytesIO(body)

    @staticmethod
    def limit_response(reset="1900"):
        return urllib.error.HTTPError(
            "https://api.github.com/repos/test/org/releases/latest",
            403, "rate limit exceeded",
            {"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": reset},
            None)

    def test_second_refresh_reuses_recent_release_without_second_request(self):
        with mock.patch.object(updates.urllib.request, "urlopen", side_effect=[
                self.reply("v1.2.3"), AssertionError("unnecessary repeat request")]) as fetch:
            with mock.patch.object(updates.time, "monotonic", return_value=100):
                first = updates.fetch_latest("test/org")
            with mock.patch.object(updates.time, "monotonic", return_value=200):
                second = updates.fetch_latest("test/org")
        self.assertEqual(fetch.call_count, 1)
        self.assertFalse(first["cached"])
        self.assertTrue(second["cached"])
        self.assertEqual(second["tag"], "v1.2.3")

    def test_cache_expires_after_fifteen_minutes(self):
        with mock.patch.object(updates.urllib.request, "urlopen",
                               side_effect=[self.reply("v1"), self.reply("v2")]) as fetch:
            with mock.patch.object(updates.time, "monotonic", return_value=100):
                a = updates.fetch_latest("test/org")
            with mock.patch.object(updates.time, "monotonic", return_value=100 + 901):
                b = updates.fetch_latest("test/org")
        self.assertEqual(fetch.call_count, 2)
        self.assertEqual((a["tag"], b["tag"]), ("v1", "v2"))
        self.assertFalse(b["cached"])

    def test_first_rate_limit_blocks_followup_requests_until_reset(self):
        with mock.patch.object(updates.time, "time", return_value=1000):
            with mock.patch.object(updates.urllib.request, "urlopen",
                                   side_effect=self.limit_response()) as fetch:
                with self.assertRaisesRegex(OSError, "rate limit reached"):
                    updates.fetch_latest("test/org")
                with self.assertRaisesRegex(OSError, "rate limit reached"):
                    updates.fetch_latest("different/repo")
                self.assertEqual(fetch.call_count, 1)
                self.assertGreaterEqual(updates._github_retry_after, 1900)

    def test_missing_reset_header_uses_short_cooldown(self):
        with mock.patch.object(updates.time, "time", return_value=1000):
            with mock.patch.object(updates.urllib.request, "urlopen",
                                   side_effect=self.limit_response(None)) as fetch:
                with self.assertRaises(OSError):
                    updates.fetch_latest("test/org")
                self.assertGreaterEqual(updates._github_retry_after, 1060)
                self.assertEqual(fetch.call_count, 1)

    def test_rate_limit_expiration_allows_new_request(self):
        with mock.patch.object(updates.urllib.request, "urlopen",
                               side_effect=[self.limit_response(), self.reply("v2")]) as fetch:
            with mock.patch.object(updates.time, "time", return_value=1000):
                with self.assertRaises(OSError):
                    updates.fetch_latest("test/org")
            with mock.patch.object(updates.time, "time", return_value=1901):
                result = updates.fetch_latest("test/org")
        self.assertEqual(result["tag"], "v2")
        self.assertEqual(fetch.call_count, 2)

    def test_unrelated_403_is_not_called_a_rate_limit(self):
        error = urllib.error.HTTPError(
            "https://api.github.com/repos/test/org/releases/latest",
            403, "Forbidden", {"X-RateLimit-Remaining": "45"}, None)
        with mock.patch.object(updates.urllib.request, "urlopen", side_effect=error):
            with self.assertRaisesRegex(OSError, "HTTP 403"):
                updates.fetch_latest("test/org")
        self.assertEqual(updates._github_retry_after, 0.0)

    def test_rate_limit_keeps_github_errors_explicit_and_nexus_independent(self):
        recipes = {
            "github-a": {"id": "github-a", "updates": [
                {"name": "A", "github": "test/org"}]},
            "github-b": {"id": "github-b", "updates": [
                {"name": "B", "github": "other/repo"}]},
            "nexus": {"id": "nexus", "updates": [
                {"name": "N", "nexus_game": "test", "nexus_mod": 1}]}
        }
        with mock.patch.object(updates.time, "time", return_value=1000):
            with mock.patch.object(updates.urllib.request, "urlopen",
                                   side_effect=self.limit_response()) as fetch:
                result = updates.check_all(
                    recipes, {},
                    nexus_fetch=lambda game, mod_id, key: {
                        "tag": "1.0", "published": "2026-11-17T10:00:00Z",
                        "url": "https://www.nexusmods.com/test/mods/1"},
                    nexus_key="mock-only")
        self.assertEqual(fetch.call_count, 1)
        self.assertEqual(result["github-a"][0]["status"], "error")
        self.assertEqual(result["github-b"][0]["status"], "error")
        self.assertIn("rate limit", result["github-b"][0]["detail"])
        self.assertEqual(result["nexus"][0]["status"], "not_installed")

    def test_cached_result_is_labeled_not_silent_freshness(self):
        recipe = {"id": "testgame", "updates": [
            {"name": "A", "github": "test/org"}]}
        with mock.patch.object(updates.urllib.request, "urlopen",
                               return_value=self.reply()):
            with mock.patch.object(updates.time, "monotonic", return_value=100):
                updates.check_recipe(recipe, {"testgame": {"installed_at": 0}})
            with mock.patch.object(updates.time, "monotonic", return_value=200):
                result = updates.check_recipe(
                    recipe, {"testgame": {"installed_at": 0}})
        self.assertEqual(result[0]["status"], "update")
        self.assertTrue(result[0]["cached"])
        self.assertIn("cached", result[0]["detail"])


if __name__ == "__main__":
    unittest.main()
