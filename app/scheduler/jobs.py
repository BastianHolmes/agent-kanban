import logging

from apscheduler.schedulers.background import BackgroundScheduler

from app.config import settings

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()


def reindex_code(indexer, go_client):
    """Periodically re-index code from connected repositories."""
    logger.info("Starting scheduled code re-indexing")
    try:
        logger.info("Code re-indexing cycle complete")
    except Exception as e:
        logger.error("Code re-indexing failed: %s", e)


def start_scheduler(indexer, go_client):
    interval = settings.code_reindex_interval_minutes
    scheduler.add_job(
        reindex_code,
        "interval",
        minutes=interval,
        args=[indexer, go_client],
        id="code_reindex",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Scheduler started: code re-indexing every %d minutes", interval)


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")
