#!/usr/bin/env python3
"""Compare two sitemap sources (XML files or URLs, indexes followed) and print added / removed URLs.
Usage: diff_sitemaps.py OLD NEW [-o diff.md]   — use for update runs to say what changed."""
import argparse, json, os, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))

def load(src):
    if os.path.exists(src):
        import xml.etree.ElementTree as ET
        root = ET.parse(src).getroot()
        return {e.text.strip().rstrip("/") for e in root.iter() if e.tag.endswith("}loc") and e.text}
    t = tempfile.mktemp(suffix=".json")
    subprocess.run([sys.executable, os.path.join(HERE, "fetch_sitemap.py"), src, "-o", t], check=True, stdout=subprocess.DEVNULL)
    return {r["loc"].rstrip("/") for r in json.load(open(t))}

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("old"); ap.add_argument("new"); ap.add_argument("-o")
    a = ap.parse_args()
    o, n = load(a.old), load(a.new)
    add, rem = sorted(n - o), sorted(o - n)
    out = f"# Sitemap diff\n\nOld {len(o)} URLs, new {len(n)} URLs. Added {len(add)}, removed {len(rem)}.\n\n## Added\n" + \
          "".join(f"- {u}\n" for u in add) + "\n## Removed\n" + "".join(f"- {u}\n" for u in rem)
    print(out) if not a.o else open(a.o, "w").write(out)
