from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

GENESIS_HASH = "0" * 64
DEFAULT_DATABASE = Path(os.environ.get("HONEYCHAIN_DB", "data/honeychain.db"))

DEMO_BATCHES: list[dict[str, Any]] = [
    {
        "id": "HC-KA-2408-001",
        "beekeeper": "Lakshmi Devi",
        "apiary": "KA-AP-042",
        "floral_source": "Wild forest multiflora",
        "region": "Chikkamagaluru, Karnataka",
        "latitude": 13.3153,
        "longitude": 75.7754,
        "harvested_at": "2026-10-02T07:42:00+00:00",
        "quantity_kg": 186.0,
        "moisture": 17.4,
        "hmf": 18.2,
        "c4_sugar": 2.1,
        "nmr_score": 0.97,
        "status": "verified",
        "certificate_id": "FSSAI-DEMO-26-1048",
    },
    {
        "id": "HC-KA-2408-002",
        "beekeeper": "Ravi Kumar",
        "apiary": "KA-AP-019",
        "floral_source": "Neem blossom",
        "region": "Mysuru, Karnataka",
        "latitude": 12.2958,
        "longitude": 76.6394,
        "harvested_at": "2026-10-01T06:18:00+00:00",
        "quantity_kg": 92.0,
        "moisture": 18.1,
        "hmf": 21.6,
        "c4_sugar": 1.4,
        "nmr_score": 0.94,
        "status": "verified",
        "certificate_id": "FSSAI-DEMO-26-1036",
    },
    {
        "id": "HC-KA-2408-003",
        "beekeeper": "Meera Gowda",
        "apiary": "KA-AP-071",
        "floral_source": "Jamun",
        "region": "Coorg, Karnataka",
        "latitude": 12.3375,
        "longitude": 75.8069,
        "harvested_at": "2026-09-30T08:05:00+00:00",
        "quantity_kg": 124.0,
        "moisture": 19.2,
        "hmf": 32.8,
        "c4_sugar": 3.5,
        "nmr_score": 0.91,
        "status": "verified",
        "certificate_id": "FSSAI-DEMO-26-1021",
    },
]


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _hash_block(unsigned_block: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(unsigned_block).encode("utf-8")).hexdigest()


def _database_path(path: Path | str | None) -> Path:
    resolved = Path(path) if path is not None else DEFAULT_DATABASE
    resolved.parent.mkdir(parents=True, exist_ok=True)
    return resolved


def _connect(path: Path | str | None = None) -> sqlite3.Connection:
    connection = sqlite3.connect(_database_path(path), timeout=15)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    return connection


def initialize_database(path: Path | str | None = None) -> None:
    """Create local tables and add three demo batches to a new ledger."""
    with _connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS batches (
                id TEXT PRIMARY KEY,
                beekeeper TEXT NOT NULL,
                apiary TEXT NOT NULL,
                floral_source TEXT NOT NULL,
                region TEXT NOT NULL,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                harvested_at TEXT NOT NULL,
                quantity_kg REAL NOT NULL,
                moisture REAL NOT NULL DEFAULT 0,
                hmf REAL NOT NULL DEFAULT 0,
                c4_sugar REAL NOT NULL DEFAULT 0,
                nmr_score REAL NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'pending',
                certificate_id TEXT NOT NULL DEFAULT 'Pending lab review'
            );
            CREATE TABLE IF NOT EXISTS blocks (
                height INTEGER PRIMARY KEY,
                timestamp TEXT NOT NULL,
                previous_hash TEXT NOT NULL,
                batch_id TEXT NOT NULL,
                event TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                hash TEXT NOT NULL UNIQUE,
                FOREIGN KEY(batch_id) REFERENCES batches(id)
            );
            CREATE INDEX IF NOT EXISTS blocks_batch_id_idx ON blocks(batch_id);
            CREATE TABLE IF NOT EXISTS packaging_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                batch_id TEXT NOT NULL,
                serial_count INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(batch_id) REFERENCES batches(id)
            );
            """
        )
        if connection.execute("SELECT COUNT(*) FROM blocks").fetchone()[0] == 0:
            previous_hash = GENESIS_HASH
            for batch in DEMO_BATCHES:
                connection.execute(
                    """INSERT OR IGNORE INTO batches
                    (id, beekeeper, apiary, floral_source, region, latitude, longitude,
                     harvested_at, quantity_kg, moisture, hmf, c4_sugar, nmr_score,
                     status, certificate_id)
                    VALUES (:id, :beekeeper, :apiary, :floral_source, :region, :latitude,
                     :longitude, :harvested_at, :quantity_kg, :moisture, :hmf, :c4_sugar,
                     :nmr_score, :status, :certificate_id)""",
                    batch,
                )
                harvest_time = datetime.fromisoformat(batch["harvested_at"])
                harvest_block = _make_block(
                    0,
                    harvest_time.isoformat(timespec="seconds"),
                    previous_hash,
                    batch["id"],
                    "HARVEST_RECORDED",
                    {
                        "apiary": batch["apiary"],
                        "floral_source": batch["floral_source"],
                        "quantity_kg": batch["quantity_kg"],
                        "region": batch["region"],
                    },
                )
                previous_hash = _insert_block(connection, harvest_block)
                lab_block = _make_block(
                    0,
                    (harvest_time + timedelta(hours=1)).isoformat(timespec="seconds"),
                    previous_hash,
                    batch["id"],
                    "LAB_CERTIFIED",
                    {
                        "certificate_id": batch["certificate_id"],
                        "nmr_score": batch["nmr_score"],
                        "status": batch["status"],
                    },
                )
                previous_hash = _insert_block(connection, lab_block)


def _make_block(
    height: int,
    timestamp: str,
    previous_hash: str,
    batch_id: str,
    event: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    return {
        "height": height,
        "timestamp": timestamp,
        "previous_hash": previous_hash,
        "batch_id": batch_id,
        "event": event,
        "payload": payload,
    }


def _insert_block(connection: sqlite3.Connection, block: dict[str, Any]) -> str:
    previous = connection.execute("SELECT height FROM blocks ORDER BY height DESC LIMIT 1").fetchone()
    block["height"] = (previous["height"] if previous else 0) + 1
    block_hash = _hash_block(block)
    connection.execute(
        """INSERT INTO blocks(height, timestamp, previous_hash, batch_id, event, payload_json, hash)
        VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            block["height"],
            block["timestamp"],
            block["previous_hash"],
            block["batch_id"],
            block["event"],
            _canonical_json(block["payload"]),
            block_hash,
        ),
    )
    return block_hash


def append_event(batch_id: str, event: str, payload: dict[str, Any], path: Path | str | None = None) -> dict[str, Any]:
    initialize_database(path)
    with _connect(path) as connection:
        block = _make_block(0, _now(), GENESIS_HASH, batch_id, event, payload)
        _insert_block(connection, block)
        block["height"] = connection.execute("SELECT MAX(height) FROM blocks").fetchone()[0]
        block["hash"] = _hash_block(block)
        return block


def get_batches(path: Path | str | None = None) -> list[dict[str, Any]]:
    initialize_database(path)
    with _connect(path) as connection:
        rows = connection.execute("SELECT * FROM batches ORDER BY harvested_at DESC").fetchall()
    return [dict(row) for row in rows]


def get_batch(batch_id: str, path: Path | str | None = None) -> dict[str, Any] | None:
    initialize_database(path)
    with _connect(path) as connection:
        row = connection.execute("SELECT * FROM batches WHERE id = ?", (batch_id.strip(),)).fetchone()
    return dict(row) if row else None


def get_blocks(path: Path | str | None = None) -> list[dict[str, Any]]:
    initialize_database(path)
    with _connect(path) as connection:
        rows = connection.execute("SELECT * FROM blocks ORDER BY height DESC").fetchall()
    result = []
    for row in rows:
        block = dict(row)
        block["payload"] = json.loads(block.pop("payload_json"))
        result.append(block)
    return result


def record_harvest(batch: dict[str, Any], path: Path | str | None = None) -> dict[str, Any]:
    initialize_database(path)
    batch = {**batch, "status": "pending", "certificate_id": "Pending lab review"}
    with _connect(path) as connection:
        connection.execute(
            """INSERT INTO batches
            (id, beekeeper, apiary, floral_source, region, latitude, longitude, harvested_at,
             quantity_kg, moisture, hmf, c4_sugar, nmr_score, status, certificate_id)
            VALUES (:id, :beekeeper, :apiary, :floral_source, :region, :latitude, :longitude,
             :harvested_at, :quantity_kg, :moisture, :hmf, :c4_sugar, :nmr_score, :status, :certificate_id)""",
            batch,
        )
        block = _make_block(
            0,
            batch["harvested_at"],
            GENESIS_HASH,
            batch["id"],
            "HARVEST_RECORDED",
            {
                "apiary": batch["apiary"],
                "floral_source": batch["floral_source"],
                "quantity_kg": batch["quantity_kg"],
                "region": batch["region"],
            },
        )
        block_hash = _insert_block(connection, block)
        block["height"] = connection.execute("SELECT MAX(height) FROM blocks").fetchone()[0]
        block["hash"] = block_hash
    return block


def certify_batch(
    batch_id: str,
    metrics: dict[str, float],
    path: Path | str | None = None,
) -> tuple[dict[str, Any], str]:
    initialize_database(path)
    batch = get_batch(batch_id, path)
    if batch is None:
        raise ValueError(f"Unknown batch: {batch_id}")
    passed = (
        metrics["moisture"] <= 20
        and metrics["hmf"] <= 80
        and metrics["c4_sugar"] <= 7
        and metrics["nmr_score"] >= 0.9
    )
    certificate_id = f"FSSAI-DEMO-{datetime.now(UTC):%y}-{hashlib.sha256(f'{batch_id}:{_canonical_json(metrics)}:{_now()}'.encode()).hexdigest()[:6].upper()}"
    updated = {
        **batch,
        **metrics,
        "status": "verified" if passed else "rejected",
        "certificate_id": certificate_id,
    }
    with _connect(path) as connection:
        connection.execute(
            """UPDATE batches SET moisture = ?, hmf = ?, c4_sugar = ?, nmr_score = ?,
            status = ?, certificate_id = ? WHERE id = ?""",
            (
                metrics["moisture"], metrics["hmf"], metrics["c4_sugar"], metrics["nmr_score"],
                updated["status"], certificate_id, batch_id,
            ),
        )
        block = _make_block(
            0,
            _now(),
            GENESIS_HASH,
            batch_id,
            "LAB_CERTIFIED",
            {"certificate_id": certificate_id, **metrics, "passed": passed},
        )
        _insert_block(connection, block)
    signature = hashlib.sha256(_canonical_json({"certificate": certificate_id, "batch": batch_id, **metrics}).encode()).hexdigest()
    return updated, signature


def record_packaging(batch_id: str, serial_count: int, path: Path | str | None = None) -> None:
    initialize_database(path)
    with _connect(path) as connection:
        connection.execute(
            "INSERT INTO packaging_runs(batch_id, serial_count, created_at) VALUES (?, ?, ?)",
            (batch_id, serial_count, _now()),
        )
        block = _make_block(
            0, _now(), GENESIS_HASH, batch_id, "PACKAGED", {"serial_count": serial_count}
        )
        _insert_block(connection, block)


def verify_chain(path: Path | str | None = None) -> tuple[bool, int]:
    initialize_database(path)
    with _connect(path) as connection:
        rows = connection.execute("SELECT * FROM blocks ORDER BY height").fetchall()
    previous_hash = GENESIS_HASH
    for row in rows:
        payload = json.loads(row["payload_json"])
        unsigned = _make_block(
            row["height"], row["timestamp"], row["previous_hash"], row["batch_id"], row["event"], payload
        )
        if row["previous_hash"] != previous_hash or _hash_block(unsigned) != row["hash"]:
            return False, len(rows)
        previous_hash = row["hash"]
    return bool(rows), len(rows)


def batch_proof(batch: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(batch).encode("utf-8")).hexdigest()
