import copy
import pathlib
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
from ios_asc.client import Client, AscError
from ios_asc import withdraw

PAYLOAD = {"app_id": "app", "version_id": "version", "submission_id": "submission", "build_id": "build"}


class Offline(Client):
    def __init__(self):
        self.writes = []
        self.responses = {
            "/v1/apps/app": {"data": {"attributes": {"name": "Example", "bundleId": "com.example.app"}}},
            "/v1/apps/app/reviewSubmissions?limit=200": {"data": [{"id": "submission", "attributes": {"state": "WAITING_FOR_REVIEW"}}]},
            "/v1/reviewSubmissions/submission/items?include=appStoreVersion": {"data": [{"relationships": {"appStoreVersion": {"data": {"id": "version"}}}}]},
            "/v1/appStoreVersions/version": {"data": {"attributes": {"versionString": "1.1", "appStoreState": "WAITING_FOR_REVIEW"}}},
            "/v1/appStoreVersions/version/build": {"data": {"id": "build", "attributes": {"version": "17"}}},
        }

    def get(self, path):
        return copy.deepcopy(self.responses[path])

    def call(self, method, path, body=None):
        self.writes.append((method, path, body))
        return {}


class Withdrawal(unittest.TestCase):
    def test_direct_write_is_blocked(self):
        c = Offline()
        with self.assertRaises(AscError):
            withdraw.perform(c, PAYLOAD)
        self.assertEqual(c.writes, [])

    def test_approved_action_cancels_only_bound_submission(self):
        c = Offline()
        with patch("herald.red.acting", return_value=123):
            withdraw.perform(c, PAYLOAD)
        self.assertEqual(c.writes, [("PATCH", "/v1/reviewSubmissions/submission", {"data": {
            "type": "reviewSubmissions", "id": "submission", "attributes": {"canceled": True}}})])

    def test_changed_build_is_refused(self):
        c = Offline()
        c.responses["/v1/appStoreVersions/version/build"]["data"]["id"] = "other"
        with self.assertRaises(AscError):
            withdraw.perform(c, PAYLOAD)
        self.assertEqual(c.writes, [])

    def test_review_started_is_refused(self):
        c = Offline()
        c.responses["/v1/apps/app/reviewSubmissions?limit=200"]["data"][0]["attributes"]["state"] = "IN_REVIEW"
        with self.assertRaises(AscError):
            withdraw.render(c, PAYLOAD)

    def test_extra_items_are_refused(self):
        c = Offline()
        items = c.responses["/v1/reviewSubmissions/submission/items?include=appStoreVersion"]["data"]
        items.append(copy.deepcopy(items[0]))
        with self.assertRaises(AscError):
            withdraw.render(c, PAYLOAD)

    def test_foreign_submission_is_refused(self):
        c = Offline()
        c.responses["/v1/apps/app/reviewSubmissions?limit=200"]["data"] = []
        with self.assertRaises(AscError):
            withdraw.render(c, PAYLOAD)

    def test_tap_identifies_the_actual_app_and_build(self):
        text = withdraw.render(Offline(), PAYLOAD)
        self.assertIn("Example (com.example.app)", text)
        self.assertIn("Build: 17", text)
        self.assertIn("Submission: submission", text)


if __name__ == "__main__":
    unittest.main()
