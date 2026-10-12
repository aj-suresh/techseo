#!/usr/bin/env python3
"""List a site's known URLs from the Internet Archive's index (no requests to the site itself).

Usage: wayback_urls.py example.com -o urls.json [--limit 5000] [--since 2024]

Useful when a site has no sitemap and crawling is blocked or too thin. Returns URLs the Archive
has captured with a 200 status, HTML only, deduplicated. These can include pages that no longer
exist, so audit them (audit_urls.py --sample) before treating any as current. Stdlib only.
"""
import argparse, json, urllib.parse, urllib.request

ap = argparse.ArgumentParser()
ap.add_argument("domain"); ap.add_argument("-o", "--out", default="urls.json")
ap.add_argument("--limit", type=int, default=5000); ap.add_argument("--since", default="2024")
a = ap.parse_args()
q = urllib.parse.urlencode([("url", a.domain.replace("https://", "").replace("http://", "").strip("/") + "/*"), ("output", "json"),
    ("fl", "original"), ("collapse", "urlkey"), ("filter", "statuscode:200"), ("filter", "mimetype:text/html"),
    ("from", a.since), ("limit", a.limit)])
req = urllib.request.Request("https://web.archive.org/cdx/search/cdx?" + q, headers={"User-Agent": "Mozilla/5.0 (sitemap-builder)"})
rows = json.load(urllib.request.urlopen(req, timeout=120))[1:]
seen, out = set(), []
for (u,) in rows:
    u = u.split("#")[0].replace(":80/", "/")
    if "?" in u: continue
    u = ("https://" + u.split("://", 1)[1]).rstrip("/") if "://" in u else u
    k = u.lower().replace("://www.", "://")
    if k in seen: continue
    seen.add(k); out.append({"loc": u, "lastmod": None, "alternates": [], "source": "wayback"})
json.dump(out, open(a.out, "w"), indent=1)
print(f"{len(out)} archived URLs -> {a.out}")
