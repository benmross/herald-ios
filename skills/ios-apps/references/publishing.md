# Getting an app onto the App Store

Verified end to end on 8 September 2026 with Emulsion, from an
empty account to "Waiting for Review" in about ninety minutes, most of which
was spent on things listed here as traps.

Use `scripts/asc.py` for anything read-only. It authenticates and returns JSON:

```python
import sys; sys.path.insert(0, "<skill>/scripts")
from asc import get
get("apps"); get("builds", "?limit=5&sort=-uploadedDate")
get("certificates"); get("profiles"); get("bundleIds")
```

**Listing drafts and submission have tools now (7 November 2026).**

- `scripts/ios-asc status <bundle-id>` shows what the editable version's listing holds and
  what still blocks submission. Read only. Verified against Emulsion's real listing.
- `scripts/ios-asc draft <listing.json>` writes the draft: store text, app name and subtitle,
  privacy URL, the attached build, screenshots and App Review contact details. The JSON
  shape is in `lib/ios_asc/draft.py`. It is checked for Apple's length limits and for em
  dashes first. Drafts only change the user's own App Store Connect page. **The write paths are
  unit tested but have not yet run against Apple's API**, so the first real use should be
  watched, and a failure should be reported with the API's message.
- `scripts/ios-asc submit <bundle-id>` files `ios.submit-review`, a red action: it refuses
  unless the listing is complete, then shows the user exactly what Apple would receive and waits
  for their tap. Nothing else in the extension can write to `reviewSubmissions`
  (`client.write` checks `red.acting()`). Use `--show` to see the tap text without asking.
- `herald act run ios.withdraw-review --payload-file <payload.json>` withdraws one
  submission after its own tap. The payload binds `app_id`, `version_id`,
  `submission_id` and the currently attached `build_id`. It refuses anything
  beyond one app-version item or anything no longer Waiting for Review.
  Upload and verify the replacement first; after withdrawal, attach it with
  `ios-asc draft`, verify readiness, then use the usual `ios-asc submit` tap.
- Creating the app record is still web UI only.

## Order of operations

1. **Preflight the toolchain.** See SKILL.md. A beta Xcode wastes everything
   downstream.
2. **Register the bundle ID.** Developer portal or `POST /v1/bundleIds`.
3. **Distribution certificate.** The user creates it in Xcode
   (Settings > Accounts > Manage Certificates > Apple Distribution). Check with
   `get("certificates")` that a `DISTRIBUTION` row exists; two `DEVELOPMENT`
   rows are not enough.
4. **Create the app record.** Web UI only. Confirmed: `POST /v1/apps` returns
   "The resource 'apps' does not allow 'CREATE'. Allowed operations are:
   GET_COLLECTION, GET_INSTANCE, UPDATE".
   - **Name must be globally unique.** Not checked until Create is pressed.
     A collision does *not* mean renaming the app: `CFBundleDisplayName` (the
     home screen) and the bundle ID are separate strings and only the store
     title has to be unique. "Emulsion" was taken; the app is still Emulsion on
     the phone and "Emulsion: Grain Wallpaper" in the store.
   - **SKU is permanent.** Use the bundle ID so everything is keyed alike.
5. **Archive and upload.** See the signing section below.
6. **Metadata and screenshots.** See the fields section.
7. **Submit.** Always the user's, every time, no exception.

## Signing

Provisioning works headlessly. This was the surprise, and it means only one
step actually needs a human:

```bash
xcodebuild ... archive \
  DEVELOPMENT_TEAM=<team id> -allowProvisioningUpdates \
  -authenticationKeyPath $HOME/private_keys/AuthKey_XXXX.p8 \
  -authenticationKeyID XXXX -authenticationKeyIssuerID <uuid>
```

With the API key passed in, `xcodebuild` creates and installs profiles over SSH
with no GUI. An earlier "No Account for Team" failure was purely the absence of
that key, not a limitation of SSH.

**`codesign` is the wall.** From an SSH session it returns
`errSecInternalComponent`, and every keychain call returns "User interaction is
not allowed", even when the user is logged in at the console, because SSH lives in a
different security session. `security set-key-partition-list` is the usual fix
and did not clear it. Do not spend more of their time on this: the fix costs
password-bearing shell commands to save three GUI clicks.

**Update, 7 November 2026:** a dedicated unlocked keychain fixes the wall for
development signing (`~/setup-build-keychain.sh`, run once in a GUI Terminal;
verified by `ios-run`). If the build keychain also holds the Apple Distribution
identity, a headless App Store archive and `xcodebuild -exportArchive` with
`destination = upload` should work; that has NOT been tested yet. A Mac whose build
keychain holds only the Development identity cannot make App Store archives. Test
with an archive and export before relying on it, and do not upload anything
without the user's say-so. Which of this install's Macs holds which identity is in
its ledger, not here.

**Until that is verified, the archive happens in Xcode.** Scheme destination "Any iOS Device",
Product > Archive, then Organizer > Distribute App > App Store Connect >
Upload.

Bump `CURRENT_PROJECT_VERSION` before any re-upload; build numbers cannot
repeat. Builds take a few minutes to appear; poll with
`get("builds", "?limit=5&sort=-uploadedDate")` in a background command rather
than making the user refresh, and wait for `processingState=VALID`.

## Screenshots

Render them natively. Never resize, especially for anything with fine detail:
resampling grain is exactly the operation that causes aliasing, and on a
generative-texture app the texture is the product.

App Store Connect has separate slots per display class and rejects anything
that does not match the slot exactly:

- **6.9 inch**: 1320 x 2868. iPhone 17 Pro Max simulator.
- **6.5 inch**: 1284 x 2778 or 1242 x 2688. iPhone 13 Pro Max simulator.

`xcrun simctl list devicetypes` still carries retired device types long after
the hardware is gone, so any legacy size can be rendered natively:

```bash
xcrun simctl create shot65 \
  com.apple.CoreSimulator.SimDeviceType.iPhone-13-Pro-Max \
  com.apple.CoreSimulator.SimRuntime.iOS-27-0
```

Always set a clean status bar first, or the shots carry whatever the simulator
felt like showing:

```bash
xcrun simctl status_bar $D override --time "9:41" --cellularMode active \
  --cellularBars 4 --wifiBars 3 --batteryState charged --batteryLevel 100
```

Vary the content between frames. The first Emulsion set showed the same plate
five times, which badly undersold an app whose premise is fourteen looks. A
DEBUG launch-argument that picks the starting state makes this trivial.

## The fields

Write each into its own file, measured against Apple's limit, so pasting is
mechanical. Limits: name 30, subtitle 30, promotional text 170, keywords 100,
description 4000.

- **No hard line wraps in prose fields.** App Store Connect wraps text itself.
  Writing the copy at 76 columns in Markdown and pasting it bakes mid-sentence
  breaks into the listing at a width matching no device. Keep paragraph breaks
  and all-caps section headings; unwrap everything else.
- **Follow the user's writing preferences** (`ledger/identity/preferences.md`).
  If they rule out em dashes, rewrite rather than substitute; a blind swap to commas
  produces comma splices, which is a worse tell than the dash.
- **Privacy policy URL is required** and must be a real page. For a
  no-network app, host one on the project's own site.
- **Export compliance**: no encryption beyond the OS means answer No.
- **App Privacy**: "Data Not Collected" if nothing leaves the device. Photos
  add-only is a write, not a read, and still counts as collecting nothing.

Fields that look required and are not: **Routing App Coverage File** (only for
apps declaring `MKDirectionsApplicationSupportedModes`), App Review demo
account when there is no login, and release notes on a 1.0.

## TestFlight

Runs in parallel with App Store review and does not delay it.

- **Internal**: instant, no review, but testers must be users on the user's App Store
  Connect account. That means giving friends access to their developer account.
  Rarely worth it.
- **External**: up to 10,000, join by tapping a public link with no account,
  but needs a Beta App Review. Separate from App Store review and usually much
  faster, though not instant, so it does not help if the app is minutes from
  approval anyway.

Never distribute a build made with beta Xcode, even to testers.
