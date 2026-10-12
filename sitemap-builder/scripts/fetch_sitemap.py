#!/usr/bin/env python3
"""Discover and read a site's live XML sitemap(s).

Usage: fetch_sitemap.py https://example.com [-o urls.json]

Finds the sitemap via robots.txt (falls back to /sitemap.xml, /sitemap_index.xml),
follows sitemap indexes, and writes JSON: [{"loc": ..., "lastmod": ..., "alternates": [[hreflang, href], ...]}].
Stdlib only.
"""
import argparse, gzip, json, re, sys, urllib.request, xml.etree.ElementTree as ET

UA = "Mozilla/5.0 (sitemap-builder)"

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "gzip"})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = r.read()
        if data[:2] == b"\x1f\x8b":
            data = gzip.decompress(data)
        return r.geturl(), data.decode("utf-8", "replace")

def local(tag):
    return tag.rsplit("}", 1)[-1]

def candidates(site):
    site = site.rstrip("/")
    found = []
    try:
        _, robots = get(site + "/robots.txt")
        found = re.findall(r"(?im)^\s*sitemap:\s*(\S+)", robots)
    except Exception as e:
        print(f"robots.txt unreadable: {e}", file=sys.stderr)
    extra = [site + p for p in ("/sitemap.xml", "/sitemap_index.xml", "/sitemap-index.xml", "/wp-sitemap.xml", "/sitemap.xml.gz")]
    return found + [e for e in extra if e not in found]

def read(url, out, seen):
    if url in seen:
        return
    seen.add(url)
    try:
        _, body = get(url)
        root = ET.fromstring(body.lstrip())
    except Exception as e:
        print(f"skip {url}: {e}", file=sys.stderr)
        return
    if local(root.tag) == "sitemapindex":
        for sm in root:
            loc = next((c.text.strip() for c in sm if local(c.tag) == "loc" and c.text), None)
            if loc:
                read(loc, out, seen)
        return
    for u in root:
        if local(u.tag) != "url":
            continue
        rec = {"loc": None, "lastmod": None, "alternates": [], "source": url}
        for c in u:
            t = local(c.tag)
            if t == "loc" and c.text:
                rec["loc"] = c.text.strip()
            elif t == "lastmod" and c.text:
                rec["lastmod"] = c.text.strip()
            elif t == "link" and c.get("hreflang"):
                rec["alternates"].append([c.get("hreflang"), c.get("href")])
        if rec["loc"]:
            out.append(rec)

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("site")
    ap.add_argument("-o", "--out", default="urls.json")
    a = ap.parse_args()
    out, seen = [], set()
    for c in candidates(a.site):
        read(c, out, seen)
        if out:
            break
    json.dump(out, open(a.out, "w"), indent=1)
    print(f"{len(out)} URLs from {len(seen)} sitemap file(s) -> {a.out}")
    if not out:
        print("No sitemap found. Use crawl_site.py to build the URL list from internal links instead.", file=sys.stderr)
        sys.exit(2)
