import os, json, hashlib, email.utils, asyncio
import feedparser
import httpx
from datetime import datetime, timedelta
from database import get_connection
from core.tripwire import run_tripwire

# Browser-like UA avoids Google News rate-limiting feedparser's default UA
_FEEDPARSER_UA = (
    "Mozilla/5.0 (compatible; MarketIntelBot/1.0; +https://github.com/Ashwinshankar98/market-intelligence)"
)

# ── Age filter — ignore articles older than this ──────────────────────────────
MAX_ARTICLE_AGE_HOURS = int(os.getenv("MAX_ARTICLE_AGE_HOURS", 48))

RSS_FEEDS = [
    # General business/tech news (Reuters deprecated — replaced with CNBC + Google News)
    ("https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=15839135", "cnbc_rss"),
    ("https://www.cnbc.com/id/19854910/device/rss/rss.html", "cnbc_rss"),
    ("https://news.google.com/rss/search?q=stock+market+earnings+merger+acquisition+deal&hl=en-US&gl=US&ceid=US:en", "google_news"),
    ("https://news.google.com/rss/search?q=technology+stocks+AI+semiconductor+chip+deal&hl=en-US&gl=US&ceid=US:en", "google_news"),

    # Hedge fund / investor moves (split large queries to avoid rate-limiting)
    ("https://news.google.com/rss/search?q=ackman+pershing+square+portfolio+bought+sold&hl=en-US&gl=US&ceid=US:en", "google_news"),
    ("https://news.google.com/rss/search?q=cathie+wood+ark+invest+bought+sold+position&hl=en-US&gl=US&ceid=US:en", "google_news"),
    ("https://news.google.com/rss/search?q=warren+buffett+berkshire+hathaway+bought+sold&hl=en-US&gl=US&ceid=US:en", "google_news"),
    ("https://news.google.com/rss/search?q=druckenmiller+duquesne+portfolio+position&hl=en-US&gl=US&ceid=US:en", "google_news"),
    ("https://news.google.com/rss/search?q=soros+burry+einhorn+loeb+portfolio+stake&hl=en-US&gl=US&ceid=US:en", "google_news"),
    ("https://news.google.com/rss/search?q=hedge+fund+13F+filing+new+position+exit&hl=en-US&gl=US&ceid=US:en", "google_news"),
    ("https://news.google.com/rss/search?q=citadel+point72+tiger+global+coatue+portfolio&hl=en-US&gl=US&ceid=US:en", "google_news"),
    ("https://news.google.com/rss/search?q=elliott+management+icahn+third+point+activist&hl=en-US&gl=US&ceid=US:en", "google_news"),

    # Your core sectors
    ("https://news.google.com/rss/search?q=nvidia+AMD+semiconductor+chip+AI+GPU&hl=en-US&gl=US&ceid=US:en", "google_news"),
    ("https://news.google.com/rss/search?q=quantum+computing+ionq+qbts+qubt+breakthrough&hl=en-US&gl=US&ceid=US:en", "google_news"),
    ("https://news.google.com/rss/search?q=rocket+lab+space+satellite+launch+contract&hl=en-US&gl=US&ceid=US:en", "google_news"),
    ("https://news.google.com/rss/search?q=optoelectronics+photonics+optical+interconnect+POET&hl=en-US&gl=US&ceid=US:en", "google_news"),
    ("https://news.google.com/rss/search?q=memory+chip+DRAM+NAND+micron+western+digital&hl=en-US&gl=US&ceid=US:en", "google_news"),
    ("https://news.google.com/rss/search?q=rare+earth+critical+minerals+mp+materials&hl=en-US&gl=US&ceid=US:en", "google_news"),
    ("https://news.google.com/rss/search?q=layoffs+acquisition+merger+partnership+earnings+beat&hl=en-US&gl=US&ceid=US:en", "google_news"),

    # Your specific holdings
    ("https://feeds.finance.yahoo.com/rss/2.0/headline?s=NVDA,META,GOOGL,NBIS,SNDK,MU,WDC,IONQ,RKLB,POET&region=US&lang=en-US", "yahoo_finance"),
    ("https://feeds.finance.yahoo.com/rss/2.0/headline?s=AMD,AVGO,SMCI,CRWV,IREN,APLD,QBTS,QUBT,PLTR,MSFT&region=US&lang=en-US", "yahoo_finance"),
    ("https://feeds.finance.yahoo.com/rss/2.0/headline?s=TSLA,SOFI,HOOD,GLW,AMKR,KLIC,TEM,DRAM,MRAM,NFLX&region=US&lang=en-US", "yahoo_finance"),
]

NEWS_API_KEY = os.getenv("NEWS_API_KEY", "")
NEWS_API_URL = "https://newsapi.org/v2/everything"
NEWS_API_QUERIES = [
    "hedge fund portfolio bought sold position",
    "Ackman Cathie Wood Buffett Druckenmiller Burry stock",
    "nvidia semiconductor AI chip partnership acquisition",
    "quantum computing ionq breakthrough",
    "layoffs restructuring earnings beat miss",
    "13F filing institutional investor new stake",
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
            parsed = datetime.fromisoformat(pub_date_str.replace("Z", "+00:00"))
            from datetime import timezone
            age = datetime.now(timezone.utc) - parsed
            return age.total_seconds() < (max_hours * 3600)
        except Exception:
            return True  # can't parse = assume recent

def _headline_is_stale(headline: str) -> bool:
    """
    Detect old articles by looking for past quarter/year patterns in headline.
    Catches undated RSS articles that slip through the date filter.
    e.g. 'Q4 2025', 'Q3 2025', 'Q1 2025', 'First Quarter 2025'
    """
    import re
    from datetime import date
    current_year = date.today().year
    current_q    = (date.today().month - 1) // 3 + 1

    # Flag any quarter from a past year
    past_year_pattern = re.compile(
        r'\bQ[1-4]\s*20(?:2[0-4])\b|\b20(?:2[0-4])\s*Q[1-4]\b',
        re.IGNORECASE
    )
    if past_year_pattern.search(headline):
        return True

    # Flag current year but past quarters
    # e.g. if we're in Q2 2026, flag "Q1 2026" articles
    current_year_old_q = re.compile(
        r'\bQ([1-4])\s*' + str(current_year) + r'\b|\b' + str(current_year) + r'\s*Q([1-4])\b',
        re.IGNORECASE
    )
    for match in current_year_old_q.finditer(headline):
        q_num = int(match.group(1) or match.group(2))
        if q_num < current_q:
            return True

    # Flag "First/Second/Third/Fourth Quarter YEAR" patterns
    quarter_words = {
        "first": 1, "second": 2, "third": 3, "fourth": 4
    }
    word_q_pattern = re.compile(
        r'\b(first|second|third|fourth)\s+quarter\s+(\d{4})\b',
        re.IGNORECASE
    )
    for match in word_q_pattern.finditer(headline):
        q_word = match.group(1).lower()
        year   = int(match.group(2))
        q_num  = quarter_words.get(q_word, 0)
        if year < current_year or (year == current_year and q_num < current_q):
            return True

    return False

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
    passing      = []
    skipped_old  = 0
    total_seen   = 0   # fetched from feeds
    already_done = 0   # already in processed_urls

    last_google = 0  # track last Google News fetch time for staggering

    for feed_url, source in RSS_FEEDS:
        try:
            # Stagger Google News fetches by 1s to avoid burst rate-limiting
            if "news.google.com" in feed_url:
                now = asyncio.get_event_loop().time()
                gap = now - last_google
                if gap < 1.0:
                    await asyncio.sleep(1.0 - gap)
                last_google = asyncio.get_event_loop().time()

            feed       = feedparser.parse(feed_url, agent=_FEEDPARSER_UA)
            n_entries  = len(feed.entries)
            if n_entries == 0:
                print(f"[RSS] Empty/unreachable: {feed_url[8:60]}")
                continue

            for entry in feed.entries[:30]:          # raised from 20 → 30
                url      = entry.get("link", "")
                headline = entry.get("title", "")
                summary  = entry.get("summary", "") or entry.get("description", "")
                pub_date = entry.get("published", "")

                if not url:
                    continue

                total_seen += 1

                if _already_processed(url):
                    already_done += 1
                    continue

                # ── Age filter ────────────────────────────────────────────────
                if not _is_recent(pub_date):
                    skipped_old += 1
                    _mark_processed(url)
                    continue

                # ── Headline stale check (undated old quarterly articles) ──────
                if _headline_is_stale(headline):
                    skipped_old += 1
                    _mark_processed(url)
                    continue

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
            print(f"[RSS] Error scanning {feed_url[8:60]}: {e}")

    print(f"[News] RSS: {len(passing)} passed | {skipped_old} too old | {already_done} already seen | {total_seen} total fetched")
    return passing

async def scan_newsapi() -> list:
    if not NEWS_API_KEY:
        print("[NewsAPI] No API key — skipping")
        return []
    passing      = []
    skipped_old  = 0
    already_done = 0
    total_seen   = 0
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

                    if not url:
                        continue

                    total_seen += 1

                    if _already_processed(url):
                        already_done += 1
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
                print(f"[NewsAPI] Error on '{query[:40]}': {e}")

    print(f"[NewsAPI]: {len(passing)} passed | {skipped_old} too old | {already_done} already seen | {total_seen} total fetched")
    return passing