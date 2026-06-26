import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import Contact, EnrichmentLog
from app.services.apollo_webhook import apply_waterfall_webhook, verify_webhook_secret

logger = logging.getLogger("apollo.webhook")

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/apollo/{secret}/contacts/{contact_id}")
async def apollo_contact_webhook(
    secret: str,
    contact_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    """Receive Apollo waterfall enrichment results (email/phone) asynchronously."""
    if not verify_webhook_secret(secret):
        raise HTTPException(status_code=404, detail="Not found.")

    contact = db.get(Contact, contact_id)
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found.")

    try:
        payload = await request.json()
    except Exception as exc:
        logger.warning("Apollo webhook for contact %s: invalid JSON (%s)", contact_id, exc)
        raise HTTPException(status_code=400, detail="Invalid JSON body.") from exc

    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Expected a JSON object.")

    updated = apply_waterfall_webhook(db, contact, payload)
    db.add(
        EnrichmentLog(
            entity_type="contact",
            entity_id=contact.id,
            endpoint="/webhooks/apollo/waterfall",
            request_payload={
                "status": payload.get("status"),
                "request_id": payload.get("request_id"),
                "email_records_enriched": payload.get("email_records_enriched"),
                "updated": updated,
            },
            response_status=200,
        )
    )
    db.commit()
    logger.info(
        "Apollo waterfall webhook for contact %s (updated=%s, request_id=%s)",
        contact_id,
        updated,
        payload.get("request_id"),
    )
    return {"ok": True, "updated": updated}
