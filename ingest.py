import feedparser
import urllib.parse

FEEDS = [
    {"url": "https://pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=1",
     "source": "PIB", "tier": "Official"},
    {"url": "https://www.thehindu.com/news/national/feeder/default.rss",
     "source": "The Hindu", "tier": "Major outlet"},
    {"url": "https://news.google.com/rss/search?q=government+scheme+OR+notification+OR+policy&hl=en-IN&gl=IN&ceid=IN:en",
     "source": "Google News", "tier": "Aggregator"},
]

def fetch_docs(extra_query=None, limit=60):
    feeds = list(FEEDS)
    if extra_query:
        q = urllib.parse.quote_plus(extra_query)
        feeds.insert(0, {
            "url": f"https://news.google.com/rss/search?q={q}&hl=en-IN&gl=IN&ceid=IN:en",
            "source": "Google News (search)", "tier": "Aggregator",
        })
    docs = []
    for f in feeds:
        try:
            parsed = feedparser.parse(f["url"])
            for e in parsed.entries:
                docs.append({
                    "title": e.get("title", ""),
                    "summary": e.get("summary", ""),
                    "link": e.get("link", ""),
                    "source": f["source"],
                    "tier": f["tier"],
                })
        except Exception as ex:
            print(f"feed failed {f['source']}:", str(ex)[:80])
    return docs[:limit]