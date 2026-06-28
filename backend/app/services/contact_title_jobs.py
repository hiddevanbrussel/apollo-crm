"""Background jobs for bulk title AI normalization — one contact at a time."""

from __future__ import annotations

import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.database import SessionLocal
from app.models import Contact
from app.services.contact_title_ai import normalize_contact_title_ai

logger = logging.getLogger("contact.title.jobs")


@dataclass
class TitleJobItem:
    index: int
    contact_id: int
    label: str | None = None
    status: str = "queued"
    result: str | None = None
    error: str | None = None
    started_at: float | None = None
    finished_at: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "contact_id": self.contact_id,
            "label": self.label,
            "status": self.status,
            "result": self.result,
            "provider": "groq" if self.result == "normalized" else None,
            "error": self.error,
        }


@dataclass
class ContactTitleAiJob:
    source: str
    contact_ids: list[int]
    filters: dict[str, Any] | None = None
    only_missing: bool = True
    force: bool = False
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    status: str = "queued"
    items: list[TitleJobItem] = field(default_factory=list)
    total_contacts: int = 0
    processed_contacts: int = 0
    normalized: int = 0
    skipped: int = 0
    failed: int = 0
    current_index: int | None = None
    current_contact: str | None = None
    error: str | None = None
    log: list[dict[str, Any]] = field(default_factory=list)
    started_at: float = field(default_factory=time.time)
    finished_at: float | None = None

    def __post_init__(self) -> None:
        self.total_contacts = len(self.contact_ids)
        self.items = [
            TitleJobItem(index=index, contact_id=contact_id)
            for index, contact_id in enumerate(self.contact_ids, start=1)
        ]

    def set_item_labels(self, db: Session) -> None:
        for item in self.items:
            contact = db.get(Contact, item.contact_id)
            if contact:
                item.label = contact.full_name or contact.email or f"#{contact.id}"
            else:
                item.label = f"#{item.contact_id} (not found)"

    def append_log(self, message: str) -> None:
        self.log.append({"at": time.time(), "message": message})
        if len(self.log) > 500:
            self.log = self.log[-500:]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "status": self.status,
            "source": self.source,
            "filters": self.filters,
            "total_contacts": self.total_contacts,
            "processed_contacts": self.processed_contacts,
            "normalized": self.normalized,
            "skipped": self.skipped,
            "failed": self.failed,
            "current_index": self.current_index,
            "current_contact": self.current_contact,
            "items": [item.to_dict() for item in self.items],
            "log": self.log[-200:],
            "error": self.error,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }


_jobs: dict[str, ContactTitleAiJob] = {}
_active_id: str | None = None
_lock = threading.Lock()


def get_job(job_id: str) -> ContactTitleAiJob | None:
    return _jobs.get(job_id)


def get_active_job() -> ContactTitleAiJob | None:
    return _jobs.get(_active_id) if _active_id else None


def list_jobs(limit: int = 10) -> list[ContactTitleAiJob]:
    jobs = sorted(_jobs.values(), key=lambda j: j.started_at, reverse=True)
    return jobs[:limit]


def _worker(job_id: str) -> None:
    job = _jobs[job_id]
    db = SessionLocal()
    try:
        job.status = "running"
        job.append_log(f"Job started — {job.total_contacts} contact(s), one at a time.")

        for item in job.items:
            item.status = "running"
            item.started_at = time.time()
            job.current_index = item.index

            contact = db.execute(
                select(Contact).options(joinedload(Contact.company)).where(Contact.id == item.contact_id)
            ).scalar_one_or_none()

            if not contact:
                item.status = "completed"
                item.result = "skipped"
                item.error = "Contact not found."
                job.skipped += 1
                job.processed_contacts += 1
                job.append_log(f"#{item.index} skipped — contact {item.contact_id} not found.")
                continue

            label = contact.full_name or contact.email or f"#{contact.id}"
            item.label = label
            job.current_contact = label
            job.append_log(f"#{item.index}/{job.total_contacts} normalizing title for {label}…")

            result = normalize_contact_title_ai(
                db,
                contact,
                force=job.force,
            )
            db.commit()

            item.status = "completed"
            item.finished_at = time.time()

            if result.skipped and result.ok:
                item.result = "skipped"
                job.skipped += 1
                job.append_log(f"#{item.index} {label} → skipped ({result.reason or result.error or 'already done'})")
            elif result.ok:
                item.result = "normalized"
                job.normalized += 1
                job.append_log(f"#{item.index} {label} → {result.title_ai}")
            else:
                item.result = "failed"
                item.error = result.error or "normalization failed"
                job.failed += 1
                job.append_log(f"#{item.index} {label} → failed: {item.error}")

            job.processed_contacts += 1

        job.status = "completed"
        job.append_log(
            f"Job completed — normalized {job.normalized}, skipped {job.skipped}, failed {job.failed}."
        )
    except Exception as exc:  # pragma: no cover
        db.rollback()
        job.status = "failed"
        job.error = str(exc)
        job.append_log(f"Job failed: {exc}")
        logger.exception("Contact title AI job failed")
    finally:
        job.current_index = None
        job.current_contact = None
        job.finished_at = time.time()
        db.close()


def start_job(
    contact_ids: list[int],
    *,
    source: str,
    filters: dict[str, Any] | None = None,
    only_missing: bool = True,
    force: bool = False,
    db: Session | None = None,
) -> tuple[ContactTitleAiJob, bool]:
    global _active_id
    with _lock:
        active = get_active_job()
        if active and active.status in {"queued", "running"}:
            return active, False

        job = ContactTitleAiJob(
            source=source,
            contact_ids=contact_ids,
            filters=filters,
            only_missing=only_missing,
            force=force,
        )
        if db is not None:
            job.set_item_labels(db)
        job.append_log(f"Queued {job.total_contacts} contact(s) for title normalization.")
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
