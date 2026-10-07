from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .database import Batch, SessionLocal, init_db
from .ledger import append_block, verify_chain

init_db()

app = FastAPI(title="HoneyChain API", version="1.0.0")


class BatchInput(BaseModel):
    id: str
    beekeeper: str
    apiary_id: str
    floral_source: str
    region: str
    latitude: float = 0.0
    longitude: float = 0.0
    quantity_kg: float = 0.0
    status: str = "pending"
    sync_status: str = "offline"


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "honeychain-api"}


@app.get("/batches")
def list_batches() -> list[dict[str, Any]]:
    db = SessionLocal()
    try:
        rows = db.query(Batch).order_by(Batch.harvested_at.desc()).all()
        return [
            {
                "id": row.id,
                "beekeeper": row.beekeeper,
                "apiary_id": row.apiary_id,
                "floral_source": row.floral_source,
                "region": row.region,
                "latitude": row.latitude,
                "longitude": row.longitude,
                "quantity_kg": row.quantity_kg,
                "status": row.status,
                "sync_status": row.sync_status,
                "cloud_status": row.cloud_status,
                "risk_score": row.risk_score,
                "purity_badge": row.purity_badge,
            }
            for row in rows
        ]
    finally:
        db.close()


@app.post("/batches")
def create_batch(payload: BatchInput) -> dict[str, Any]:
    db = SessionLocal()
    try:
        batch = db.query(Batch).filter(Batch.id == payload.id).first()
        if batch:
            raise HTTPException(status_code=409, detail="Batch already exists")
        batch = Batch(
            id=payload.id,
            beekeeper=payload.beekeeper,
            apiary_id=payload.apiary_id,
            floral_source=payload.floral_source,
            region=payload.region,
            latitude=payload.latitude,
            longitude=payload.longitude,
            quantity_kg=payload.quantity_kg,
            status=payload.status,
            sync_status=payload.sync_status,
            cloud_status="local-cache",
        )
        db.add(batch)
        db.commit()
        db.refresh(batch)
        append_block(batch.id, "HARVEST_RECORDED", {
            "apiary_id": batch.apiary_id,
            "floral_source": batch.floral_source,
            "quantity_kg": batch.quantity_kg,
            "region": batch.region,
        })
        return {"id": batch.id, "status": "created"}
    finally:
        db.close()


@app.get("/ledger/verify")
def ledger_verify() -> dict[str, Any]:
    valid, errors = verify_chain()
    return {"valid": valid, "errors": errors}


@app.get("/sync/status")
def sync_status() -> dict[str, str]:
    return {"status": "ready", "backend": "sqlite-primary", "cloud": "postgres-ready"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
