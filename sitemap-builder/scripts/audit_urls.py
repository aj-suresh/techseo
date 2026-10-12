#!/usr/bin/env python3
"""Probe URLs live and record what each one really returns.

Usage: audit_urls.py urls.json -o audit.json [--workers 12]
       audit_urls.py --list-file urls.txt -o audit.json   (plain list, one URL per line)

Per URL: status, redirect target, robots (meta tag and X-Robots-Tag), canonical, title,
and a soft-404 flag (200 page titled 'not found'). Redirects are NOT followed so a
301 shows up as a 301. Stdlib only.
"""
import argparse, json, re, sys, time, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor

UA = "Mozilla/5.0 (sitemap-builder audit)"

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None

opener = urllib.request.build_opener(NoRedirect)

DELAY = 0.0

def probe(url):
    if DELAY:
        time.sleep(DELAY)
    rec = {"url": url, "status": None, "redirect": "", "robots": "", "canonical": "", "title": "", "soft404": False, "error": ""}
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        try:
            r = opener.open(req, timeout=30)
        except urllib.error.HTTPError as e:
            r = e
        rec["status"] = r.getcode()
        rec["redirect"] = r.headers.get("Location", "") or ""
        xr = r.headers.get("X-Robots-Tag", "") or ""
        ctype = r.headers.get("Content-Type", "")
        body = ""
        if "html" in ctype:
            body = r.read(400000).decode("utf-8", "replace")
        meta = re.search(r'<meta[^>]+name=["\']robots["\'][^>]*content=["\']([^"\']*)', body, re.I) or \
               re.search(r'<meta[^>]+content=["\']([^"\']*)["\'][^>]*name=["\']robots', body, re.I)
        rec["robots"] = ", ".join(x for x in [meta.group(1) if meta else "", xr] if x)
        can = re.search(r'<link[^>]+rel=["\']canonical["\'][^>]*href=["\']([^"\']*)', body, re.I)
        rec["canonical"] = can.group(1) if can else ""
        t = re.search(r"<title[^>]*>([^<]*)", body, re.I)
        rec["title"] = (t.group(1).strip() if t else "")[:160]
        rec["soft404"] = rec["status"] == 200 and bool(re.search(r"not found|404", rec["title"], re.I))
        rec["content_type"] = ctype.split(";")[0]
    except Exception as e:
        rec["error"] = str(e)[:200]
    return rec

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("input", nargs="?")
    ap.add_argument("--list-file")
    ap.add_argument("-o", "--out", default="audit.json")
    ap.add_argument("--workers", type=int, default=12, help="use 3-4 for sites you do not own")
    ap.add_argument("--delay", type=float, default=0.0, help="seconds each worker waits before a request (be polite to third-party sites)")
    ap.add_argument("--sample", type=int, help="probe only N evenly spaced URLs (quick look at a large competitor site)")
    a = ap.parse_args()
    if a.list_file:
        urls = [l.strip() for l in open(a.list_file) if l.strip()]
    else:
        urls = [r["loc"] for r in json.load(open(a.input))]
    urls = list(dict.fromkeys(urls))
    if a.sample and len(urls) > a.sample:
        step = len(urls) / a.sample
        urls = [urls[int(i * step)] for i in range(a.sample)]
    DELAY = a.delay
    with ThreadPoolExecutor(a.workers) as ex:
        res = list(ex.map(probe, urls))
    json.dump(res, open(a.out, "w"), indent=1)
    from collections import Counter
    print(len(res), "probed;", dict(Counter(r["status"] for r in res)),
          "| noindex:", sum("noindex" in r["robots"].lower() for r in res),
          "| soft404:", sum(r["soft404"] for r in res), "| errors:", sum(bool(r["error"]) for r in res))
    blocked = sum(r["status"] in (401, 403, 429, 503) for r in res)
    if blocked > len(res) * 0.2:
        print("WARNING: many 401/403/429/503 responses. The site is probably rate-limiting or blocking bots; "
              "treat status results as unreliable, slow down (--workers 2 --delay 2) or report URLs unaudited.")
