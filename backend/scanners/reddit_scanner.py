import os, json
from collections import Counter
from database import get_connection
from core.tripwire import run_tripwire, WATCHLIST, TICKER_PATTERN

SUBREDDITS = [
    "wallstreetbets", "stocks", "investing",
    "SecurityAnalysis", "options", "StockMarket",
    "AIstocks", "semiconductors",
]

async def scan_reddit() -> list:
    """
    Scan Reddit for ticker mention spikes and high-signal posts.
    Uses PRAW if credentials available, falls back to Reddit JSON API.
    """
    reddit_id     = os.getenv("REDDIT_CLIENT_ID", "")
    reddit_secret = os.getenv("REDDIT_CLIENT_SECRET", "")
    passing = []

    if False:  # disable PRAW until credentials are set up
        passing = await _scan_with_praw(reddit_id, reddit_secret)
    else:
        passing = await _scan_with_json_api()

    print(f"[Reddit] Scan complete: {len(passing)} posts passed tripwire")
    return passing

async def _scan_with_json_api() -> list:
    """Fallback: Reddit public JSON API, no credentials needed."""
    import httpx
    passing = []
    ticker_counts = Counter()

    async with httpx.AsyncClient(
        headers={"User-Agent": "MarketIntelBot/1.0"},
        timeout=10,
        follow_redirects=True
    ) as client:
        for sub in SUBREDDITS[:4]:  # limit to 4 on free tier
            try:
                resp = await client.get(
                    f"https://www.reddit.com/r/{sub}/hot.json?limit=25"
                )
                data = resp.json()
                posts = data.get("data", {}).get("children", [])

                for post in posts:
                    p = post.get("data", {})
                    title   = p.get("title", "")
                    selftext= p.get("selftext", "")[:500]
                    score   = p.get("score", 0)
                    url     = f"https://reddit.com{p.get('permalink', '')}"
                    upvote_ratio = p.get("upvote_ratio", 0)

                    # Only look at high-engagement posts
                    if score < 100 and upvote_ratio < 0.75:
                        continue

                    full_text = f"{title} {selftext}"
                    result = run_tripwire(full_text)

                    # Count ticker mentions for spike detection
                    for ticker in result["tickers"]:
                        ticker_counts[ticker] += 1

                    if result["passed"] and score >= 100:
                        conn = get_connection()
                        conn.execute("""
                            INSERT OR IGNORE INTO events
                                (source, event_type, headline, summary, url,
                                 tickers, raw_keywords, passed_tier1)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            f"reddit_{sub}", "reddit_post",
                            title[:500], selftext[:1000], url,
                            json.dumps(result["tickers"]),
                            json.dumps(result["keywords"]),
                            1,
                        ))
                        conn.commit()
                        event_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
                        conn.close()

                        passing.append({
                            "event_id":   event_id,
                            "source":     f"reddit_{sub}",
                            "headline":   title,
                            "summary":    f"Reddit post with {score} upvotes ({upvote_ratio*100:.0f}% upvoted). {selftext[:200]}",
                            "url":        url,
                            "tickers":    result["tickers"],
                            "category":   result["category"] or "reddit_sentiment",
                            "score_boost": min(result["score_boost"] + int(score / 100), 30),
                        })

            except Exception as e:
                print(f"[Reddit] Error scanning r/{sub}: {e}")

    # Log ticker spikes
    if ticker_counts:
        top = ticker_counts.most_common(5)
        print(f"[Reddit] Top mentions: {top}")

    return passing

async def _scan_with_praw(client_id: str, client_secret: str) -> list:
    """Full PRAW scan when credentials are available."""
    try:
        import praw
        reddit = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            user_agent=os.getenv("REDDIT_USER_AGENT", "MarketIntelBot/1.0"),
        )
        passing = []
        for sub_name in SUBREDDITS:
            try:
                sub = reddit.subreddit(sub_name)
                for post in sub.hot(limit=30):
                    if post.score < 150:
                        continue
                    full_text = f"{post.title} {post.selftext[:400]}"
                    result = run_tripwire(full_text)
                    if result["passed"]:
                        passing.append({
                            "event_id":   None,
                            "source":     f"reddit_{sub_name}",
                            "headline":   post.title,
                            "summary":    post.selftext[:500],
                            "url":        f"https://reddit.com{post.permalink}",
                            "tickers":    result["tickers"],
                            "category":   result["category"] or "reddit_sentiment",
                            "score_boost": result["score_boost"],
                        })
            except Exception as e:
                print(f"[PRAW] Error on r/{sub_name}: {e}")
        return passing
    except ImportError:
        return await _scan_with_json_api()
