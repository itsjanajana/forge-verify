import re
from urllib.parse import quote_plus

import feedparser
import requests

HEADERS = {"User-Agent": "Mozilla/5.0 (Forge Verify hackathon prototype)"}

# tier = how much we trust this kind of source as evidence
FEEDS = [
    {
        "url": "https://news.google.com/rss/search?q=government+scheme+OR+notification+OR+policy+India&hl=en-IN&gl=IN&ceid=IN:en",
        "source": "Google News",
        "tier": "Aggregator",
    },
    {
        "url": "https://www.thehindu.com/news/national/feeder/default.rss",
        "source": "The Hindu",
        "tier": "Major outlet",
    },
    {
        # PIB press releases, English. Confirm/change at https://www.pib.gov.in/ViewRss.aspx
        "url": "https://pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=3",
        "source": "PIB",
        "tier": "Official",
    },
]


def clean(text):
    return re.sub(r"<[^>]+>", "", text or "").strip()


def _parse(url):
    """Fetch with a timeout; fall back to feedparser's own fetch if requests fails."""
    try:
        r = requests.get(url, timeout=8, headers=HEADERS)
        r.raise_for_status()
        return feedparser.parse(r.content)
    except Exception:
        return feedparser.parse(url)


def _to_doc(e, source, tier):
    return {
        "title": clean(e.get("title", "")),
        "summary": clean(e.get("summary", "")),
        "link": e.get("link", ""),
        "published": e.get("published", ""),
        "source": source,
        "tier": tier,
    }


def fetch_docs(limit=30):
    docs = []
    for feed in FEEDS:
        try:
            parsed = _parse(feed["url"])
            for e in parsed.entries[:limit]:
                docs.append(_to_doc(e, feed["source"], feed["tier"]))
        except Exception as ex:
            print("feed failed:", feed["source"], ex)
    return docs


def search_news(query, limit=10):
    """Live Google News RSS search built from one assertion's keywords."""
    url = (
        "https://news.google.com/rss/search?q="
        f"{quote_plus(query)}&hl=en-IN&gl=IN&ceid=IN:en"
    )
    try:
        parsed = _parse(url)
        return [_to_doc(e, "Google News", "Aggregator") for e in parsed.entries[:limit]]
    except Exception as ex:
        print("live search failed:", str(ex)[:100])
        return []


if __name__ == "__main__":
    docs = fetch_docs()
    print(f"fetched {len(docs)} documents")
    for src in {d["source"] for d in docs}:
        print(src, sum(1 for d in docs if d["source"] == src))
    for d in docs[:5]:
        print(f"- [{d['source']} | {d['tier']}] {d['title'][:80]}")
