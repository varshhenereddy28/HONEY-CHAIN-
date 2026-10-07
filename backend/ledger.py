from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from .database import BlockRecord, SessionLocal

GENESIS_HASH = "0" * 64


def canonical_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def hash_payload(data: Any) -> str:
    return hashlib.sha256(canonical_json(data).encode("utf-8")).hexdigest()


def append_block(batch_id: str, event: str, payload: dict[str, Any]) -> dict[str, Any]:
    db = SessionLocal()
    try:
        previous = db.query(BlockRecord).order_by(BlockRecord.height.desc()).first()
        previous_hash = previous.hash if previous else GENESIS_HASH
        block_height = (previous.height if previous else 0) + 1
        timestamp = datetime.now(timezone.utc).replace(tzinfo=None)
        record = {
            "batch_id": batch_id,
            "height": block_height,
            "timestamp": timestamp.isoformat(),
            "previous_hash": previous_hash,
            "event": event,
            "payload": payload,
        }
        block_hash = hash_payload(record)
        row = BlockRecord(
            batch_id=batch_id,
            height=block_height,
            timestamp=timestamp,
            previous_hash=previous_hash,
            event=event,
            payload_json=json.dumps(payload, ensure_ascii=False, sort_keys=True),
            hash=block_hash,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return {
            "id": row.id,
            "batch_id": row.batch_id,
            "height": row.height,
            "timestamp": row.timestamp.isoformat(),
            "previous_hash": row.previous_hash,
            "event": row.event,
            "payload": payload,
            "hash": row.hash,
        }
    finally:
        db.close()


def get_blocks() -> list[dict[str, Any]]:
    db = SessionLocal()
    try:
        rows = db.query(BlockRecord).order_by(BlockRecord.height.asc()).all()
        return [
            {
                "id": row.id,
                "batch_id": row.batch_id,
                "height": row.height,
                "timestamp": row.timestamp.isoformat(),
                "previous_hash": row.previous_hash,
                "event": row.event,
                "payload": json.loads(row.payload_json),
                "hash": row.hash,
            }
            for row in rows
        ]
    finally:
        db.close()


def verify_chain() -> tuple[bool, list[str]]:
    blocks = get_blocks()
    previous_hash = GENESIS_HASH
    errors: list[str] = []
    for block in blocks:
        unsigned = {
            "batch_id": block["batch_id"],
            "height": block["height"],
            "timestamp": block["timestamp"],
            "previous_hash": block["previous_hash"],
            "event": block["event"],
            "payload": block["payload"],
        }
        actual_hash = hash_payload(unsigned)
        if block["previous_hash"] != previous_hash:
            errors.append(f"Previous hash mismatch at height {block['height']}")
        if block["hash"] != actual_hash:
            errors.append(f"Hash mismatch at height {block['height']}")
        previous_hash = block["hash"]
    return not errors, errors
