# herald-ios

A [Herald](https://github.com/benmross/herald) extension for building native
iOS apps from a machine that has no Xcode. Herald drives a Mac over SSH: it
scaffolds projects, builds them, publishes a tap-to-install page for your phone,
and fills in App Store listings. Submitting for review always waits for your tap.

```bash
herald ext install https://github.com/benmross/herald-ios
herald ext setup ios
```

## What you need

- A Mac with release Xcode (a beta Xcode cannot ship to the App Store), reachable
  over SSH with key auth. Tailscale works well.
- An Apple developer account and its Team ID.
- An App Store Connect API key. Its identifiers go in Herald's secret store under
  `appstore` (`key_id`, `issuer_id`, `key_path`), and a copy of the `.p8` goes at
  `~/private_keys/AuthKey_<key_id>.p8` on the Mac for xcodebuild.
- A build keychain on the Mac. `codesign` cannot reach the login keychain from an
  SSH session (`errSecInternalComponent`), so create a dedicated keychain once from
  a GUI Terminal, import your Apple signing identities into it, and save its
  password to `~/.config/build-keychain-pw`. Keep only Apple identities in it.
- An HTTPS address serving `ios.ota_dir` (iOS refuses plain-HTTP install
  manifests). `tailscale serve --https=<port>` in front of a local static server
  keeps it private to your tailnet.

## What it provides

- The `ios-apps` skill: how Herald sessions build, test and ship, and the traps
  that each cost a full build cycle the first time.
- `ios-new <Name> [bundle-id]`: a buildable iPhone-only SwiftUI project.
- `ios-run <project-dir> [scheme]`: build, sign and publish an install link.
- `ios-asc status|draft|submit`: App Store Connect listing status and drafts.
  `submit` is a red action: it shows exactly what Apple would receive and waits
  for your tap.

Settings are listed in `herald-extension.json` and asked by `herald ext setup ios`.
