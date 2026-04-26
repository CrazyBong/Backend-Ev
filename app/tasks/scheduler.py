import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.db.database import AsyncSessionLocal
from app.tasks.cleanup_tasks import release_abandoned_locks, cleanup_database_garbage
from sqlalchemy import text

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()

async def _run_release_abandoned_locks():
    try:
        async with AsyncSessionLocal() as db:
            await release_abandoned_locks(db)
    except Exception as e:
        logger.error(f"Scheduler failed to release abandoned locks: {e}")

async def _run_cleanup_database_garbage():
    try:
        async with AsyncSessionLocal() as db:
            await cleanup_database_garbage(db)
    except Exception as e:
        logger.error(f"Scheduler failed to cleanup garbage: {e}")


async def _run_retrain_all_models():
    """Weekly job: retrain RF demand model for every active station."""
    from app.ml.training import train_station_model  # lazy import
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(text("SELECT id FROM stations WHERE is_active = true"))
            station_ids = [str(row[0]) for row in result.all()]

        logger.info("Weekly ML retraining started", extra={"station_count": len(station_ids)})
        for sid in station_ids:
            try:
                async with AsyncSessionLocal() as db:
                    status = await train_station_model(db, sid)
                logger.info("Retrain result", extra={"station_id": sid, "status": status["status"]})
            except Exception as exc:
                logger.error("Retrain failed for station",
                             extra={"station_id": sid, "error": str(exc)})
    except Exception as exc:
        logger.error(f"Weekly ML retraining job failed: {exc}")

def start_scheduler():
    """Starts the APScheduler with predefined jobs."""
    if not scheduler.running:
        # Release abandoned locks every 30 seconds
        scheduler.add_job(
            _run_release_abandoned_locks, 
            'interval', 
            seconds=30, 
            id='release_abandoned_locks', 
            replace_existing=True,
            max_instances=1
        )
        
        # Cleanup expired OTPs and JWTs every 1 hour
        scheduler.add_job(
            _run_cleanup_database_garbage, 
            'interval', 
            hours=1, 
            id='cleanup_database_garbage', 
            replace_existing=True,
            max_instances=1
        )
        
        # Weekly RF model retraining — Sunday 02:00 IST (20:30 UTC Saturday)
        scheduler.add_job(
            _run_retrain_all_models,
            'cron',
            day_of_week='sun',
            hour=20,
            minute=30,
            timezone='UTC',
            id='retrain_all_demand_models',
            replace_existing=True,
            max_instances=1,
        )

        scheduler.start()
        logger.info("APScheduler started successfully.")

def shutdown_scheduler():
    """Shuts down the APScheduler gracefully."""
    if scheduler.running:
        scheduler.shutdown()
        logger.info("APScheduler stopped successfully.")
