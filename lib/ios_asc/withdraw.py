"""Withdraw one queued app version through an approved red action."""
from .client import AscError


def queued(c, payload):
    if set(payload) != {"app_id", "version_id", "submission_id", "build_id"}:
        raise ValueError("withdraw-review needs the exact app, version, submission and build IDs")
    if any(not isinstance(v, str) or not v or "/" in v or "?" in v for v in payload.values()):
        raise ValueError("invalid App Store resource ID")
    app, version, submission, build = (payload[k] for k in
                                     ("app_id", "version_id", "submission_id", "build_id"))
    a = c.get(f"/v1/apps/{app}")["data"]["attributes"]
    submissions = c.get(f"/v1/apps/{app}/reviewSubmissions?limit=200")["data"]
    sub = next((s for s in submissions if s["id"] == submission), None)
    if not sub or sub["attributes"]["state"] != "WAITING_FOR_REVIEW":
        raise AscError("the exact submission is no longer waiting for review for this app")
    items = c.get(f"/v1/reviewSubmissions/{submission}/items?include=appStoreVersion")["data"]
    if len(items) != 1 or items[0].get("relationships", {}).get("appStoreVersion", {}).get("data", {}).get("id") != version:
        raise AscError("withdrawal must contain only the exact approved app version")
    v = c.get(f"/v1/appStoreVersions/{version}")["data"]["attributes"]
    b = c.get(f"/v1/appStoreVersions/{version}/build").get("data")
    if v["appStoreState"] != "WAITING_FOR_REVIEW" or not b or b["id"] != build:
        raise AscError("the queued version or attached build changed; ask for fresh approval")
    return a, v, b["attributes"]


def render(c, payload):
    app, version, build = queued(c, payload)
    return (f"Withdraw this app from the App Store review queue?\n\n"
            f"App: {app['name']} ({app['bundleId']})\n"
            f"Version: {version['versionString']}\nBuild: {build['version']}\n"
            f"Submission: {payload['submission_id']}\n\n"
            "This removes only that waiting submission. Review restarts when it is "
            "resubmitted. The replacement build is submitted with a separate approval.")


def perform(c, payload):
    queued(c, payload)
    submission = payload["submission_id"]
    c.write("PATCH", f"/v1/reviewSubmissions/{submission}", {"data": {
        "type": "reviewSubmissions", "id": submission, "attributes": {"canceled": True}}})
    return ("Requested withdrawal of the approved waiting App Store submission",
            f"reviewSubmission {submission}")
