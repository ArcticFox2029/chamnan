#!/usr/bin/env python3
"""Load the demo page in a WKWebView, press Measure, and report what the page says and logs.

    miki-hybridge-ai/.venv/bin/python3 site/tools/probe.py [url] [seconds]

`shoot.py` answers "what does it look like"; this answers "does it work". A screenshot of a page
stuck on "Loading the Python runtime" looks exactly like a screenshot of one still loading, and the
difference is in the console — so console.log/warn/error, window.onerror and unhandled rejections
are all forwarded to a message handler and printed with the status line the page is showing.
"""
import pathlib
import sys

import AppKit
import WebKit

URL = sys.argv[1] if len(sys.argv) > 1 else "https://arcticfox2029.github.io/chamnan-measure/"
WAIT = float(sys.argv[2]) if len(sys.argv) > 2 else 90.0
# What a visitor types. Given, because the failure being chased was reported with one specific
# repository in the box and an empty box takes a different path through the page entirely.
REPO = sys.argv[3] if len(sys.argv) > 3 else ""
LOG = []

HOOK = """
(function () {
  function send(kind, args) {
    try {
      window.webkit.messageHandlers.probe.postMessage(
        kind + " :: " + Array.from(args).map(function (a) {
          if (a instanceof Error) return a.stack || (a.name + ": " + a.message);
          try { return typeof a === "string" ? a : JSON.stringify(a); } catch (e) { return String(a); }
        }).join(" "));
    } catch (e) {}
  }
  ["log", "warn", "error", "info"].forEach(function (k) {
    var orig = console[k].bind(console);
    console[k] = function () { send(k, arguments); orig.apply(console, arguments); };
  });
  window.addEventListener("error", function (e) {
    send("onerror", [e.message + " @ " + e.filename + ":" + e.lineno]);
  });
  window.addEventListener("unhandledrejection", function (e) {
    send("rejected", [e.reason]);
  });
})();
"""


class Probe(AppKit.NSObject):
    def webView_didFinishNavigation_(self, view, nav):
        STATE["ready"] = True

    def webView_didFailProvisionalNavigation_withError_(self, view, nav, err):
        STATE["ready"] = True
        LOG.append(f"navigation failed :: {err}")

    def userContentController_didReceiveScriptMessage_(self, controller, message):
        LOG.append(str(message.body()))


STATE = {"ready": False}
SEEN = []

CARDS_JS = """
(function () {
  var g = document.querySelector('.cards');
  if (!g) return ['no .cards yet'];
  var cols = getComputedStyle(g).gridTemplateColumns.split(' ').length;
  var out = ['grid ' + g.clientWidth + 'px in ' + cols + ' column(s)'];
  document.querySelectorAll('.card').forEach(function (c, i) {
    var t = c.querySelector('table');
    out.push('  card ' + (i + 1) + ' box ' + c.clientWidth + 'px content ' + c.scrollWidth +
             'px' + (t ? ', table needs ' + t.scrollWidth + 'px' : ''));
  });
  return out;
})();
"""

OVERFLOW_JS = """
(function () {
  var out = [];
  var all = document.querySelectorAll('*');
  for (var i = 0; i < all.length; i++) {
    var el = all[i];
    var ox = getComputedStyle(el).overflowX;
    if (ox === 'auto' || ox === 'scroll') continue;
    // A form field whose value is longer than the box is normal and natively scrollable — the
    // caret reaches the rest. Reporting it buried the one real overflow beside it.
    if (/^(input|textarea|select)$/.test(el.tagName.toLowerCase())) continue;
    if (el.clientWidth > 0 && el.scrollWidth > el.clientWidth + 1) {
      var cls = (typeof el.className === 'string' && el.className)
        ? '.' + el.className.trim().replace(/ +/g, '.') : '';
      out.push(el.tagName.toLowerCase() + cls + ' : content ' + el.scrollWidth +
               'px inside ' + el.clientWidth + 'px');
    }
  }
  return out;
})();
"""


def _spin(loop, done, seconds):
    end = AppKit.NSDate.dateWithTimeIntervalSinceNow_(seconds)
    while AppKit.NSDate.date().compare_(end) < 0:
        if done():
            return
        loop.runUntilDate_(AppKit.NSDate.dateWithTimeIntervalSinceNow_(0.05))


def read(view, loop, js, seconds=8.0):
    box = {}
    view.evaluateJavaScript_completionHandler_(js, lambda v, e: box.update(v=v, e=e))
    _spin(loop, lambda: "v" in box, seconds)
    return box.get("v")


def shot(view, loop, out):
    """Photograph the result cards, which exist only after a measurement finishes — so `shoot.py`,
    which loads the page and stops, can never picture them."""
    # `?.` on a missing element yields undefined, undefined + number is NaN, and `int(NaN)` raises:
    # a run that timed out before the cards appeared used to die here rather than say so.
    y = read(view, loop, "document.querySelector('.cards')?.getBoundingClientRect().top + "
                         "window.scrollY - 24")
    try:
        y = int(y)
    except (TypeError, ValueError):
        print("\nno shot: the measurement did not finish, so there are no cards to photograph")
        return
    read(view, loop, f"window.scrollTo(0, {y});")
    _spin(loop, lambda: False, 0.6)
    box = {}
    snap = WebKit.WKSnapshotConfiguration.alloc().init()
    snap.setRect_(AppKit.NSMakeRect(0, 0, view.frame().size.width, view.frame().size.height))
    view.takeSnapshotWithConfiguration_completionHandler_(
        snap, lambda img, err: box.update(img=img, err=err))
    _spin(loop, lambda: "img" in box, 20)
    img = box.get("img")
    if img is None:
        print(f"\nsnapshot failed: {box.get('err')}")
        return
    rep = AppKit.NSBitmapImageRep.alloc().initWithData_(img.TIFFRepresentation())
    out.write_bytes(bytes(rep.representationUsingType_properties_(AppKit.NSPNGFileType, {})))
    print(f"\nshot: {out}")


def main():
    AppKit.NSApplication.sharedApplication()
    cfg = WebKit.WKWebViewConfiguration.alloc().init()
    # 🐛 [2026-09-09] Verifying a just-published page WITHOUT this served the WKWebView's own
    # cached copy, and the run reported the previous build's layout as if it were the new one —
    # the second time in one session that a warm cache nearly recorded the wrong conclusion.
    # Checking a deployment means checking it cold.
    if "--cold" in sys.argv:
        # A first-time visitor, which is the only one who waits for the 10 MB runtime. With the
        # default persistent store every run after the first is warm, and a warm run cannot show
        # what a cold one looks like — the confound that nearly had this reported as a regression.
        cfg.setWebsiteDataStore_(WebKit.WKWebsiteDataStore.nonPersistentDataStore())
    probe = Probe.alloc().init()
    controller = cfg.userContentController()
    controller.addScriptMessageHandler_name_(probe, "probe")
    controller.addUserScript_(WebKit.WKUserScript.alloc()
                              .initWithSource_injectionTime_forMainFrameOnly_(HOOK, 0, True))
    width = 1280
    if "--width" in sys.argv:
        width = int(sys.argv[sys.argv.index("--width") + 1])
    view = WebKit.WKWebView.alloc().initWithFrame_configuration_(
        AppKit.NSMakeRect(0, 0, width, 900), cfg)
    view.setNavigationDelegate_(probe)
    view.loadRequest_(AppKit.NSURLRequest.requestWithURL_(AppKit.NSURL.URLWithString_(URL)))

    loop = AppKit.NSRunLoop.currentRunLoop()
    _spin(loop, lambda: STATE["ready"], 45)
    print(f"loaded: {URL}")
    _spin(loop, lambda: False, 3.0)

    print("  status:", read(view, loop, "document.getElementById('status')?.textContent?.trim()"))
    print("  button disabled:", read(view, loop, "document.querySelector('button[type=submit],#go')?.disabled"))

    # Press the thing a visitor presses, and watch what the page reports.
    if REPO:
        read(view, loop, """
            (function () {
              var i = document.getElementById('repo');
              i.value = %r;
              i.dispatchEvent(new Event('input', {bubbles: true}));
              return i.value;
            })();""" % REPO)
    read(view, loop, """
        (function () {
          var b = document.getElementById('go') ||
                  Array.from(document.querySelectorAll('button')).find(function (x) {
                    return /measure/i.test(x.textContent); });
          if (!b) return 'no button found';
          b.disabled = false; b.click(); return 'clicked ' + b.textContent.trim();
        })();""")
    # Sample the status line as it changes, so a stage that comes and goes is not missed.
    end = AppKit.NSDate.dateWithTimeIntervalSinceNow_(WAIT)
    while AppKit.NSDate.date().compare_(end) < 0:
        now = read(view, loop, "document.getElementById('status')?.textContent?.trim()", 3.0)
        if now and (not SEEN or SEEN[-1] != now):
            SEEN.append(now)
        _spin(loop, lambda: False, 1.0)
    print("  status after:", read(view, loop, "document.getElementById('status')?.textContent?.trim()"))
    for line in SEEN:
        print("  seen:", line)
    # Anything whose content is wider than the box drawn around it. A clipped table looks like a
    # design choice in a screenshot and like missing data to a reader, so it is measured rather
    # than eyeballed. `null` back means the check itself failed and is reported as such — a
    # measurement that cannot run must never read as a clean result.
    cards = read(view, loop, CARDS_JS, 10.0)
    print("\nresult cards:")
    for line in (cards or ["(check failed)"]):
        print("   ", line)

    over = read(view, loop, OVERFLOW_JS, 10.0)
    print("\nclipped (content wider than its box):")
    if over is None:
        print("    CHECK FAILED — the probe script did not return; see the console below")
    elif not over:
        print("    none")
    else:
        for line in over:
            print("   ", line)

    if "--shot" in sys.argv:
        shot(view, loop, pathlib.Path(sys.argv[sys.argv.index("--shot") + 1]).resolve())

    print(f"\nconsole ({len(LOG)} message(s)):")
    for line in LOG[:60]:
        print("   ", line[:400])


if __name__ == "__main__":
    main()
