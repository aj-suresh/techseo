#!/usr/bin/env python3
"""Render the interactive site map page (self-contained HTML) from sitemap URLs + audit (+ optional Search Console data).

Usage: build_tree.py urls.json audit.json -o site-map.html --site example.com
          [--gsc gsc.json] [--window "2025-07-01 to 2026-10-12"] [--legacy-audit legacy_audit.json]

--gsc: JSON list of {"page": url, "clicks": n, "impressions": n} (Search Console page-level rows).
       URLs are matched ignoring trailing slashes. Without it, click columns show 0.
--legacy-audit: audit.json of GSC pages that are NOT in the sitemap (run audit_urls.py on them).
       They become a "Not in sitemap" group, each tagged 404 / "301 -> target" / etc.
Language sections are detected from the hreflang codes in the sitemap. Stdlib only.
"""
import argparse, json, os, re, datetime
from urllib.parse import urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(HERE, "..", "assets", "template.html")

def key(u): return u.rstrip("/")

def mk(name):
    return {"n": name, "k": "seg", "u": None, "c": 0, "i": 0, "p": 0, "f": [], "ch": [], "g": None}

def insert(root, url, langs, own, status):
    segs = [s for s in urlparse(url).path.split("/") if s]
    node, lang = root, None
    for k, s in enumerate(segs):
        if k == 0 and s in langs:
            lang = s
        nm = "/" + s
        nxt = next((c for c in node["ch"] if c["n"] == nm), None)
        if not nxt:
            nxt = mk(nm); node["ch"].append(nxt)
        if lang:
            nxt["l"] = lang
        node = nxt
    node["u"] = url; node["own"] = own
    if status:
        node["s"] = status

def roll(n, grp):
    n["g"] = grp
    own = n.pop("own", None)
    n["c"], n["i"], n["p"] = (own[0], own[1], 1) if own else (0, 0, 0)
    for ch in n["ch"]:
        roll(ch, grp); n["c"] += ch["c"]; n["i"] += ch["i"]; n["p"] += ch["p"]
    n["ch"].sort(key=lambda x: (-x["c"], -x["p"], x["n"]))

def group(name, gid, urls, langs, info, host):
    h = mk(urlparse(host).netloc); h["k"] = "host"
    for u in urls:
        insert(h, u, langs, *info(u))
    if urlparse(host).path in ("", "/") and any(urlparse(u).path in ("", "/") for u in urls):
        pass
    roll(h, gid)
    h["u"] = host + "/" if h["p"] and any(urlparse(u).path in ("", "/") for u in urls) else None
    return {"n": name, "k": "group", "u": None, "ch": [h], "f": [], "g": gid, "c": h["c"], "i": h["i"], "p": h["p"]}

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("urls"); ap.add_argument("audit", help="audit.json, or - to skip")
    ap.add_argument("-o", "--out", default="site-map.html")
    ap.add_argument("--site", required=True)
    ap.add_argument("--gsc"); ap.add_argument("--window", default="")
    ap.add_argument("--legacy-audit")
    a = ap.parse_args()
    recs = json.load(open(a.urls))
    audit = {} if a.audit == "-" else {key(r["url"]): r for r in json.load(open(a.audit))}
    gsc = {}
    if a.gsc:
        for r in json.load(open(a.gsc)):
            k = key(r["page"]); g = gsc.setdefault(k, [0, 0])
            g[0] += r.get("clicks", 0); g[1] += r.get("impressions", 0)
    langs = {h for r in recs for h, _ in r["alternates"] if h not in ("x-default",)}
    langs = {l for l in langs if re.fullmatch(r"[a-z]{2}(-[A-Za-z]{2,4})?", l)}
    # default language = the one whose alternates have no path prefix
    first_segs = {s for r in recs for s in [([x for x in urlparse(r['loc']).path.split('/') if x] or [''])[0]]}
    langs = {l for l in langs if l in first_segs}
    host = "https://" + a.site

    def info_sm(u):
        g = gsc.get(key(u), [0, 0]); au = audit.get(key(u))
        s = ""
        if au:
            if "noindex" in au["robots"].lower(): s = "noindex"
            elif au["status"] != 200: s = str(au["status"])
            elif au["soft404"]: s = "soft 404"
            elif au["canonical"] and key(au["canonical"]) != key(u): s = "canonical elsewhere"
        if not s and a.gsc and key(u) not in gsc and urlparse(u).path.split("/")[1:2] not in [[l] for l in langs]:
            s = "no search data"
        return (g[0], g[1]), s

    sm_urls = [r["loc"] for r in recs]
    groups = [group("Sitemap", "marketing", sm_urls, langs, info_sm, host)]
    meta = {"site": a.site, "window": a.window, "checked": datetime.date.today().isoformat(),
            "languages": sorted(langs), "default_lang": "en", "hosts": 1}
    flagged = sum(1 for u in sm_urls if info_sm(u)[1] in ("noindex", "soft 404", "canonical elsewhere") or info_sm(u)[1].isdigit())
    legacy = []
    if a.legacy_audit:
        la = json.load(open(a.legacy_audit)); have = {key(u) for u in sm_urls}
        la = [r for r in la if key(r["url"]) not in have]
        def info_l(u):
            r = next(x for x in la if x["url"] == u); g = gsc.get(key(u), [0, 0])
            if str(r["status"]).startswith("30"):
                t = re.sub(r"^https?://[^/]+", "", r["redirect"]) if r["redirect"].startswith("http" + "://" + a.site) or r["redirect"].startswith("https://" + a.site) else r["redirect"]
                s = "301 → " + (t or "/")
            elif r["status"] == 200:
                s = "200" + (" noindex" if "noindex" in r["robots"].lower() else "")
            else: s = str(r["status"])
            return (g[0], g[1]), s
        legacy = [r["url"] for r in la]
        if legacy:
            groups.append(group("Not in sitemap (seen in Search Console)", "legacy", legacy, langs, info_l, host))
            groups[-1]["ch"][0]["u"] = None
    root = {"n": a.site, "k": "root", "u": None, "f": [], "ch": groups,
            "c": sum(g["c"] for g in groups), "i": sum(g["i"] for g in groups), "p": sum(g["p"] for g in groups)}
    dead = sum(1 for u in legacy if info_l(u)[1][:3] in ("404", "410")) if legacy else 0
    meta["pages"] = root["p"]
    meta["lede"] = (f"Built from the site's XML sitemap (checked {meta['checked']})" +
                    (f", with Google Search clicks from {a.window} alongside" if a.gsc else "") +
                    (". URLs Google still lists but the sitemap omits are in their own group." if legacy else "."))
    meta["stats"] = [["Pages mapped", f"{root['p']:,}"], ["In live sitemap", f"{len(sm_urls):,}"],
                     ["Language sections", len(langs) + 1], ["Flagged in sitemap", flagged, "warn"]] if audit else [["Pages mapped", f"{root['p']:,}"], ["In sitemap", f"{len(sm_urls):,}"], ["Language sections", len(langs) + 1]]
    if legacy:
        meta["stats"].append([f"Not in sitemap ({dead} dead)", f"{len(legacy):,}", "warn"])
    note = ("Pages come from the live sitemap, so pages with no search traffic still appear. Flags: noindex = listed in the sitemap but tells Google not to index it; "
            "404 or 301 on a not-in-sitemap URL is what it returns today." + (" Clicks are Google Search clicks for the period shown." if a.gsc else ""))
    html = open(TEMPLATE).read()
    html = html.replace("__DATA__", json.dumps({"tree": root, "meta": meta}, separators=(",", ":")).replace("</", "<\\/"))
    html = html.replace("__SITE__", a.site).replace("__NOTE__", note)
    open(a.out, "w").write(html)
    print(f"{root['p']} pages, {len(sm_urls)} in sitemap, {flagged} flagged, {len(legacy)} legacy -> {a.out}")
