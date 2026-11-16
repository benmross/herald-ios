"""What Apple's review queue would receive, and the submission itself."""
from __future__ import annotations

from .client import AscError, Client


def readiness(c: Client, app_id: str, version_id: str) -> tuple[list[str], list[str]]:
    """Returns (what the tap screen shows, blocking problems)."""
    app = c.get(f"/v1/apps/{app_id}")["data"]["attributes"]
    v = c.get(f"/v1/appStoreVersions/{version_id}")["data"]["attributes"]
    lines = [f"App: {app['name']} ({app['bundleId']})", f"Version: {v['versionString']}  state: {v['appStoreState']}"]
    problems = []
    if v["appStoreState"] not in ("PREPARE_FOR_SUBMISSION", "DEVELOPER_REJECTED", "REJECTED",
                                  "METADATA_REJECTED", "INVALID_BINARY"):
        problems.append(f"this version is {v['appStoreState']}, not editable")
    b = c.get(f"/v1/appStoreVersions/{version_id}/build").get("data")
    if not b:
        problems.append("no build is attached")
    else:
        ba = b["attributes"]
        lines.append(f"Build: {ba['version']}  processing: {ba['processingState']}")
        if ba["processingState"] != "VALID":
            problems.append("the attached build has not finished processing")
    locs = c.get(f"/v1/appStoreVersions/{version_id}/appStoreVersionLocalizations")["data"]
    if not locs:
        problems.append("no store listing text")
    for loc in locs:
        a = loc["attributes"]; tag = a["locale"]
        lines.append(f"{tag}: description {len(a.get('description') or '')} chars, "
                     f"keywords {len(a.get('keywords') or '')}, support {a.get('supportUrl') or 'none'}")
        for need in ("description", "keywords", "supportUrl"):
            if not a.get(need):
                problems.append(f"{tag} is missing {need}")
        sets = c.get(f"/v1/appStoreVersionLocalizations/{loc['id']}/appScreenshotSets")["data"]
        n = sum(len(c.get(f"/v1/appScreenshotSets/{s['id']}/appScreenshots")["data"]) for s in sets)
        lines.append(f"{tag}: {n} screenshots in {len(sets)} sets")
        if n == 0:
            problems.append(f"{tag} has no screenshots")
    info = c.get(f"/v1/apps/{app_id}/appInfos")["data"]
    for i in info:
        for loc in c.get(f"/v1/appInfos/{i['id']}/appInfoLocalizations")["data"]:
            a = loc["attributes"]
            lines.append(f"{a['locale']}: name {a.get('name')!r}, subtitle {a.get('subtitle')!r}, "
                         f"privacy policy {a.get('privacyPolicyUrl') or 'none'}")
            if not a.get("privacyPolicyUrl"):
                problems.append(f"{a['locale']} has no privacy policy URL")
    d = c.get(f"/v1/appStoreVersions/{version_id}/appStoreReviewDetail").get("data")
    if not d:
        problems.append("no App Review contact details")
    return lines, problems


def submit(c: Client, app_id: str, version_id: str) -> str:
    sub = c.write("POST", "/v1/reviewSubmissions", {"data": {"type": "reviewSubmissions",
                  "attributes": {"platform": "IOS"}, "relationships": {"app": {"data": {
                  "type": "apps", "id": app_id}}}}})["data"]
    c.write("POST", "/v1/reviewSubmissionItems", {"data": {"type": "reviewSubmissionItems",
            "relationships": {"reviewSubmission": {"data": {"type": "reviewSubmissions", "id": sub["id"]}},
                              "appStoreVersion": {"data": {"type": "appStoreVersions", "id": version_id}}}}})
    c.write("PATCH", f"/v1/reviewSubmissions/{sub['id']}", {"data": {"type": "reviewSubmissions",
            "id": sub["id"], "attributes": {"submitted": True}}})
    return sub["id"]
