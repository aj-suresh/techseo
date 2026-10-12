---
name: sitemap-builder
description: Create or update the sitemap of any website, your own or a competitor's. Reads the site's real XML sitemap (or crawls links, or uses the Internet Archive when there is none), probes URLs for status, noindex, canonical and redirects, optionally layers in Google Search Console clicks when available, then writes a clean sitemap.xml and an interactive site-map page (hosts, paths, languages, legacy URLs). Use whenever the user wants to build, refresh, audit, clean up, diff or visualise a sitemap or site structure, says "sitemap", "sitemap.xml", "site map", "map out a competitor's site", "what pages does X have", "what pages does our site have", "which URLs should be in the sitemap", "pages Google sees that we don't list", or asks to update an earlier sitemap artifact, even if they never say "XML".
---

# Sitemap builder

Produce two things for any domain, yours or a competitor's: a **clean `sitemap.xml`** that lists only pages worth indexing, and an **interactive site map** (one HTML page) that shows the whole structure, with problems flagged and, when Search Console is available, traffic. The same flow covers creating from scratch and refreshing an earlier version.

The live sitemap is the best source of what a site contains, and probing every URL is what makes the XML trustworthy: a sitemap that lists redirects, 404s or noindex pages teaches Google to distrust it. Search Console is an optional extra that ranks pages by traffic and finds dead URLs still getting clicks.

## Start by working out what you have

Ask nothing you can infer. Two facts decide the path:

- **Own site or someone else's?** A competitor's site (or any site the user does not run) means: no Search Console, no deploying the XML, gentler probing. The output is analysis, not a file to publish.
- **Is Search Console available for this domain?** Check whether the GSC tools are connected and whether the domain is a property in them. If either answer is no, skip every GSC step. The deliverables are the same, minus click counts and the not-in-sitemap group. Never make the flow depend on GSC, and never tell the user a competitor needs it.

State which mode you chose in one line, then go.

## Workflow

Work in a scratch folder. Scripts are in `scripts/` next to this file (stdlib Python, no installs). Call them by full path.

1. **Get the URL list.** Try these in order and stop at the first that yields a usable list. Say which source you used, because it determines how complete the map is.
   1. `python3 scripts/fetch_sitemap.py https://example.com -o urls.json`. Reads `robots.txt` if it exists, then tries `/sitemap.xml`, `/sitemap_index.xml`, `/sitemap-index.xml`, `/wp-sitemap.xml`. A missing `robots.txt` is fine; it just falls through to the guessed paths. Exit code 2 means none found.
   2. `python3 scripts/crawl_site.py https://example.com -o urls.json --max-pages 500`. Follows internal links from the homepage, honors `robots.txt` Disallow and Crawl-delay, waits between requests. Exit code 3 means robots.txt forbids crawling or blocks bots; respect that and move on. Pages reachable only through JavaScript menus, search or forms will be missed.
   3. `python3 scripts/wayback_urls.py example.com -o urls.json`. Asks the Internet Archive which URLs it has seen, without touching the site. It includes pages that may be gone, so audit it.
   4. Web search with `site:example.com` plus a few topical terms, and fetch the nav and footer of the homepage. Hand-assemble `urls.json` (`[{"loc": url, "lastmod": null, "alternates": []}]`). Last resort; label the result as a partial sample.

   Combine sources when one is thin (for example sitemap plus crawl), de-duplicating. The map of a site with no sitemap is always a floor, and the page and the report should say so.
2. **Audit URLs.** `python3 scripts/audit_urls.py urls.json -o audit.json`. Redirects are not followed, so a 301 is recorded as a 301. Own site: audit everything (add `--workers 24` if it is large). Someone else's site: use `--workers 3 --delay 0.5` and `--sample 100` to 300 for big sites, because hammering a third party is rude and gets you blocked. The script warns when most responses are 403/429, which means the data is unreliable; report that rather than presenting statuses as fact. Skipping the audit is allowed (`-` in place of `audit.json` below), but then nothing in the output is verified live, and the report must say that.
3. **Search Console, only if available for this domain.** Pull page-level clicks and impressions (see `references/gsc-notes.md`) into `gsc.json`. Then find URLs Google lists that the sitemap omits, write them to `legacy.txt`, and audit them with `audit_urls.py --list-file legacy.txt -o legacy.json`. This surfaces dead pages still earning clicks. Skip this step entirely for competitors.
4. **Write the XML.** `python3 scripts/build_xml.py urls.json audit.json -o sitemap.xml --drop-file excluded.tsv`. A URL stays only if it returns 200, is not noindex, is not a soft 404, and is its own canonical. hreflang alternates pointing at dropped pages are removed. Add `--exclude-pattern REGEX` for indexable but low-value pages (test, variants, thank-you); confirm with the user before excluding anything that is not noindex. `--keep-lastmod` preserves existing dates; never invent dates. For a competitor this file is a clean inventory of their indexable pages, not something to deploy.
5. **Render the site map page.** `python3 scripts/build_tree.py urls.json audit.json -o site-map.html --site example.com` and add `--gsc gsc.json --window "START to END" --legacy-audit legacy.json` only when you have them. Use `-` for the audit if you skipped it.
6. **Report.** Lead with what the user needs to decide. Own site: counts kept and dropped, reasons (`excluded.tsv`), legacy URLs with the most clicks that now 404 (redirect candidates), suspected duplicates. Competitor: how the site is organised (top sections by page count, language coverage, what they have that you might not, such as comparison pages, glossary or FAQ hubs, webinars, case studies), and how complete the map is given the source. Give file paths.

## Updating an earlier sitemap

When the user points at an earlier sitemap, artifact or XML, read it first so you build on it rather than replace it. Run the same pipeline, then `python3 scripts/diff_sitemaps.py OLD NEW` to state what was added and removed. Keep any group or section the old version had that this run cannot refresh (for example other subdomains known only from Search Console), and say it was carried over unchanged.

## Publishing the page

If an Artifact tool is available, publish `site-map.html` there. Load the artifact design guidance first if the tool asks. If publishing fails, do not loop; hand over the local HTML and the XML and say what failed. The XML is always delivered as a file, since an artifact cannot host it at the site root.

## Deploying the XML

Own sites only. You do not change the live site. Tell the user the file goes at the site root (or wherever their build generates it), that `robots.txt` should keep a `Sitemap:` line pointing to it, and that it can be submitted in Search Console. Offer to submit it with the GSC tool only if the user asks, since that is an outward-facing change. If the site generates its sitemap from code (Astro, Next, WordPress plugin), the durable fix for the excluded pages is in that config, so name the pages and reasons; hand-edited XML gets overwritten on the next build.

## Judgment calls

- Noindex, 404 and redirecting pages leave the XML. That is rule, not preference.
- Indexable but low-value pages (test, variants, thank-you, internal tools) are the user's call. List them, recommend `noindex` or exclusion, and wait.
- Multi-language sites: keep every language that passes the audit, and keep hreflang symmetrical. A page that is noindex in one language should leave the alternates of its siblings too, which the script does.
- Subdomains (docs, store, status) have their own sitemaps. Map them only from data you have, and label the source.
- Competitor sites: stay within robots.txt, keep request rates low, and describe only what is publicly reachable. Do not log in, do not bypass blocks, and do not present a partial map as complete.
- Over 50,000 URLs or 50 MB: the script splits the output and writes a `sitemap-index.xml`.

## Files

- `scripts/fetch_sitemap.py`, `crawl_site.py`, `wayback_urls.py` (get URLs); `audit_urls.py` (probe); `build_xml.py`, `build_tree.py`, `diff_sitemaps.py` (outputs)
- `assets/template.html`: page shell used by `build_tree.py`; do not hand-edit the data line
- `references/gsc-notes.md`: how to pull and shape Search Console data
