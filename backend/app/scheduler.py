from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timezone
from backend.app.run_pipeline import run_full_pipeline 

scheduler = BackgroundScheduler()

def start_scheduler():
    # Run every 3 minutes, starting immediately
    if not scheduler.running:
        scheduler.start()

    scheduler.add_job(
        run_full_pipeline,
        "interval",
        minutes=5,
        next_run_time=datetime.now(timezone.utc),  # Run immediately at startup (timezone-aware)
        max_instances=1,                  # Prevent overlapping runs
    )

