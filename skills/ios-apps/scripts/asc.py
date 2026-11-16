"""Read-only App Store Connect client.

Signs its own ES256 JWT from the key identified in config/secrets.json under
`appstore`. Never prints or returns the key itself.

    import sys; sys.path.insert(0, ".claude/skills/ios-apps/scripts")
    from asc import get
    get("apps")
    get("builds", "?limit=5&sort=-uploadedDate")

Writes (POST/PATCH) are deliberately not wrapped here: they are currently
denied by the harness permission classifier, so a helper would only produce
a confusing failure. If the user grants that permission, add them then.
"""
import json, time, os, pathlib, urllib.request, urllib.error, jwt

S = json.load(open(pathlib.Path(os.environ.get("HERALD_HOME", pathlib.Path.home()/".herald"))/"secrets.json"))["appstore"]
KEY = pathlib.Path(os.path.expanduser(S["key_path"])).read_text()

def token():
    now = int(time.time())
    return jwt.encode(
        {"iss": S["issuer_id"], "iat": now, "exp": now + 900, "aud": "appstoreconnect-v1"},
        KEY, algorithm="ES256", headers={"kid": S["key_id"], "typ": "JWT"})

def get(path, params=""):
    url = f"https://api.appstoreconnect.apple.com/v1/{path}{params}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token()}"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return {"_httperror": e.code, "_body": e.read().decode()[:400]}
