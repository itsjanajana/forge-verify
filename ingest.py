import feedparser
import re

FEEDS = [
    {"url": "https://news.google.com/rss/search?q=government+scheme+OR+notification+OR+policy+India&hl=en-IN&gl=IN&ceid=IN:en", "source": "Google News"},
    {"url": "https://www.thehindu.com/news/national/feeder/default.rss", "source": "The Hindu"},
]

def clean(text):
    return re.sub(r"<[^>]+>", "", text or "").strip()

def fetch_docs(limit=30):
    docs = []
    for feed in FEEDS:
        try:
            parsed = feedparser.parse(feed["url"])
            for e in parsed.entries[:limit]:
                docs.append({
                    "title": clean(e.get("title", "")),
                    "summary": clean(e.get("summary", "")),
                    "link": e.get("link", ""),
                    "published": e.get("published", ""),
                    "source": feed["source"],
                })
        except Exception as ex:
            print("feed failed:", feed["source"], ex)
    return docs

if __name__ == "__main__":
    docs = fetch_docs()
    print(f"fetched {len(docs)} documents")
    for d in docs[:5]:
        print(f"- [{d['source']}] {d['title'][:80]}")

