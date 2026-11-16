"""Write a listing draft from one JSON file. Idempotent: run it again to change the draft.

{
  "bundle_id": "com.example.thing", "locale": "en-US",
  "version": {"copyright": "2026 Your Name"},
  "localization": {"description": "...", "keywords": "a,b", "promotionalText": "...",
                   "supportUrl": "https://...", "marketingUrl": "https://...", "whatsNew": "..."},
  "info": {"name": "...", "subtitle": "...", "privacyPolicyUrl": "https://..."},
  "build": "latest",                      # or a build number string
  "screenshots": {"APP_IPHONE_69": ["/path/1.png", ...]},
  "review": {"contactFirstName": "...", "contactLastName": "...", "contactEmail": "...",
             "contactPhone": "...", "demoAccountRequired": false, "notes": "..."}
}
"""
from __future__ import annotations

import json
import pathlib

import urllib.request

from .client import AscError, Client, md5

LIMITS = {"description": 4000, "keywords": 100, "promotionalText": 170, "whatsNew": 4000,
          "name": 30, "subtitle": 30}


def check(spec: dict) -> list[str]:
    problems = []
    for block in ("localization", "info"):
        for k, v in spec.get(block, {}).items():
            if k in LIMITS and len(v) > LIMITS[k]:
                problems.append(f"{k} is {len(v)} characters, limit {LIMITS[k]}")
            if "—" in str(v):
                problems.append(f"{k} contains an em dash")
    return problems


def _upsert_loc(c: Client, parent: str, kind: str, rel: str, locale: str, attrs: dict) -> str:
    items = c.get(f"/v1/{parent}/{kind}")["data"]
    found = next((i for i in items if i["attributes"]["locale"] == locale), None)
    if found:
        c.write("PATCH", f"/v1/{kind}/{found['id']}",
                {"data": {"type": kind, "id": found["id"], "attributes": attrs}})
        return found["id"]
    parent_type = "appStoreVersions" if rel == "appStoreVersion" else "appInfos"
    r = c.write("POST", f"/v1/{kind}", {"data": {"type": kind, "attributes": {"locale": locale, **attrs},
                "relationships": {rel: {"data": {"type": parent_type, "id": parent.split("/")[-1]}}}}})
    return r["data"]["id"]


def _screens(c: Client, loc_id: str, display: str, files: list[str]) -> None:
    sets = c.get(f"/v1/appStoreVersionLocalizations/{loc_id}/appScreenshotSets")["data"]
    s = next((x for x in sets if x["attributes"]["screenshotDisplayType"] == display), None)
    if s is None:
        s = c.write("POST", "/v1/appScreenshotSets", {"data": {"type": "appScreenshotSets",
                    "attributes": {"screenshotDisplayType": display}, "relationships": {
                    "appStoreVersionLocalization": {"data": {"type": "appStoreVersionLocalizations",
                                                             "id": loc_id}}}}})["data"]
    for old in c.get(f"/v1/appScreenshotSets/{s['id']}/appScreenshots")["data"]:
        c.write("DELETE", f"/v1/appScreenshots/{old['id']}")
    for f in files:
        p = pathlib.Path(f)
        made = c.write("POST", "/v1/appScreenshots", {"data": {"type": "appScreenshots",
                       "attributes": {"fileName": p.name, "fileSize": p.stat().st_size},
                       "relationships": {"appScreenshotSet": {"data": {"type": "appScreenshotSets",
                                                                       "id": s["id"]}}}}})["data"]
        blob = p.read_bytes()
        for op in made["attributes"]["uploadOperations"]:
            req = urllib.request.Request(op["url"], data=blob[op["offset"]:op["offset"] + op["length"]],
                                         method=op["method"],
                                         headers={h["name"]: h["value"] for h in op["requestHeaders"]})
            urllib.request.urlopen(req, timeout=120).read()
        c.write("PATCH", f"/v1/appScreenshots/{made['id']}", {"data": {"type": "appScreenshots",
                "id": made["id"], "attributes": {"uploaded": True, "sourceFileChecksum": md5(p)}}})


def apply(spec: dict, client: Client | None = None) -> list[str]:
    problems = check(spec)
    if problems:
        raise AscError("; ".join(problems))
    c = client or Client()
    done = []
    app = c.app(spec["bundle_id"]); version = c.editable_version(app["id"])
    locale = spec.get("locale", "en-US")
    if spec.get("version"):
        c.write("PATCH", f"/v1/appStoreVersions/{version['id']}", {"data": {"type": "appStoreVersions",
                "id": version["id"], "attributes": spec["version"]}}); done.append("version")
    loc_id = None
    if spec.get("localization"):
        loc_id = _upsert_loc(c, f"appStoreVersions/{version['id']}", "appStoreVersionLocalizations",
                             "appStoreVersion", locale, spec["localization"]); done.append("localization")
    if spec.get("info"):
        info = c.get(f"/v1/apps/{app['id']}/appInfos")["data"][0]
        _upsert_loc(c, f"appInfos/{info['id']}", "appInfoLocalizations", "appInfo", locale,
                    spec["info"]); done.append("info")
    if spec.get("build"):
        builds = c.builds(app["id"])
        pick = builds[0] if spec["build"] == "latest" else next(
            (b for b in builds if b["attributes"]["version"] == str(spec["build"])), None)
        if pick is None or pick["attributes"]["processingState"] != "VALID":
            raise AscError("that build is missing or not finished processing")
        c.write("PATCH", f"/v1/appStoreVersions/{version['id']}/relationships/build",
                {"data": {"type": "builds", "id": pick["id"]}}); done.append("build")
    if spec.get("screenshots"):
        if loc_id is None:
            loc_id = c.get(f"/v1/appStoreVersions/{version['id']}/appStoreVersionLocalizations")["data"][0]["id"]
        for display, files in spec["screenshots"].items():
            _screens(c, loc_id, display, files); done.append(f"screenshots {display}")
    if spec.get("review"):
        r = spec["review"]
        existing = c.get(f"/v1/appStoreVersions/{version['id']}/appStoreReviewDetail").get("data")
        if existing:
            c.write("PATCH", f"/v1/appStoreReviewDetails/{existing['id']}", {"data": {
                    "type": "appStoreReviewDetails", "id": existing["id"], "attributes": r}})
        else:
            c.write("POST", "/v1/appStoreReviewDetails", {"data": {"type": "appStoreReviewDetails",
                    "attributes": r, "relationships": {"appStoreVersion": {"data": {
                    "type": "appStoreVersions", "id": version["id"]}}}}})
        done.append("review details")
    return done
