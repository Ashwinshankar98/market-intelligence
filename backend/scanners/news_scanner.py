import os, json, hashlib, email.utils
import feedparser
import httpx
from datetime import datetime, timedelta
from database import get_connection
from core.tripwire import run_tripwire

# ── Age filter — ignore articles older than this ──────────────────────────────
MAX_ARTICLE_AGE_HOURS = int(os.getenv("MAX_ARTICLE_AGE_HOURS", 48))

RSS_FEEDS = [
    # General business/tech news
    ("https://feeds.reuters.com/reuters/businessNews",   "reuters_rss"),
    ("https://feeds.reuters.com/reuters/technologyNews", "reuters_rss"),

    # Hedge fund / investor moves
    ("https://news.google.com/rss/search?q=ackman+pershing+square+portfolio+bought+sold&hl=en-US&gl=US&ceid=US:en", "google_news"),
    ("https://news.google.com/rss/search?q=cathie+wood+ark+invest+bought+sold+position&hl=en-US&gl=US&ceid=US:en", "google_news"),
    ("https://news.google.com/rss/search?q=warren+buffett+berkshire+hathaway+bought+sold&hl=en-US&gl=US&ceid=US:en", "google_news"),
    ("https://news.google.com/rss/search?q=druckenmiller+soros+burry+einhorn+portfolio&hl=en-US&gl=US&ceid=US:en", "google_news"),
    ("https://news.google.com/rss/search?q=hedge+fund+13F+filing+new+position+exit&hl=en-US&gl=US&ceid=US:en", "google_news"),
    ("https://news.google.com/rss/search?q=citadel+point72+tiger+global+coatue+portfolio&hl=en-US&gl=US&ceid=US:en", "google_news"),

    # Your core sectors
    ("https://news.google.com/rss/search?q=nvidia+AMD+semiconductor+chip+AI+GPU&hl=en-US&gl=US&ceid=US:en", "google_news"),
    ("https://news.google.com/rss/search?q=quantum+computing+ionq+qbts+qubt+breakthrough&hl=en-US&gl=US&ceid=US:en", "google_news"),
    ("https://news.google.com/rss/search?q=rocket+lab+space+satellite+launch+contract&hl=en-US&gl=US&ceid=US:en", "google_news"),
    ("https://news.google.com/rss/search?q=optoelectronics+photonics+optical+interconnect+POET&hl=en-US&gl=US&ceid=US:en", "google_news"),
    ("https://news.google.com/rss/search?q=memory+chip+DRAM+NAND+micron+western+digital&hl=en-US&gl=US&ceid=US:en", "google_news"),
    ("https://news.google.com/rss/search?q=layoffs+acquisition+merger+partnership+earnings+beat&hl=en-US&gl=US&ceid=US:en", "google_news"),

    # Your specific holdings
    ("https://feeds.finance.yahoo.com/rss/2.0/headline?s=NVDA,META,GOOGL,NBIS,SNDK,MU,WDC,IONQ,RKLB,POET&region=US&lang=en-US", "yahoo_finance"),
    ("https://feeds.finance.yahoo.com/rss/2.0/headline?s=AMD,AVGO,SMCI,CRWV,IREN,APLD,QBTS,QUBT,PLTR,MSFT&region=US&lang=en-US", "yahoo_finance"),
]

NEWS_API_KEY = os.getenv("NEWS_API_KEY", "")
NEWS_API_URL = "https://newsapi.org/v2/everything"
NEWS_API_QUERIES = [
    "hedge fund portfolio bought sold position",
    "Ackman Cathie Wood Buffett Druckenmiller Burry stock",
    "nvidia semiconductor AI chip partnership acquisition",
    "quantum computing ionq breakthrough",
    "layoffs restructuring earnings beat miss",
]

def _url_hash(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()

def _already_processed(url: str) -> bool:
    conn = get_connection()
    row  = conn.execute("SELECT url FROM processed_urls WHERE url=?", (_url_hash(url),)).fetchone()
    conn.close()
    return row is not None

def _mark_processed(url: str):
    conn = get_connection()
    conn.execute("INSERT OR IGNORE INTO processed_urls (url) VALUES (?)", (_url_hash(url),))
    conn.commit()
    conn.close()

def _is_recent(pub_date_str: str, max_hours: int = MAX_ARTICLE_AGE_HOURS) -> bool:
    """Return True if article was published within max_hours. Unknown date = assume recent."""
    if not pub_date_str:
        return True
    try:
        parsed = email.utils.parsedate_to_datetime(pub_date_str)
        age    = datetime.now(parsed.tzinfo) - parsed
        return age.total_seconds() < (max_hours * 3600)
    except Exception:
        try:
            # Try ISO format (NewsAPI)
            parsed = datetime.fromisoformat(pub_date_str.replace("Z", "+00:00"))
            from datetime import timezone
            age = datetime.now(timezone.utc) - parsed
            return age.total_seconds() < (max_hours * 3600)
        except Exception:
            return True  # can't parse = assume recent

def _save_event(source, event_type, headline, summary, url, tripwire_result, published_at=None):
    conn = get_connection()
    conn.execute("""
        INSERT INTO events (source, event_type, headline, summary, url, tickers,
             raw_keywords, published_at, passed_tier1)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (source, event_type, headline[:500], (summary or "")[:1000], url,
          json.dumps(tripwire_result.get("tickers", [])),
          json.dumps(tripwire_result.get("keywords", [])),
          published_at, 1 if tripwire_result["passed"] else 0))
    conn.commit()
    event_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()
    return event_id

async def scan_rss_feeds() -> list:
    passing  = []
    skipped_old = 0
    for feed_url, source in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:20]:
                url      = entry.get("link", "")
                pub_date = entry.get("published", "")

                if not url or _already_processed(url):
                    continue

                # ── Age filter — skip old articles ────────────────────────────
                if not _is_recent(pub_date):
                    skipped_old += 1
                    _mark_processed(url)  # mark so we don't re-check
                    continue

                headline  = entry.get("title", "")
                summary   = entry.get("summary", "") or entry.get("description", "")
                full_text = f"{headline} {summary}"
                result    = run_tripwire(full_text)
                _mark_processed(url)
                event_id  = _save_event(source, "news", headline, summary, url, result, pub_date)

                if result["passed"]:
                    extra = 15 if result.get("investors") else 0
                    passing.append({
                        "event_id":    event_id,
                        "source":      source,
                        "headline":    headline,
                        "summary":     summary,
                        "url":         url,
                        "tickers":     result["tickers"],
                        "investors":   result.get("investors", []),
                        "category":    result["category"],
                        "score_boost": result["score_boost"] + extra,
                    })
        except Exception as e:
            print(f"[RSS] Error scanning {feed_url[:60]}: {e}")

    print(f"[News] RSS scan: {len(passing)} passed, {skipped_old} skipped (too old)")
    return passing

async def scan_newsapi() -> list:
    if not NEWS_API_KEY:
        return []
    passing     = []
    skipped_old = 0
    async with httpx.AsyncClient(timeout=10) as client:
        for query in NEWS_API_QUERIES:
            try:
                resp = await client.get(NEWS_API_URL, params={
                    "q":        query,
                    "apiKey":   NEWS_API_KEY,
                    "language": "en",
                    "sortBy":   "publishedAt",
                    "pageSize": 10,
                    "from":     (datetime.utcnow() - timedelta(hours=48)).strftime("%Y-%m-%dT%H:%M:%S"),
                })
                for article in resp.json().get("articles", []):
                    url      = article.get("url", "")
                    pub_date = article.get("publishedAt", "")

                    if not url or _already_processed(url):
                        continue

                    if not _is_recent(pub_date):
                        skipped_old += 1
                        _mark_processed(url)
                        continue

                    headline = article.get("title", "")
                    summary  = article.get("description", "") or ""
                    result   = run_tripwire(f"{headline} {summary}")
                    _mark_processed(url)
                    event_id = _save_event("newsapi", "news", headline, summary, url, result, pub_date)

                    if result["passed"]:
                        extra = 15 if result.get("investors") else 0
                        passing.append({
                            "event_id":    event_id,
                            "source":      "newsapi",
                            "headline":    headline,
                            "summary":     summary,
                            "url":         url,
                            "tickers":     result["tickers"],
                            "investors":   result.get("investors", []),
                            "category":    result["category"],
                            "score_boost": result["score_boost"] + extra,
                        })
            except Exception as e:
                print(f"[NewsAPI] Error: {e}")

    print(f"[NewsAPI] Scan: {len(passing)} passed, {skipped_old} skipped (too old)")
    return passing