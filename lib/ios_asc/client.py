"""App Store Connect transport. Reads are open. Writes are split by who may make them.

Draft metadata (descriptions, keywords, screenshots, attaching a build) only changes
what sits in the user's own App Store Connect page, and they can edit or clear it, so a
session may write it. Anything that sends the app to Apple's review queue goes
through the `ios.submit-review` red action and `red.acting()` is checked here.
"""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import time
import urllib.error
import urllib.request

import jwt

API = "https://api.appstoreconnect.apple.com"
HOME = pathlib.Path(os.environ.get("HERALD_HOME", pathlib.Path.home() / ".herald"))

#: What a session may create or change without a tap. Never anything under reviewSubmissions.
DRAFT_WRITES = ("appStoreVersionLocalizations", "appInfoLocalizations", "appStoreVersions",
                "appScreenshotSets", "appScreenshots", "appStoreReviewDetails",
                "ageRatingDeclarations")
RED_WRITES = ("reviewSubmissions", "reviewSubmissionItems")


class AscError(RuntimeError):
    pass


class Client:
    def __init__(self):
        s = json.loads((HOME / "secrets.json").read_text())["appstore"]
        self.key_id, self.issuer = s["key_id"], s["issuer_id"]
        self.key = pathlib.Path(os.path.expanduser(s["key_path"])).read_text()

    def token(self) -> str:
        now = int(time.time())
        return jwt.encode({"iss": self.issuer, "iat": now, "exp": now + 900,
                           "aud": "appstoreconnect-v1"}, self.key, algorithm="ES256",
                          headers={"kid": self.key_id, "typ": "JWT"})

    def call(self, method: str, path: str, body: dict | None = None) -> dict:
        url = path if path.startswith("http") else f"{API}{path}"
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method, headers={
            "Authorization": f"Bearer {self.token()}", "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                raw = r.read()
        except urllib.error.HTTPError as e:
            raise AscError(f"{method} {path}: {e.code} {e.read().decode()[:600]}") from None
        return json.loads(raw) if raw else {}

    def get(self, path: str) -> dict:
        return self.call("GET", path)

    def resource(self, path: str) -> str:
        """First path segment after /v1/, the resource type a write targets."""
        return path.split("?")[0].split("/v1/", 1)[-1].lstrip("/").split("/")[0]

    def write(self, method: str, path: str, body: dict | None = None) -> dict:
        kind = self.resource(path)
        if kind in RED_WRITES:
            from herald import red
            if red.acting() is None:
                raise AscError(f"{kind} is only written by an approved ios.submit-review")
        elif kind not in DRAFT_WRITES:
            raise AscError(f"writes to {kind} are not allowed here")
        elif method == "DELETE" and kind != "appScreenshots":
            raise AscError("only draft screenshots may be deleted")
        return self.call(method, path, body)

    # -- lookups ---------------------------------------------------------
    def app(self, bundle_id: str) -> dict:
        d = self.get(f"/v1/apps?filter[bundleId]={bundle_id}")["data"]
        if not d:
            raise AscError(f"no app record for {bundle_id}; create it in App Store Connect first")
        return d[0]

    def editable_version(self, app_id: str) -> dict:
        states = "PREPARE_FOR_SUBMISSION,DEVELOPER_REJECTED,REJECTED,METADATA_REJECTED,INVALID_BINARY"
        d = self.get(f"/v1/apps/{app_id}/appStoreVersions?filter[appStoreState]={states}&limit=5")["data"]
        if not d:
            raise AscError("no editable version; add a new version in App Store Connect")
        return d[0]

    def builds(self, app_id: str) -> list[dict]:
        return self.get(f"/v1/builds?filter[app]={app_id}&sort=-uploadedDate&limit=10")["data"]


def md5(path: pathlib.Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()
