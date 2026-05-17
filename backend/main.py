import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

load_dotenv()

from database import init_db
from routers.api import router as api_router
from routers.lookup import router as lookup_router

app = FastAPI(
    title="Market Intelligence API",
    description="Event-driven market intelligence with options recommendations",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)
app.include_router(lookup_router)

scheduler = AsyncIOScheduler(timezone="US/Eastern")

@app.on_event("startup")
async def startup():
    init_db()

    from core.orchestrator import run_full_scan, run_breaking_scan, run_weekly_synthesis

    scan_interval     = int(os.getenv("SCAN_INTERVAL_MINUTES", 60))
    breaking_interval = int(os.getenv("BREAKING_SCAN_MINUTES", 15))

    scheduler.add_job(
        run_full_scan,
        trigger=IntervalTrigger(minutes=scan_interval),
        id="full_scan",
        name="Hourly full scan",
        replace_existing=True,
    )

    scheduler.add_job(
        run_breaking_scan,
        trigger=IntervalTrigger(minutes=breaking_interval),
        id="breaking_scan",
        name="Breaking news tripwire",
        replace_existing=True,
    )

    scheduler.add_job(
        run_weekly_synthesis,
        trigger=CronTrigger(day_of_week="sun", hour=20, minute=0, timezone="US/Eastern"),
        id="weekly_synthesis",
        name="Sunday weekly synthesis",
        replace_existing=True,
    )

    scheduler.start()
    print("[App] Market Intelligence started")
    print(f"[App] Full scan every {scan_interval} min · Breaking scan every {breaking_interval} min")
    print("[App] Weekly synthesis every Sunday 8pm ET")

    import asyncio
    asyncio.create_task(run_full_scan())

@app.on_event("shutdown")
async def shutdown():
    scheduler.shutdown()

@app.get("/health")
def health():
    jobs = [{"id": j.id, "next_run": str(j.next_run_time)} for j in scheduler.get_jobs()]
    return {"status": "ok", "version": "1.0.0", "scheduled_jobs": jobs}

@app.get("/")
def root():
    return {
        "message": "Market Intelligence API",
        "docs":    "/docs",
        "health":  "/health",
        "signals": "/api/signals",
        "stats":   "/api/stats",
        "lookup":  "/api/lookup",
    }
