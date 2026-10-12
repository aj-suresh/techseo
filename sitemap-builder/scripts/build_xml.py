#!/usr/bin/env python3
"""Write a clean sitemap.xml from an audit, and explain every URL left out.

Usage: build_xml.py urls.json audit.json -o sitemap.xml [--extra extra.txt] [--exclude-pattern REGEX ...]
                    [--drop-file report/excluded.tsv] [--keep-lastmod]

Keeps a URL only if it returned 200, is not noindex, and its canonical (if any) points to itself.
hreflang alternates are kept only if the alternate is also kept, and only when a URL has 2+ left
(a lone self-reference is noise). --extra adds URLs (one per line) that exist live but were missing
from the old sitemap; they must pass the same audit, so audit them first. Splits into
sitemap-N.xml plus sitemap-index.xml past 50,000 URLs. Stdlib only.
"""
import argparse, json, os, re
from xml.sax.saxutils import escape

def norm(u):
    return re.sub(r"^(https?://[^/]+)$", r"\1/", u.strip())

def same(a, b):
    return a.rstrip("/") == b.rstrip("/")

def verdict(a, patterns):
    if a["error"]:
        return "unreachable: " + a["error"]
    if a["status"] != 200:
        return f"status {a['status']}" + (f" -> {a['redirect']}" if a["redirect"] else "")
    if "noindex" in a["robots"].lower():
        return "noindex"
    if a["soft404"]:
        return "soft 404 (200 with not-found title)"
    if a["canonical"] and not same(a["canonical"], a["url"]):
        return "canonical points elsewhere: " + a["canonical"]
    for p in patterns:
        if re.search(p, a["url"]):
            return "matches exclude pattern " + p
    return ""

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("urls"); ap.add_argument("audit", help="audit.json, or - to skip the audit and keep every URL")
    ap.add_argument("-o", "--out", default="sitemap.xml")
    ap.add_argument("--extra")
    ap.add_argument("--exclude-pattern", action="append", default=[])
    ap.add_argument("--drop-file")
    ap.add_argument("--keep-lastmod", action="store_true")
    a = ap.parse_args()
    recs = json.load(open(a.urls))
    audit = {} if a.audit == "-" else {norm(r["url"]): r for r in json.load(open(a.audit))}
    if a.extra:
        have = {norm(r["loc"]) for r in recs}
        for l in open(a.extra):
            if l.strip() and norm(l) not in have:
                recs.append({"loc": l.strip(), "lastmod": None, "alternates": []})
    keep, dropped = [], []
    for r in recs:
        au = audit.get(norm(r["loc"]))
        v = ("" if a.audit == "-" else "not audited") if not au else verdict(au, a.exclude_pattern)
        (dropped if v else keep).append((r, v))
    kept = {norm(r["loc"]) for r, _ in keep}
    entries = []
    for r, _ in keep:
        alts = [(h, norm(u)) for h, u in r["alternates"] if norm(u) in kept]
        if len(alts) < 2:
            alts = []
        x = f"  <url>\n    <loc>{escape(norm(r['loc']))}</loc>\n"
        if a.keep_lastmod and r.get("lastmod"):
            x += f"    <lastmod>{escape(r['lastmod'])}</lastmod>\n"
        x += "".join(f'    <xhtml:link rel="alternate" hreflang="{escape(h)}" href="{escape(u)}"/>\n' for h, u in alts)
        entries.append(x + "  </url>")
    head = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">\n'
    if len(entries) <= 50000:
        open(a.out, "w").write(head + "\n".join(entries) + "\n</urlset>\n")
        print(f"{len(entries)} URLs -> {a.out}")
    else:
        base = os.path.splitext(a.out)[0]
        names = []
        for i in range(0, len(entries), 50000):
            n = f"{base}-{i // 50000}.xml"; names.append(os.path.basename(n))
            open(n, "w").write(head + "\n".join(entries[i:i + 50000]) + "\n</urlset>\n")
        root = re.match(r"(https?://[^/]+)", norm(keep[0][0]["loc"])).group(1)
        open(os.path.join(os.path.dirname(a.out) or ".", "sitemap-index.xml"), "w").write(
            '<?xml version="1.0" encoding="UTF-8"?>\n<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' +
            "".join(f"  <sitemap><loc>{root}/{n}</loc></sitemap>\n" for n in names) + "</sitemapindex>\n")
        print(f"{len(entries)} URLs split across {len(names)} files + sitemap-index.xml")
    if a.drop_file:
        with open(a.drop_file, "w") as f:
            f.write("url\treason\n" + "".join(f"{r['loc']}\t{v}\n" for r, v in dropped))
    print(f"{len(dropped)} excluded" + (f" (see {a.drop_file})" if a.drop_file else ""))
    for r, v in dropped[:15]:
        print("  -", r["loc"], "|", v)
