# fastkeel/modules/jobs.py
import logging
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI

from fastkeel.core.config import Config

logger = logging.getLogger(__name__)

scheduler: AsyncIOScheduler | None = None


def heartbeat_check() -> None:
    """Built-in heartbeat: logs that the scheduler is alive."""
    logger.info("fastkeel heartbeat — scheduler is alive")


def resolve_job_func(job_name: str) -> Any:
    """Resolve a job function by convention: project.logic.<job_name>.

    Falls back to a no-op if the module or function is not found.
    """
    try:
        module = __import__(f"project.logic.{job_name}", fromlist=[job_name])
        return getattr(module, job_name)
    except (ImportError, AttributeError):
        logger.warning("Job function not found for '%s', using no-op", job_name)
        return lambda: None


async def include_jobs(app: FastAPI, config: Config) -> None:
    """Initialize APScheduler and register scheduled jobs."""
    global scheduler

    scheduler = AsyncIOScheduler()

    # Built-in heartbeat check (every 5 minutes)
    scheduler.add_job(
        heartbeat_check,
        "interval",
        minutes=5,
        id="_fastkeel_heartbeat",
    )

    # Custom jobs from config
    if config.jobs_config:
        for job_name, job_params in config.jobs_config.items():
            scheduler.add_job(
                resolve_job_func(job_name),
                **job_params,
                id=job_name,
            )

    scheduler.start()
