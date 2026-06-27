"""
APScheduler initialisation and lifecycle management.

Provides ``init_scheduler()`` and ``shutdown_scheduler()`` called
from the FastAPI lifespan handler.
"""

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.scheduler.jobs import register_jobs

logger = logging.getLogger(__name__)

# Module-level scheduler instance
scheduler: AsyncIOScheduler = AsyncIOScheduler()


def init_scheduler() -> None:
    """Initialise and start the background job scheduler."""
    register_jobs(scheduler)
    scheduler.start()
    logger.info("APScheduler started — all jobs registered")


def shutdown_scheduler() -> None:
    """Gracefully shut down the scheduler."""
    scheduler.shutdown(wait=False)
    logger.info("APScheduler shut down")
