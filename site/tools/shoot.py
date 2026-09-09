#!/usr/bin/env python3
"""Screenshot the demo page at a given viewport, so a layout claim can be looked at.

    miki-hybridge-ai/.venv/bin/python3 site/tools/shoot.py <out.png> [width] [height] [scroll]

Needs pyobjc-framework-WebKit, which is why it lives beside the page rather than in the plugin:
nothing chamnan ships may depend on it. The page is loaded from the local file, so this measures
the working tree and not whatever is currently deployed.

A full-page shot is not what is wanted here. The page is 6,000+ pixels tall and the question a
layout bug asks is always about one screen, so this takes a real viewport and an optional scroll
offset instead — the same thing a person looking at the page would see.
"""
import pathlib
import sys

import AppKit
import WebKit
import Quartz

OUT = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "shot.png").resolve()
W = int(sys.argv[2]) if len(sys.argv) > 2 else 1440
H = int(sys.argv[3]) if len(sys.argv) > 3 else 900
SCROLL = int(sys.argv[4]) if len(sys.argv) > 4 else 0
PAGE = pathlib.Path(__file__).resolve().parent.parent / "index.html"


class Done(AppKit.NSObject):
    """Navigation delegate. A plain Python attribute set in `init` does not survive the ObjC
    bridge here, so the flag lives in a module-level dict the delegate writes into."""

    def webView_didFinishNavigation_(self, view, nav):
        STATE["ready"] = True

    def webView_didFailNavigation_withError_(self, view, nav, err):
        STATE["ready"] = True
        STATE["error"] = str(err)


STATE = {"ready": False, "error": None}


def main():
    app = AppKit.NSApplication.sharedApplication()
    cfg = WebKit.WKWebViewConfiguration.alloc().init()
    view = WebKit.WKWebView.alloc().initWithFrame_configuration_(
        AppKit.NSMakeRect(0, 0, W, H), cfg)
    delegate = Done.alloc().init()
    STATE["ready"] = False
    view.setNavigationDelegate_(delegate)
    view.loadFileURL_allowingReadAccessToURL_(
        AppKit.NSURL.fileURLWithPath_(str(PAGE)),
        AppKit.NSURL.fileURLWithPath_(str(PAGE.parent)))

    loop = AppKit.NSRunLoop.currentRunLoop()
    _spin(loop, lambda: STATE["ready"], 30)
    if STATE["error"]:
        raise SystemExit(f"page did not load: {STATE['error']}")
    # The page's own scripts pick the language and paint the table after load fires, so a snapshot
    # taken the instant navigation finishes catches an unstyled frame.
    _spin(loop, lambda: False, 2.0)
    if SCROLL:
        view.evaluateJavaScript_completionHandler_(f"window.scrollTo(0,{SCROLL});", None)
        _spin(loop, lambda: False, 0.6)

    holder = {}
    snap = WebKit.WKSnapshotConfiguration.alloc().init()
    snap.setRect_(AppKit.NSMakeRect(0, 0, W, H))

    def got(image, err):
        holder["image"] = image
        holder["err"] = err
    view.takeSnapshotWithConfiguration_completionHandler_(snap, got)
    _spin(loop, lambda: "image" in holder, 20)

    image = holder.get("image")
    if image is None:
        raise SystemExit(f"no snapshot: {holder.get('err')}")
    rep = AppKit.NSBitmapImageRep.alloc().initWithData_(image.TIFFRepresentation())
    OUT.write_bytes(bytes(rep.representationUsingType_properties_(AppKit.NSPNGFileType, {})))
    print(f"{OUT}  {W}x{H} at scroll {SCROLL}  {OUT.stat().st_size:,} bytes")


def _spin(loop, done, seconds):
    """Run the main run loop until `done()` or the time is up — a WKWebView does nothing without it."""
    end = AppKit.NSDate.dateWithTimeIntervalSinceNow_(seconds)
    while AppKit.NSDate.date().compare_(end) < 0:
        if done():
            return
        loop.runUntilDate_(AppKit.NSDate.dateWithTimeIntervalSinceNow_(0.05))


if __name__ == "__main__":
    main()
