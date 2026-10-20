# Search discovery for aionpc.ru

## What is published

The Russian and English homepages describe the product as a free, open-source local AI workspace. Local inference has no subscription or per-token charge; model licenses, hardware, electricity and storage are separate. No access to proprietary cloud models is promised.

Five focused guides in each language cover Windows, Ubuntu, the experimental Mac build, offline AI and model selection. They contain real installer links, SHA256 commands, catalog-derived file sizes, hardware limits and links to verification evidence. Keep them useful and updated rather than generating keyword variants.

Every canonical page has a unique title/description, one H1, self-canonical, reciprocal ru/en/x-default links, Open Graph, Twitter cards and static JSON-LD. App data identifies price zero, MIT source and actual OS limitations. There are no invented ratings, reviews or endorsements. Valid software markup without real reviews does not imply Google software rich-result eligibility.

`robots.txt` allows public pages and their assets, including access by Googlebot, Yandex, Bingbot, OAI-SearchBot and PerplexityBot. API/download/model binary paths remain excluded. `sitemap.xml` contains only 12 real canonical pages and language alternates. `llms.txt` is an optional public documentation index, not a ranking factor or a guaranteed route into AI answers. No crawler receives hidden instructions or special promotional content.

## Verification and notification

Build: `python -B site/build.py`.

Audit: `python -B packaging/audit_site_seo.py --base https://aionpc.ru --report logs/seo-live-20261020.json`.

After a verified public deployment, `python -B packaging/submit_indexnow.py` submits the actual sitemap URLs once to the official global endpoint. It reads the project-local verification configuration, checks the live key file and skips an unchanged successful submission. HTTP 200 means received; 202 means received with key validation pending. Neither means indexed or ranked. Google discovery still uses normal crawling/Search Console.

Deployment remains an atomic static overlay with rollback. The VPN, DNS, firewall, app release assets and model files are outside the SEO change.

## Owner step after SEO

The owner has not yet added this domain to webmaster accounts and chose to connect them after the SEO work:

1. Sign in to [Google Search Console](https://search.google.com/search-console) in the owner's account. Add `https://aionpc.ru/` as a URL-prefix property (or use domain verification with DNS). Supply the exact verification file/meta value for deployment; do not share passwords. Submit `https://aionpc.ru/sitemap.xml` after verification.
2. Sign in to [Yandex Webmaster](https://webmaster.yandex.ru/), add `https://aionpc.ru/`, confirm ownership and submit the same sitemap.
3. Optionally use [Bing Webmaster Tools](https://www.bing.com/webmasters/) for crawl reports. No account or tracking code was fabricated by this deployment.
4. Observe actual impressions, query clicks, coverage and crawl errors. Build genuine visibility through useful release notes, documentation, user feedback and independent references. Do not buy fake links, reviews, traffic or mass-post comments.

## Primary references reviewed 2026-10-20

- [Google: AI search optimization](https://developers.google.com/search/docs/fundamentals/ai-optimization-guide)
- [Google: software app structured data](https://developers.google.com/search/docs/appearance/structured-data/software-app)
- [Yandex: sitemap requirements](https://yandex.ru/support/webmaster/ru/controlling-robot/sitemap)
- [OpenAI: search crawler](https://developers.openai.com/api/docs/bots)
- [Perplexity: crawlers](https://docs.perplexity.ai/docs/resources/perplexity-crawlers)
- [IndexNow: protocol](https://www.indexnow.org/documentation)

Indexing, a first-place ranking and inclusion in AI answers are not guaranteed. Crawler HTTP access was checked with user-agent strings; this is not proof of a real provider crawl. Network transfer timing is not a field Core Web Vitals measurement.
