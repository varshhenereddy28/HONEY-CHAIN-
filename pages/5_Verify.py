from __future__ import annotations

import hashlib

import cv2
import numpy as np
import streamlit as st

try:
    from streamlit_qrcode_scanner import qrcode_scanner
except Exception:  # pragma: no cover
    qrcode_scanner = None

from backend.database import Batch, QualityTest, SessionLocal
from backend.ledger import append_block, get_blocks, verify_chain
from backend.ml_engine import flag_fraud

st.set_page_config(page_title="Verify", layout="wide")
from backend.ui import apply_theme, render_navigation

apply_theme()
render_navigation("Verify")
st.title("Step 5 · Verify")
st.caption("Consumer verification and live QR scanning for smartphones.")

st.info("Live mobile camera scanning requires HTTPS or localhost. For phone testing, run `npx ngrok http 8501` in a separate terminal.")

def parse_batch_id(value: str) -> str:
    value = value.strip()
    if value.startswith("HONEYCHAIN|"):
        return value.split("|", 2)[1].strip()
    return value

def decode_uploaded_qr(image_bytes: bytes) -> str | None:
    image = cv2.imdecode(np.frombuffer(image_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        return None
    decoded, _, _ = cv2.QRCodeDetector().detectAndDecode(image)
    return decoded.strip() or None


batch_id = None
if qrcode_scanner is not None:
    st.caption("The scanner prefers the rear-facing camera. On phones, open this page over HTTPS or localhost.")
    scan_result = qrcode_scanner(key="honeychain-verify-scanner")
    if isinstance(scan_result, str) and scan_result.strip():
        batch_id = parse_batch_id(scan_result)
        st.success(f"Scanned batch: {batch_id}")
else:
    st.warning("Live camera scanner is unavailable; upload a QR image or enter a batch ID.")

file_upload = st.file_uploader("Or upload a QR image from the phone gallery", type=["png", "jpg", "jpeg"])
if file_upload is not None:
    uploaded_value = decode_uploaded_qr(file_upload.getvalue())
    if uploaded_value:
        batch_id = parse_batch_id(uploaded_value)
        st.success(f"QR image decoded: {batch_id}")
    else:
        st.warning("No readable QR code was found in that image.")

manual_id = st.text_input("Lookup batch ID manually", disabled=bool(batch_id))
lookup_id = batch_id or manual_id.strip()

if lookup_id:
    db = SessionLocal()
    try:
        batch = db.query(Batch).filter(Batch.id == lookup_id).first()
        latest_test = (
            db.query(QualityTest)
            .filter(QualityTest.batch_id == lookup_id)
            .order_by(QualityTest.created_at.desc())
            .first()
        )
        history = db.query(Batch).filter(Batch.id != lookup_id).all()
        batch_history = [
            {
                "id": row.id,
                "apiary_id": row.apiary_id,
                "quantity_kg": row.quantity_kg,
                "status": row.status,
            }
            for row in history
        ]
    finally:
        db.close()

    if batch is None:
        st.warning("No matching batch found.")
    else:
        if batch_id and st.session_state.get("last_logged_scan") != batch_id:
            append_block(batch_id, "SCAN_RECORDED", {"source": "camera-or-image"})
            st.session_state["last_logged_scan"] = batch_id

        blocks = get_blocks()
        batch_blocks = [block for block in blocks if block["batch_id"] == lookup_id]
        scan_count = sum(
            block["batch_id"] == lookup_id and block["event"] == "SCAN_RECORDED"
            for block in blocks
        )
        lab_block = next(
            (
                block for block in reversed(batch_blocks)
                if block["event"] == "LAB_CERTIFIED"
            ),
            None,
        )
        risk = flag_fraud(
            {
                "id": batch.id,
                "apiary_id": batch.apiary_id,
                "quantity_kg": batch.quantity_kg,
                "duplicate_scan_count": max(0, scan_count - 1),
                "status": batch.status,
            },
            batch_history,
        )
        chain_valid, chain_errors = verify_chain()
        proof = batch_blocks[-1]["hash"] if batch_blocks else "No ledger proof recorded"
        st.metric("Purity badge", batch.purity_badge or "Pending lab review")
        st.metric("Risk status", risk["status"], delta=f"Score {risk['risk_score']:.3f}")
        st.metric("Batch status", batch.status)

        col1, col2 = st.columns(2)
        with col1:
            st.json({
                "batch_id": batch.id,
                "beekeeper": batch.beekeeper,
                "apiary_id": batch.apiary_id,
                "region": batch.region,
                "floral_source": batch.floral_source,
                "quantity_kg": batch.quantity_kg,
            })
        with col2:
            st.json({
                "certificate_id": batch.certificate_id,
                "sha256_ledger_proof": proof,
                "certificate_signature": (
                    lab_block["payload"].get("digital_signature") if lab_block else None
                ),
                "chain_valid": chain_valid,
                "chain_errors": chain_errors,
                "risk_score": risk["risk_score"],
                "duplicate_scan_count": scan_count,
                "sync_status": batch.sync_status,
            })

        st.map(data={"lat": [batch.latitude], "lon": [batch.longitude]})
        st.subheader("Lab metrics")
        if latest_test:
            st.json({
                "moisture": latest_test.moisture,
                "hmf": latest_test.hmf,
                "c4_sugar": latest_test.c4_sugar,
                "nmr_score": latest_test.nmr_score,
                "compliance": latest_test.compliance,
                "certificate_id": latest_test.certificate_id,
            })
        else:
            st.info("No laboratory test has been recorded for this batch.")
else:
    st.info("Scan a QR code or enter a batch ID to verify authenticity.")
