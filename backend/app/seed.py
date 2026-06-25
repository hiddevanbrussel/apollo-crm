"""Bootstrap essential data: admin user and the default Apollo settings row.

No sample/dummy companies or contacts are created. This runs on startup and is
idempotent: running it multiple times will not create duplicates.
"""

from __future__ import annotations

import logging

from sqlalchemy import select

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models import ApolloSettings, User

logger = logging.getLogger("seed")
logging.basicConfig(level=logging.INFO)


def seed() -> None:
    db = SessionLocal()
    try:
        # Admin user
        admin = db.execute(
            select(User).where(User.email == settings.ADMIN_EMAIL)
        ).scalar_one_or_none()
        if not admin:
            admin = User(
                name=settings.ADMIN_NAME,
                email=settings.ADMIN_EMAIL,
                password_hash=hash_password(settings.ADMIN_PASSWORD),
                role="admin",
            )
            db.add(admin)
            logger.info("Created admin user %s", settings.ADMIN_EMAIL)
        else:
            if admin.role != "admin":
                admin.role = "admin"
                logger.info("Promoted %s to admin.", settings.ADMIN_EMAIL)
            else:
                logger.info("Admin user already exists, skipping.")

        # Apollo settings row
        apollo_row = db.execute(select(ApolloSettings).limit(1)).scalar_one_or_none()
        if not apollo_row:
            db.add(
                ApolloSettings(
                    base_url=settings.APOLLO_BASE_URL,
                    enabled=False,
                    api_key_encrypted=None,
                )
            )
            logger.info("Created default Apollo settings row.")

        db.commit()
        logger.info("Bootstrap complete (no sample data).")
    except Exception:  # pragma: no cover
        db.rollback()
        logger.exception("Bootstrap failed")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    if settings.SEED_ON_START:
        seed()
    else:
        logger.info("SEED_ON_START is false; skipping bootstrap.")
