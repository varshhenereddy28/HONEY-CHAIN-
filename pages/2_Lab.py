from __future__ import annotations

import io
from datetime import datetime, timezone
from hashlib import sha256

import streamlit as st
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.pdfgen import canvas

from backend.database import Batch, QualityTest, SessionLocal
from backend.ledger import append_block, hash_payload

st.set_page_config(page_title="Lab", layout="wide")
from backend.ui import apply_theme, render_navigation

apply_theme()
render_navigation("Lab")
st.title("Step 2 · Lab")
st.caption("Chemical testing and FSSAI compliance validation.")


def calculate_pass(moisture: float, hmf: float, c4_sugar: float, nmr_score: float) -> tuple[bool, str]:
    passed = (
        moisture <= 20
        and hmf <= 80
        and c4_sugar <= 7
        and nmr_score >= 0.9
    )
    return passed, "PASS" if passed else "FAIL"


def build_certificate_pdf(
    batch_id: str,
    certificate_id: str,
    metrics: dict[str, float],
    passed: bool,
    signature: str,
) -> bytes:
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    title = styles["Title"]
    text = styles["BodyText"]
    pdf.setTitle(f"HoneyChain Certificate {batch_id}")
    pdf.setFillColor(colors.HexColor("#0f172a"))
    pdf.drawString(72, 750, "HoneyChain Quality Certificate")
    pdf.drawString(72, 720, f"Batch: {batch_id}")
    pdf.drawString(72, 700, f"Status: {'PASS' if passed else 'FAIL'}")
    pdf.drawString(72, 680, f"Certificate ID: {certificate_id}")
    pdf.drawString(72, 660, f"Moisture %: {metrics['moisture']:.2f}")
    pdf.drawString(72, 640, f"HMF: {metrics['hmf']:.2f}")
    pdf.drawString(72, 620, f"C4 sugar: {metrics['c4_sugar']:.2f}")
    pdf.drawString(72, 600, f"NMR Score: {metrics['nmr_score']:.2f}")
    pdf.drawString(72, 560, f"SHA-256 signature: {signature}")
    pdf.save()
    return buffer.getvalue()


db = SessionLocal()
try:
    batches = db.query(Batch).order_by(Batch.harvested_at.desc()).all()
finally:
    db.close()

if not batches:
    st.info("No batches found. Log a harvest in the Beekeeper page first.")
    st.stop()

batch_options = {batch.id: f"{batch.id} | {batch.beekeeper} | {batch.status}" for batch in batches}
selected_batch_id = st.selectbox("Batch to test", options=list(batch_options.keys()), format_func=lambda key: batch_options[key])

selected_batch = next((batch for batch in batches if batch.id == selected_batch_id), None)

with st.form("lab_form"):
    moisture = st.number_input("Moisture %", min_value=0.0, max_value=100.0, value=18.2, step=0.1)
    hmf = st.number_input("HMF", min_value=0.0, max_value=200.0, value=21.6, step=0.1)
    c4_sugar = st.number_input("C4 sugar", min_value=0.0, max_value=50.0, value=2.1, step=0.1)
    nmr_score = st.number_input("NMR score", min_value=0.0, max_value=1.0, value=0.97, step=0.01)
    submitted = st.form_submit_button("Validate batch")

if submitted:
    passed, result = calculate_pass(float(moisture), float(hmf), float(c4_sugar), float(nmr_score))
    batch_id = selected_batch_id
    certificate_id = f"FSSAI-DEMO-{datetime.now(timezone.utc):%y}-{sha256(f'{batch_id}:{moisture}:{hmf}:{c4_sugar}:{nmr_score}'.encode()).hexdigest()[:8].upper()}"
    metrics = {
        "moisture": float(moisture),
        "hmf": float(hmf),
        "c4_sugar": float(c4_sugar),
        "nmr_score": float(nmr_score),
    }
    signed_record = {
        "batch_id": batch_id,
        "certificate_id": certificate_id,
        "metrics": metrics,
        "passed": passed,
    }
    digital_signature = hash_payload(signed_record)

    db = SessionLocal()
    try:
        batch = db.query(Batch).filter(Batch.id == batch_id).one()
        batch.status = "verified" if passed else "rejected"
        batch.certificate_id = certificate_id
        batch.purity_badge = "100% purity" if passed else "review required"
        db.add(batch)
        test_record = QualityTest(
            batch_id=batch_id,
            moisture=float(moisture),
            hmf=float(hmf),
            c4_sugar=float(c4_sugar),
            nmr_score=float(nmr_score),
            passed=passed,
            compliance=result,
            certificate_id=certificate_id,
        )
        db.add(test_record)
        db.commit()
        append_block(batch_id, "LAB_CERTIFIED", {
            "certificate_id": certificate_id,
            "moisture": float(moisture),
            "hmf": float(hmf),
            "c4_sugar": float(c4_sugar),
            "nmr_score": float(nmr_score),
            "passed": passed,
            "digital_signature": digital_signature,
        })
    finally:
        db.close()

    st.success(f"Compliance result: {result}")
    st.info(f"Certificate ID: {certificate_id}")
    pdf_bytes = build_certificate_pdf(batch_id, certificate_id, metrics, passed, digital_signature)
    st.download_button("Download signed certificate (PDF)", data=pdf_bytes, file_name=f"{batch_id}_certificate.pdf", mime="application/pdf")
