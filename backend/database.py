from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Generator

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text, create_engine
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

Base = declarative_base()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./honeychain.db")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Batch(Base):
    __tablename__ = "batches"

    id = Column(String, primary_key=True)
    beekeeper = Column(String, nullable=False)
    apiary_id = Column(String, nullable=False)
    floral_source = Column(String, nullable=False)
    region = Column(String, nullable=False)
    latitude = Column(Float, default=0.0)
    longitude = Column(Float, default=0.0)
    harvested_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    quantity_kg = Column(Float, default=0.0)
    status = Column(String, default="pending")
    sync_status = Column(String, default="offline")
    cloud_status = Column(String, default="local-cache")
    risk_score = Column(Float, default=0.0)
    purity_badge = Column(String, default="pending")
    certificate_id = Column(String, default="pending")
    notes = Column(Text, default="")

    quality_tests = relationship("QualityTest", back_populates="batch", cascade="all, delete-orphan")
    blocks = relationship("BlockRecord", back_populates="batch", cascade="all, delete-orphan")
    packaging_runs = relationship("PackagingRun", back_populates="batch", cascade="all, delete-orphan")


class QualityTest(Base):
    __tablename__ = "quality_tests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    batch_id = Column(String, ForeignKey("batches.id"), nullable=False)
    moisture = Column(Float, default=0.0)
    hmf = Column(Float, default=0.0)
    c4_sugar = Column(Float, default=0.0)
    nmr_score = Column(Float, default=0.0)
    passed = Column(Boolean, default=False)
    compliance = Column(String, default="pending")
    certificate_id = Column(String, default="pending")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    batch = relationship("Batch", back_populates="quality_tests")


class BlockRecord(Base):
    __tablename__ = "blocks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    batch_id = Column(String, ForeignKey("batches.id"), nullable=False)
    height = Column(Integer, nullable=False, unique=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    previous_hash = Column(String, nullable=False)
    event = Column(String, nullable=False)
    payload_json = Column(Text, nullable=False)
    hash = Column(String, nullable=False, unique=True)

    batch = relationship("Batch", back_populates="blocks")


class PackagingRun(Base):
    __tablename__ = "packaging_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    batch_id = Column(String, ForeignKey("batches.id"), nullable=False)
    serial_count = Column(Integer, default=0)
    qr_payload = Column(Text, default="")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    batch = relationship("Batch", back_populates="packaging_runs")


def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    seed_demo_batches()


def seed_demo_batches() -> None:
    db = SessionLocal()
    try:
        has_batches = db.query(Batch).count() > 0

        samples = [
            {
                "id": "HC-KA-2408-001",
                "beekeeper": "Lakshmi Devi",
                "apiary_id": "KA-AP-042",
                "floral_source": "Wild forest multiflora",
                "region": "Chikkamagaluru, Karnataka",
                "latitude": 13.3153,
                "longitude": 75.7754,
                "harvested_at": datetime(2026, 10, 2, 7, 42, tzinfo=timezone.utc),
                "quantity_kg": 186.0,
                "status": "verified",
                "sync_status": "offline",
                "cloud_status": "local-cache",
                "risk_score": 0.07,
                "purity_badge": "100% purity",
                "certificate_id": "FSSAI-DEMO-26-1048",
                "notes": "High-altitude wild flora harvest",
            },
            {
                "id": "HC-KA-2408-002",
                "beekeeper": "Ravi Kumar",
                "apiary_id": "KA-AP-019",
                "floral_source": "Neem blossom",
                "region": "Mysuru, Karnataka",
                "latitude": 12.2958,
                "longitude": 76.6394,
                "harvested_at": datetime(2026, 10, 1, 6, 18, tzinfo=timezone.utc),
                "quantity_kg": 92.0,
                "status": "verified",
                "sync_status": "offline",
                "cloud_status": "local-cache",
                "risk_score": 0.1,
                "purity_badge": "100% purity",
                "certificate_id": "FSSAI-DEMO-26-1036",
                "notes": "Neem blossom batch",
            },
            {
                "id": "HC-KA-2408-003",
                "beekeeper": "Meera Gowda",
                "apiary_id": "KA-AP-071",
                "floral_source": "Jamun",
                "region": "Coorg, Karnataka",
                "latitude": 12.3375,
                "longitude": 75.8069,
                "harvested_at": datetime(2026, 9, 30, 8, 5, tzinfo=timezone.utc),
                "quantity_kg": 124.0,
                "status": "verified",
                "sync_status": "offline",
                "cloud_status": "local-cache",
                "risk_score": 0.13,
                "purity_badge": "100% purity",
                "certificate_id": "FSSAI-DEMO-26-1021",
                "notes": "Jamun sample batch",
            },
        ]

        for item in samples:
            if not has_batches:
                db.add(Batch(**item))

        quality_samples = [
            ("HC-KA-2408-001", 17.4, 18.2, 2.1, 0.97, "FSSAI-DEMO-26-1048"),
            ("HC-KA-2408-002", 18.1, 21.6, 1.4, 0.94, "FSSAI-DEMO-26-1036"),
            ("HC-KA-2408-003", 19.2, 32.8, 3.5, 0.91, "FSSAI-DEMO-26-1021"),
        ]
        for batch_id, moisture, hmf, c4_sugar, nmr_score, certificate_id in quality_samples:
            batch_exists = db.query(Batch).filter(Batch.id == batch_id).first()
            test_exists = db.query(QualityTest).filter(QualityTest.batch_id == batch_id).first()
            if batch_exists and not test_exists:
                db.add(QualityTest(
                    batch_id=batch_id,
                    moisture=moisture,
                    hmf=hmf,
                    c4_sugar=c4_sugar,
                    nmr_score=nmr_score,
                    passed=True,
                    compliance="PASS",
                    certificate_id=certificate_id,
                ))

        db.commit()
    finally:
        db.close()

    from .ledger import append_block, hash_payload

    db = SessionLocal()
    try:
        available_batches = {
            row.id: row.quantity_kg
            for row in db.query(Batch).filter(Batch.id.in_([sample[0] for sample in quality_samples])).all()
        }
        existing_events = {
            (row.batch_id, row.event)
            for row in db.query(BlockRecord).filter(
                BlockRecord.batch_id.in_(available_batches.keys())
            ).all()
        }
    finally:
        db.close()

    for batch_id, moisture, hmf, c4_sugar, nmr_score, certificate_id in quality_samples:
        if batch_id not in available_batches:
            continue
        if (batch_id, "HARVEST_RECORDED") not in existing_events:
            append_block(batch_id, "HARVEST_RECORDED", {
                "sample_record": True,
                "quantity_kg": available_batches[batch_id],
            })
        metrics = {
            "moisture": moisture,
            "hmf": hmf,
            "c4_sugar": c4_sugar,
            "nmr_score": nmr_score,
        }
        signed_record = {
            "batch_id": batch_id,
            "certificate_id": certificate_id,
            "metrics": metrics,
            "passed": True,
        }
        if (batch_id, "LAB_CERTIFIED") not in existing_events:
            append_block(batch_id, "LAB_CERTIFIED", {
                "certificate_id": certificate_id,
                "moisture": moisture,
                "hmf": hmf,
                "c4_sugar": c4_sugar,
                "nmr_score": nmr_score,
                "passed": True,
                "digital_signature": hash_payload(signed_record),
                "sample_record": True,
            })
