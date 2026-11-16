# Proving an iOS app works without touching the device

The constraint that shapes all of this: Herald cannot tap. `simctl` has no verb
for synthesising a touch, and building a UI test target to press eight buttons
is more machinery than the problem deserves. Almost everything below exists to
work around that one gap.

## Reach any screen with a DEBUG launch argument

Read state from the environment, guarded so it cannot exist in a release build:

```swift
init() {
    #if DEBUG
    if let name = ProcessInfo.processInfo.environment["APP_CATEGORY"],
       let match = Category.allCases.first(where: {
           $0.title.caseInsensitiveCompare(name) == .orderedSame }) {
        category = match
    }
    #endif
}
```

`simctl` passes environment through with a `SIMCTL_CHILD_` prefix:

```bash
SIMCTL_CHILD_APP_CATEGORY=Tone xcrun simctl launch $D com.example.app
```

This is what makes screenshotting every screen possible in one batched script.
Add one for each axis worth varying: which panel, which document, which preset.

## Reach anything behind a menu with a self-test hook

Export lived behind a `Menu`, so the whole render-and-encode path was shipping
unexercised. A DEBUG hook that runs it and writes the result somewhere fetchable
fixes that:

```swift
if ProcessInfo.processInfo.environment["APP_SELFTEST"] == "export" {
    await actions.selfTestExport()   // writes to Documents, logs via NSLog
}
```

Then pull it off and check the *pixels*, not just that a file appeared:

```bash
C=$(xcrun simctl get_app_container $D com.example.app data)
cp "$C/Documents/selftest-export.png" /tmp/
```

This matters more than it looks. A preview and an export are two different
render passes at two different resolutions, so a screenshot of the preview is
no evidence at all about the exported file. Check standard deviation and mean
neighbour delta to prove it is a real image and not a blank frame.

## Reproduce a device-only bug by moving the threshold

Emulsion's grain flicker would not reproduce in the simulator, because the
simulator's GPU times sit far below the thresholds that triggered it, so the
back-off branch never ran. Exposing the threshold as a DEBUG environment
override reproduced it immediately and deterministically.

**Generalise this.** When a bug will not reproduce off-device, find the
threshold real hardware crosses and the simulator does not, then move the
threshold rather than giving up. Timeouts, frame budgets, memory limits and
cache sizes are all candidates.

Instrument the same way. A counter that logs draws per second turned "it feels
slow" into "this is drawing continuously while idle", and after the fix, "one
draw and then silence".

## Read screenshots as contact sheets

Full-resolution screenshots are expensive to look at and slow to move. Crop to
the region that differs, downscale, and tile them into one image:

```python
from PIL import Image, ImageDraw
tiles = [Image.open(f).crop((0, TOP, W, H)).resize((W//2, (H-TOP)//2)) for f in files]
```

Five panels in one image instead of five reads. Verify dimensions
programmatically with an assert rather than by eye.

## Check the runtime log properly

```bash
xcrun simctl spawn $D log show --last 30s --predicate 'process == "AppName"'
```

Filter with care. A naive `grep -iE "error|fault|assert"` matches the word
`Default` in every single log line and the word `assertion` in ordinary UIKit
background-task chatter. Filter on the log *level* column instead, and treat a
genuinely empty result as the good news it is.

## What a simulator cannot tell you

Signing, real GPU timings, HealthKit, camera, background delivery, thermal
behaviour and actual battery cost. When something has only been checked in a
simulator, say so plainly rather than implying it has been verified. Several of
Emulsion's worst bugs were invisible until it ran on a real phone.
