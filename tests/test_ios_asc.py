import pathlib, sys, unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
from ios_asc import client as cl, draft


class Offline(cl.Client):
    def __init__(self):
        self.calls = []

    def call(self, method, path, body=None):
        self.calls.append((method, path)); return {}


class WriteGate(unittest.TestCase):
    def test_review_submission_needs_an_approved_action(self):
        with self.assertRaises(cl.AscError):
            Offline().write("POST", "/v1/reviewSubmissions", {})

    def test_draft_metadata_is_allowed(self):
        c = Offline(); c.write("PATCH", "/v1/appStoreVersionLocalizations/1", {})
        self.assertEqual(c.calls, [("PATCH", "/v1/appStoreVersionLocalizations/1")])

    def test_unlisted_resources_and_deletes_are_refused(self):
        for m, p in (("POST", "/v1/apps"), ("DELETE", "/v1/appStoreVersions/1"), ("PATCH", "/v1/users/1")):
            with self.assertRaises(cl.AscError):
                Offline().write(m, p, {})


class ListingChecks(unittest.TestCase):
    def test_limits_and_em_dash(self):
        spec = {"localization": {"keywords": "x" * 101, "description": "a — b"}, "info": {"name": "n" * 31}}
        self.assertEqual(len(draft.check(spec)), 3)

    def test_clean_listing_passes(self):
        self.assertEqual(draft.check({"localization": {"keywords": "a,b"}, "info": {"name": "Thing"}}), [])


if __name__ == "__main__":
    unittest.main()
