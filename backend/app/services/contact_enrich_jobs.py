"""Background jobs for bulk contact enrichment with pre-planned batches."""

from __future__ import annotations

import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from app.core.database import SessionLocal
from app.models import Contact
from app.services.contact_enrich import enrich_contact_auto

logger = logging.getLogger("contact.enrich.jobs")

DEFAULT_BATCH_SIZE = 50


@dataclass
class EnrichBatch:
    index: int
    contact_ids: list[int]
    status: str = "queued"  # queued | running | completed | failed
    enriched: int = 0
    pending: int = 0
    failed: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)
    started_at: float | None = None
    finished_at: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "contact_count": len(self.contact_ids),
            "status": self.status,
            "enriched": self.enriched,
            "pending": self.pending,
            "failed": self.failed,
            "skipped": self.skipped,
            "errors": self.errors[:20],
        }


@dataclass
class ContactEnrichJob:
    source: str  # selected | unenriched
    contact_ids: list[int]
    batch_size: int = DEFAULT_BATCH_SIZE
    filters: dict[str, Any] | None = None
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    status: str = "queued"  # queued | running | completed | failed
    batches: list[EnrichBatch] = field(default_factory=list)
    total_contacts: int = 0
    processed_contacts: int = 0
    enriched: int = 0
    pending: int = 0
    failed: int = 0
    skipped: int = 0
    current_batch: int | None = None
    current_contact: str | None = None
    error: str | None = None
    log: list[dict[str, Any]] = field(default_factory=list)
    started_at: float = field(default_factory=time.time)
    finished_at: float | None = None

    def __post_init__(self) -> None:
        self.total_contacts = len(self.contact_ids)
        self.batches = self._plan_batches()

    def _plan_batches(self) -> list[EnrichBatch]:
        size = max(1, self.batch_size)
        batches: list[EnrichBatch] = []
        for index, start in enumerate(range(0, len(self.contact_ids), size), start=1):
            chunk = self.contact_ids[start : start + size]
            batches.append(EnrichBatch(index=index, contact_ids=chunk))
        return batches

    def append_log(self, message: str) -> None:
        self.log.append({"at": time.time(), "message": message})
        if len(self.log) > 200:
            self.log = self.log[-200:]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "status": self.status,
            "source": self.source,
            "filters": self.filters,
            "total_contacts": self.total_contacts,
            "batch_size": self.batch_size,
            "batch_count": len(self.batches),
            "processed_contacts": self.processed_contacts,
            "enriched": self.enriched,
            "pending": self.pending,
            "failed": self.failed,
            "skipped": self.skipped,
            "current_batch": self.current_batch,
            "current_contact": self.current_contact,
            "batches": [b.to_dict() for b in self.batches],
            "log": self.log[-100:],
            "error": self.error,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }


_jobs: dict[str, ContactEnrichJob] = {}
_active_id: str | None = None
_lock = threading.Lock()


def get_job(job_id: str) -> ContactEnrichJob | None:
    return _jobs.get(job_id)


def get_active_job() -> ContactEnrichJob | None:
    return _jobs.get(_active_id) if _active_id else None


def list_jobs(limit: int = 10) -> list[ContactEnrichJob]:
    jobs = sorted(_jobs.values(), key=lambda j: j.started_at, reverse=True)
    return jobs[:limit]


def _worker(job_id: str) -> None:
    job = _jobs[job_id]
    db = SessionLocal()
    try:
        job.status = "running"
        job.append_log(
            f"Job started: {job.total_contacts} contact(s) in {len(job.batches)} batch(es) "
            f"of up to {job.batch_size}."
        )

        for batch in job.batches:
            batch.status = "running"
            batch.started_at = time.time()
            job.current_batch = batch.index
            job.append_log(
                f"Batch {batch.index}/{len(job.batches)} started ({len(batch.contact_ids)} contacts)."
            )

            for contact_id in batch.contact_ids:
                contact = db.get(Contact, contact_id)
                if not contact:
                    batch.skipped += 1
                    job.skipped += 1
                    batch.errors.append(f"Contact #{contact_id}: not found.")
                    job.processed_contacts += 1
                    continue

                label = contact.full_name or contact.email or f"#{contact.id}"
                job.current_contact = label

                enrich_result = enrich_contact_auto(db, contact)
                if enrich_result.ok:
                    if enrich_result.status == "pending":
                        batch.pending += 1
                        job.pending += 1
                    else:
                        batch.enriched += 1
                        job.enriched += 1
                else:
                    batch.failed += 1
                    job.failed += 1
                    err = f"{label}: {enrich_result.error or 'match failed'}"
                    batch.errors.append(err)

                job.processed_contacts += 1

            db.commit()
            batch.status = "completed"
            batch.finished_at = time.time()
            job.append_log(
                f"Batch {batch.index} done — enriched {batch.enriched}, pending {batch.pending}, "
                f"failed {batch.failed}, skipped {batch.skipped}."
            )

        job.status = "completed"
        job.append_log(
            f"Job completed — enriched {job.enriched}, pending {job.pending}, "
            f"failed {job.failed}, skipped {job.skipped}."
        )
    except Exception as exc:  # pragma: no cover
        db.rollback()
        job.status = "failed"
        job.error = str(exc)
        job.append_log(f"Job failed: {exc}")
        logger.exception("Contact enrich job failed")
    finally:
        job.current_batch = None
        job.current_contact = None
        job.finished_at = time.time()
        db.close()


def start_job(
    contact_ids: list[int],
    *,
    source: str,
    filters: dict[str, Any] | None = None,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> tuple[ContactEnrichJob, bool]:
    """Start a new job unless one is already running. Returns (job, started)."""
    global _active_id
    with _lock:
        active = get_active_job()
        if active and active.status in {"queued", "running"}:
            return active, False

        job = ContactEnrichJob(
            source=source,
            contact_ids=contact_ids,
            batch_size=batch_size,
            filters=filters,
        )
        job.append_log(
            f"Planned {len(job.batches)} batch(es) for {job.total_contacts} contact(s)."
        )
        _jobs[job.id] = job
        _active_id = job.id

        if len(_jobs) > 30:
            for old_id in [
                jid
                for jid, j in _jobs.items()
                if j.status not in {"queued", "running"} and jid != job.id
            ][:-15]:
                _jobs.pop(old_id, None)

    threading.Thread(target=_worker, args=(job.id,), daemon=True).start()
    return job, True
