# Search Console data for the site map

Goal: `gsc.json` = `[{"page": "https://example.com/path", "clicks": 12, "impressions": 340}, ...]`.

- Use the page dimension, a window of about 16 months, and page through every row (row limits are 25,000 per call).
- Pick the property that matches the site: a domain property (`sc-domain:example.com`) covers all subdomains, a URL-prefix property covers one host.
- URL variants (trailing slash, `www`, `http`, tracking parameters, `#fragment`) show up as separate rows. Strip query strings and fragments and sum the rows before saving; `build_tree.py` already matches ignoring trailing slashes.
- Rows for other subdomains: filter to the host being mapped, or map each host separately.
- Legacy list for step 4: `gsc pages − sitemap URLs`, compared after normalising trailing slashes, written one per line.
