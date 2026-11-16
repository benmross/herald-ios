"""Sending an app to Apple's review queue, after a tap on exactly what Apple would receive."""
from ios_asc.client import AscError, Client
from ios_asc.review import readiness, submit
from ios_asc import withdraw


def _check(p):
    if set(p) != {"app_id", "version_id"}:
        raise ValueError("ios.submit-review needs exactly app_id and version_id")


def render(p):
    _check(p)
    lines, problems = readiness(Client(), p["app_id"], p["version_id"])
    if problems:
        raise ValueError("not ready to submit: " + "; ".join(problems))
    text = "\n".join(["Submit this app for App Store review?", ""] + lines)
    if len(text.encode("utf-16-le")) // 2 > 3500:
        raise ValueError("This approval would be cut off in Telegram; shorten the listing summary")
    return text


def perform(p):
    _check(p)
    c = Client()
    lines, problems = readiness(c, p["app_id"], p["version_id"])
    if problems:
        raise AscError("not ready to submit: " + "; ".join(problems))
    sub = submit(c, p["app_id"], p["version_id"])
    return (f"Submitted to App Review ({lines[0]})", f"reviewSubmission {sub}")


KINDS = {
    "ios.submit-review": (render, perform),
    "ios.withdraw-review": (
        lambda p: withdraw.render(Client(), p),
        lambda p: withdraw.perform(Client(), p),
    ),
}
