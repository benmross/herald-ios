---
name: ios-apps
description: Build, test, sign, and publish native iOS apps for the user, from an idea to an App Store submission, by driving their Mac over SSH from Herald's machine. Use this whenever they want an iPhone app built, changed, tested on a simulator or device, archived, uploaded to TestFlight, or submitted for review. Covers the project shape that does not silently break, how to test and screenshot without touching the device, the signing and provisioning path that works headlessly and the one step that does not, App Store Connect's real requirements, and the traps that each cost a full build cycle the first time.
---

# Building and shipping iOS apps

All of this was learned by shipping Emulsion, a wallpaper app, to the App Store on
8 September 2026, in one afternoon. Everything stated here was verified.
Read `references/publishing.md` before a submission and
`references/testing.md` before trying to prove an app works.

## The machine

Herald's machine may have no Xcode. Every build, simulator and signing
operation happens on a Mac over SSH (Tailscale works well). This install's
specifics are settings and a ledger note, never this file:

```bash
herald config get ios        # build_host, fallback_host, team_id, signing_identity,
                             # ota_url, ota_dir, bundle_prefix, node_bin
herald context ios-build-setup   # machine facts: keychains, devices, quirks
```

Below, `$MAC` means `ios.build_host`. A laptop with its lid closed drops off
the network and `ssh` times out. That is ordinary, not a fault. Retry two or
three times with a sleep before concluding anything is wrong.

- The App Store Connect API key's identifiers are in secrets.json under
  `appstore` (`issuer_id`, `key_id`, `key_path`). xcodebuild needs a copy of the
  `.p8` at `~/private_keys/AuthKey_<key_id>.p8` on the Mac. Never print it.
- `scripts/asc.py` in this skill is a working authenticated client. Import it
  and call `get("apps")`. It signs its own ES256 JWT.
- If Node is not on PATH, `ios.node_bin` says where it is. Export it before
  running any web build.

## Preflight, before writing any code

Run this first. Two of these have each cost a full build-and-upload cycle.

```bash
ssh $MAC 'xcode-select -p; xcodebuild -version; ls -d /Applications/Xcode*.app'
```

- **A beta Xcode cannot ship.** App Store Connect rejects the build at the very
  last gate, after signing, uploading and all the metadata work are done. If
  `xcode-select -p` points at `Xcode-beta.app`, or `xcodebuild -version` shows a
  beta, stop and have the user install release Xcode from the Mac App Store, then
  `sudo xcode-select -s /Applications/Xcode.app`. Both can coexist.
- Check the deployment target against reality, not against the version number.
  iOS 26 sounds new and was a year old by September 2026, at 79% of all iPhones
  (Apple's own figure). Look it up at developer.apple.com/support/app-store/
  rather than guessing from how large the number is.

## Project shape

**Check a hand-written `.xcodeproj` into git. Do not use XcodeGen.**

XcodeGen rewrites whatever sits at `info.path` and `entitlements.path` back to
a bare template on *every* `xcodegen generate`. On HeraldHealth this silently
deleted `NSHealthShareUsageDescription` and both HealthKit entitlements, twice,
and each one only surfaced as a crash on a real device because Info.plist keys
have no build-time check at all. A clean `CODE_SIGNING_ALLOWED=NO` build is not
evidence those files are intact.

If a project must use XcodeGen, put the contents in `project.yml` under
`info.properties` and `entitlements.properties` so the generator owns them, and
delete the hand-maintained files so nothing can diverge.

Otherwise:

- `TARGETED_DEVICE_FAMILY = 1` for iPhone only.
- Capabilities come from entitlements. An app with no entitlements file needs
  no App ID capabilities at all. Saving to Photos is add-only and is just
  `NSPhotoLibraryAddUsageDescription` in Info.plist, not a capability.
- Commit at every milestone. A long build is exactly when an interruption
  happens, and `git log` is the cheapest handoff to the next session. The
  session that wrote Emulsion wrote the entire app and committed nothing.

## The loop

```bash
rsync -az --delete --exclude '.git' ./ $MAC:Developer/<Name>/
ssh $MAC 'cd ~/Developer/<Name> && xcodebuild -project <Name>.xcodeproj \
  -scheme <Name> -sdk iphonesimulator \
  -destination "platform=iOS Simulator,name=iPhone 17 Pro" \
  -derivedDataPath /tmp/dd CODE_SIGNING_ALLOWED=NO build'
```

**Batch remote work into one script.** Build, install, launch, screenshot and
fetch in a single `ssh` invocation that returns one artefact. Fifteen separate
round trips cost far more wall clock than the work inside them, and a lid
closing mid-sequence loses the whole sequence.

The `--exclude '.git'` above has a cost: the Mac copy is not a repository, so
Xcode reports no source control and Xcode Cloud refuses to configure. If the user
wants either, clone from GitHub on the Mac and `git pull` instead of rsyncing.

## Judgment that generalises

- **Measure before optimising, and delete before fixing a third time.**
  Emulsion shipped with an adaptive-resolution renderer that caused three
  separate visible bugs. It was fixed three times before anyone asked what it
  bought: measured, 0.06 to 0.75 ms a frame against an 8.3 ms budget. It was
  removed, 194 lines for 35. Three bugs in one component is a reason to question
  the component.
- **A container's shape change needs its contents rechecked.** Two of that
  day's UI bugs were caused by the previous fix in the same area.
- Screenshots and simulators cannot see a real device. Say plainly what has
  only been verified in a simulator.

## Publishing

See `references/publishing.md`. Everything is automatable
except two things. App Store Connect's API refuses to create the app record
(`apps` allows GET and UPDATE, not CREATE), and `codesign` cannot reach the
login keychain from an SSH session, so the archive itself happens in Xcode.

## New app, start to finish (verified 7 November 2026)

1. `scripts/ios-new <Name> [bundle-id]` stamps a buildable iPhone-only SwiftUI project into
   `projects/<name>-ios` in the Herald checkout from `template/` (hand-written project,
   git-initialised, team from `ios.team_id`, bundle id from `ios.bundle_prefix` unless given).
   Load `herald-projects` first: new repos are private, commit at milestones.
2. Write the app. Info.plist keys go in the project's build settings (`INFOPLIST_KEY_*`)
   or an Info.plist file added to the target; entitlements only if a capability needs one.
3. `scripts/ios-run <project-dir> <Name>` builds on `ios.build_host` (falling back to
   `ios.fallback_host` if it is unreachable) and prints the install page. Send the user the link.
4. The user taps Install in Safari. A re-run with the same bundle id updates in place.
5. Simulators work headlessly over SSH: `xcrun simctl boot` and `xcrun simctl io <device>
   screenshot`.

Publishing: `scripts/ios-asc` (status, draft, submit) and `references/publishing.md`.

Known limits: development builds only run on phones registered in the account and expire with
the profile (about a year). The build Mac needs to be reachable and logged in, for the keychain
below.

## Fast install to the phone (verified 7 November 2026)

`scripts/ios-run <project-dir> [scheme]` rsyncs the project to the build Mac
(`IOS_BUILD_HOST` overrides `ios.build_host`), unlocks the build keychain,
archives, exports a development IPA with automatic signing through the App Store
Connect key, pulls it to `ios.ota_dir` (default `~/ota`) and prints the install
page at `ios.ota_url`. A small app builds and publishes in seconds. The scheme
must equal the project name unless given. The user taps the link in Safari on
the phone and taps Install. Serving over the tailnet works even on networks that
isolate clients and block `devicectl`.

- Serve `ios.ota_dir` over HTTPS at `ios.ota_url`: iOS refuses plain-HTTP
  manifests. A local static server plus `tailscale serve --https=<port>` keeps it
  on the tailnet only.
- The build Mac needs `~/.config/build-keychain-pw` and `build.keychain-db`, made
  once from a GUI Terminal, because codesign cannot reach the login keychain over
  SSH (errSecInternalComponent). Keep only Apple identities in it.
- With the phone on USB, `xcrun devicectl device install app --device <udid> <app>` installs in ~3s.
- A new bundle id is provisioned automatically on first build. Development IPAs only install on
  phones registered in the account.
- Never `pkill -f` a pattern that appears in your own command line: it kills the shell.
