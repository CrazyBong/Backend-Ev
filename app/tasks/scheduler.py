import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.db.database import AsyncSessionLocal
from app.tasks.cleanup_tasks import release_abandoned_locks, cleanup_database_garbage

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
        
        scheduler.start()
        logger.info("APScheduler started successfully.")

def shutdown_scheduler():
    """Shuts down the APScheduler gracefully."""
    if scheduler.running:
        scheduler.shutdown()
        logger.info("APScheduler stopped successfully.")
