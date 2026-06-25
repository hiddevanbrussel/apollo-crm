"""Background job manager for bulk domain lookups via Groq.

Runs in a daemon thread so a single HTTP request can kick off processing of all
companies without a domain, while the frontend polls for progress.

State is kept in-memory (single-process app); a restart clears running jobs.
"""

from __future__ import annotations

import logging
import threading
import time
import uuid

from sqlalchemy import func, select

from app.core.database import SessionLocal
from app.models import Company, EnrichmentLog
from app.services.groq_service import GroqError
from app.services.settings_service import build_groq_client

logger = logging.getLogger("domain.jobs")


class DomainJob:
    def __init__(self) -> None:
        self.id = uuid.uuid4().hex
        self.status = "running"  # running | completed | failed
        self.total = 0
        self.processed = 0
        self.found = 0
        self.applied = 0
        self.current: str | None = None
        self.error: str | None = None
        self.started_at = time.time()
        self.finished_at: float | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "status": self.status,
            "total": self.total,
            "processed": self.processed,
            "found": self.found,
            "applied": self.applied,
            "current": self.current,
            "error": self.error,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }


_jobs: dict[str, DomainJob] = {}
_active_id: str | None = None
_lock = threading.Lock()


def get_job(job_id: str) -> DomainJob | None:
    return _jobs.get(job_id)


def get_active_job() -> DomainJob | None:
    return _jobs.get(_active_id) if _active_id else None


def _apply_found_domain(db, company: Company, domain: str | None) -> bool:
    if not domain:
        return False
    if company.domain and company.domain.lower() == domain.lower():
        return False
    clash = db.execute(
        select(Company).where(func.lower(Company.domain) == domain.lower())
    ).scalar_one_or_none()
    if clash and clash.id != company.id:
        return False
    company.domain = domain
    return True


def _worker(job_id: str) -> None:
    job = _jobs[job_id]
    db = SessionLocal()
    try:
        client = build_groq_client(db)
        companies = (
            db.execute(
                select(Company)
                .where((Company.domain.is_(None)) | (Company.domain == ""))
                .order_by(Company.updated_at.desc())
            )
            .scalars()
            .all()
        )
        job.total = len(companies)

        for company in companies:
            job.current = company.name
            try:
                result = client.find_domain(company.name, company.country)
            except GroqError as exc:
                logger.warning("Domain lookup failed for %s: %s", company.name, exc.message)
                db.add(
                    EnrichmentLog(
                        entity_type="company",
                        entity_id=company.id,
                        endpoint="groq/find-domain",
                        request_payload={"name": company.name, "country": company.country},
                        response_status=exc.status_code,
                    )
                )
                db.commit()
                job.processed += 1
                continue

            domain = result.get("domain")
            if result.get("found") and domain:
                job.found += 1
                if _apply_found_domain(db, company, domain):
                    job.applied += 1
            db.add(
                EnrichmentLog(
                    entity_type="company",
                    entity_id=company.id,
                    endpoint="groq/find-domain",
                    request_payload={"name": company.name, "country": company.country},
                    response_status=200,
                )
            )
            db.commit()
            job.processed += 1

        job.status = "completed"
    except Exception as exc:  # pragma: no cover
        db.rollback()
        job.status = "failed"
        job.error = str(exc)
        logger.exception("Domain job failed")
    finally:
        job.current = None
        job.finished_at = time.time()
        db.close()


def start_job() -> tuple[DomainJob, bool]:
    """Start a new job unless one is already running. Returns (job, started)."""
    global _active_id
    with _lock:
        active = get_active_job()
        if active and active.status == "running":
            return active, False
        job = DomainJob()
        _jobs[job.id] = job
        _active_id = job.id
        # Keep memory bounded: drop old finished jobs.
        if len(_jobs) > 20:
            for old_id in [
                jid for jid, j in _jobs.items() if j.status != "running" and jid != job.id
            ][:-10]:
                _jobs.pop(old_id, None)

    threading.Thread(target=_worker, args=(job.id,), daemon=True).start()
    return job, True
