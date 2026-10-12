#!/usr/bin/env python3
"""Build a URL list by following internal links, for sites with no usable XML sitemap.

Usage: crawl_site.py https://example.com -o urls.json [--max-pages 500] [--delay 1.0]

Breadth-first from the homepage, same host only, HTML pages only. Honors robots.txt
(Disallow rules and Crawl-delay) and identifies itself, so it is safe to point at a
competitor's site. Output matches fetch_sitemap.py (loc, lastmod, alternates, source) so
the rest of the pipeline is unchanged. The result is a floor, not a full inventory: pages
reachable only through search, forms or JavaScript menus will be missed. Stdlib only.
"""
import argparse, json, re, time, urllib.request, urllib.robotparser
from collections import deque
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse, urldefrag

UA = "Mozilla/5.0 (sitemap-builder crawler)"
SKIP = re.compile(r"\.(png|jpe?g|gif|webp|svg|ico|pdf|zip|css|js|mp4|mp3|woff2?|xml|json|txt)(\?|$)", re.I)

class Links(HTMLParser):
    def __init__(self):
        super().__init__(); self.hrefs = []; self.alts = []
    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if tag == "a" and d.get("href"):
            self.hrefs.append(d["href"])
        elif tag == "link" and d.get("rel") == "alternate" and d.get("hreflang") and d.get("href"):
            self.alts.append([d["hreflang"], d["href"]])

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("site"); ap.add_argument("-o", "--out", default="urls.json")
    ap.add_argument("--max-pages", type=int, default=500)
    ap.add_argument("--delay", type=float, default=1.0)
    a = ap.parse_args()
    root = a.site.rstrip("/"); host = urlparse(root).netloc.lower().removeprefix("www.")
    rp = urllib.robotparser.RobotFileParser(root + "/robots.txt")
    try: rp.read()
    except Exception: pass
    if rp.disallow_all:
        print("robots.txt forbids crawling (or answered 401/403 to bots). Not crawling. Use wayback_urls.py or web search instead.")
        raise SystemExit(3)
    delay = max(a.delay, rp.crawl_delay(UA) or 0)
    seen, out, q = {root + "/"}, [], deque([root + "/"])
    while q and len(out) < a.max_pages:
        url = q.popleft()
        if rp.default_entry is not None or rp.entries:
            if not rp.can_fetch(UA, url): continue
        try:
            time.sleep(delay)
            r = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=30)
            if "html" not in r.headers.get("Content-Type", ""): continue
            final = r.geturl()
            if urlparse(final).netloc.lower().removeprefix("www.") != host: continue
            p = Links(); p.feed(r.read(600000).decode("utf-8", "replace"))
        except Exception:
            continue
        out.append({"loc": final, "lastmod": None, "alternates": [[h, urljoin(final, u)] for h, u in p.alts], "source": "crawl"})
        for h in p.hrefs:
            u = urldefrag(urljoin(final, h))[0]
            pu = urlparse(u)
            if pu.scheme not in ("http", "https") or pu.netloc.lower().removeprefix("www.") != host: continue
            if SKIP.search(pu.path) or pu.query: continue
            if u not in seen:
                seen.add(u); q.append(u)
    json.dump(out, open(a.out, "w"), indent=1)
    print(f"{len(out)} pages crawled ({len(q)} discovered but not visited) -> {a.out}")

main()
