import os, json, hashlib
import feedparser
import httpx
from datetime import datetime, timezone
from database import get_connection
from core.tripwire import run_tripwire

RSS_FEEDS = [
    ("https://feeds.reuters.com/reuters/businessNews", "reuters_rss"),
    ("https://feeds.reuters.com/reuters/technologyNews", "reuters_rss"),
    ("https://news.google.com/rss/search?q=layoffs+acquisition+merger+partnership&hl=en-US&gl=US&ceid=US:en", "google_news"),
    ("https://news.google.com/rss/search?q=nvidia+apple+meta+microsoft+AI+earnings&hl=en-US&gl=US&ceid=US:en", "google_news"),
    ("https://news.google.com/rss/search?q=semiconductor+quantum+computing+chip+stocks&hl=en-US&gl=US&ceid=US:en", "google_news"),
    ("https://news.google.com/rss/search?q=insider+buying+SEC+filing+hedge+fund&hl=en-US&gl=US&ceid=US:en", "google_news"),
    ("https://news.google.com/rss/search?q=stock+market+investing+earnings+beat&hl=en-US&gl=US&ceid=US:en", "google_news"),
]

NEWS_API_KEY = os.getenv("NEWS_API_KEY", "")
NEWS_API_URL = "https://newsapi.org/v2/everything"
NEWS_API_QUERIES = [
    "layoffs OR restructuring OR acquisition OR merger",
    "nvidia OR semiconductor OR AI chip OR quantum computing",
    "insider buying OR SEC filing OR earnings beat OR earnings miss",
]

def _url_hash(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()

def _already_processed(url: str) -> bool:
    conn = get_connection()
    row = conn.execute(
        "SELECT url FROM processed_urls WHERE url = ?", (_url_hash(url),)
    ).fetchone()
    conn.close()
    return row is not None

def _mark_processed(url: str):
    conn = get_connection()
    conn.execute(
        "INSERT OR IGNORE INTO processed_urls (url) VALUES (?)", (_url_hash(url),)
    )
    conn.commit()
    conn.close()

def _save_event(source, event_type, headline, summary, url, tripwire_result, published_at=None):
    conn = get_connection()
    conn.execute("""
        INSERT INTO events
            (source, event_type, headline, summary, url, tickers,
             raw_keywords, published_at, passed_tier1)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        source, event_type, headline[:500], (summary or "")[:1000],
        url,
        json.dumps(tripwire_result.get("tickers", [])),
        json.dumps(tripwire_result.get("keywords", [])),
        published_at,
        1 if tripwire_result["passed"] else 0,
    ))
    conn.commit()
    event_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()
    return event_id

async def scan_rss_feeds() -> list:
    """Scan all RSS feeds through the tripwire. Returns passing events."""
    passing = []
    for feed_url, source in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:20]:
                url = entry.get("link", "")
                if not url or _already_processed(url):
                    continue

                headline = entry.get("title", "")
                summary  = entry.get("summary", "") or entry.get("description", "")
                pub_date = entry.get("published", "")
                full_text = f"{headline} {summary}"

                result = run_tripwire(full_text)
                _mark_processed(url)
                event_id = _save_event(source, "news", headline, summary, url, result, pub_date)

                if result["passed"]:
                    passing.append({
                        "event_id": event_id, "source": source,
                        "headline": headline, "summary": summary,
                        "url": url, "tickers": result["tickers"],
                        "category": result["category"],
                        "score_boost": result["score_boost"],
                    })
        except Exception as e:
            print(f"[RSS] Error scanning {feed_url}: {e}")

    print(f"[News] RSS scan complete: {len(passing)} events passed tripwire")
    return passing

async def scan_newsapi() -> list:
    """Scan NewsAPI (100 req/day free). Returns passing events."""
    if not NEWS_API_KEY:
        return []

    passing = []
    async with httpx.AsyncClient(timeout=10) as client:
        for query in NEWS_API_QUERIES:
            try:
                resp = await client.get(NEWS_API_URL, params={
                    "q": query, "apiKey": NEWS_API_KEY,
                    "language": "en", "sortBy": "publishedAt", "pageSize": 10,
                })
                data = resp.json()
                for article in data.get("articles", []):
                    url = article.get("url", "")
                    if not url or _already_processed(url):
                        continue

                    headline = article.get("title", "")
                    summary  = article.get("description", "") or ""
                    pub_date = article.get("publishedAt", "")
                    full_text = f"{headline} {summary}"

                    result = run_tripwire(full_text)
                    _mark_processed(url)
                    event_id = _save_event("newsapi", "news", headline, summary, url, result, pub_date)

                    if result["passed"]:
                        passing.append({
                            "event_id": event_id, "source": "newsapi",
                            "headline": headline, "summary": summary,
                            "url": url, "tickers": result["tickers"],
                            "category": result["category"],
                            "score_boost": result["score_boost"],
                        })
            except Exception as e:
                print(f"[NewsAPI] Error: {e}")

    print(f"[NewsAPI] Scan complete: {len(passing)} events passed tripwire")
    return passing
