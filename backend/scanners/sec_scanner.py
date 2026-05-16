import json
import httpx
from database import get_connection
from core.tripwire import run_tripwire, WATCHLIST

EDGAR_BASE  = "https://efts.sec.gov/LATEST/search-index?q="
EDGAR_FULL  = "https://efts.sec.gov/LATEST/search-index?dateRange=custom&startdt={start}&enddt={end}&forms={form}"
EDGAR_AGENT = {"User-Agent": "MarketIntelBot contact@example.com"}

# Form 4 = insider trades, 8-K = material events
FORMS_TO_WATCH = ["4", "8-K"]

async def scan_sec_filings() -> list:
    """Scan SEC EDGAR for recent Form 4 and 8-K filings."""
    from datetime import datetime, timedelta
    today     = datetime.utcnow().date()
    yesterday = today - timedelta(days=1)
    passing   = []

    async with httpx.AsyncClient(headers=EDGAR_AGENT, timeout=15) as client:
        for form in FORMS_TO_WATCH:
            try:
                url = f"https://efts.sec.gov/LATEST/search-index?forms={form}&dateRange=custom&startdt={yesterday}&enddt={today}"
                resp = await client.get(url)
                data = resp.json()
                hits = data.get("hits", {}).get("hits", [])

                for hit in hits[:30]:
                    src      = hit.get("_source", {})
                    entity   = src.get("entity_name", "Unknown")
                    form_type= src.get("form_type", form)
                    filed_at = src.get("file_date", "")
                    accession= src.get("accession_no", "")
                    url_doc  = f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&filenum={accession}"

                    if form == "4":
                        headline = f"SEC Form 4: Insider transaction at {entity}"
                        summary  = f"Insider buy/sell filing for {entity}. Filed {filed_at}."
                        event_type = "insider_buy"
                    else:
                        headline = f"SEC 8-K Material Event: {entity}"
                        summary  = f"Material event filing by {entity}. Filed {filed_at}."
                        event_type = "sec_8k"

                    # Check if entity matches watchlist
                    ticker_match = any(t.upper() in entity.upper() for t in WATCHLIST)
                    full_text = f"{headline} {summary} {entity}"
                    result = run_tripwire(full_text)

                    # Form 4 always passes if it's a buy (we can't tell without parsing full doc)
                    # 8-K passes if tripwire matches or it's a major company
                    should_pass = result["passed"] or (form == "4" and ticker_match)

                    conn = get_connection()
                    conn.execute("""
                        INSERT OR IGNORE INTO events
                            (source, event_type, headline, summary, url,
                             tickers, raw_keywords, published_at, passed_tier1)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        "sec_edgar", event_type, headline, summary, url_doc,
                        json.dumps(result.get("tickers", [])),
                        json.dumps(result.get("keywords", [])),
                        filed_at, 1 if should_pass else 0,
                    ))
                    conn.commit()
                    event_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
                    conn.close()

                    if should_pass:
                        passing.append({
                            "event_id":    event_id,
                            "source":      "sec_edgar",
                            "headline":    headline,
                            "summary":     summary,
                            "url":         url_doc,
                            "tickers":     result["tickers"] or ([entity] if ticker_match else []),
                            "category":    "insider" if form == "4" else "regulatory",
                            "score_boost": 22 if form == "4" else result["score_boost"],
                        })

            except Exception as e:
                print(f"[SEC] Error scanning Form {form}: {e}")

    print(f"[SEC] Scan complete: {len(passing)} filings passed")
    return passing
