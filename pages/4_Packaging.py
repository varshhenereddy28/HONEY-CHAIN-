from __future__ import annotations

import csv
import io
import zipfile

import qrcode
import streamlit as st

from backend.database import Batch, PackagingRun, SessionLocal
from backend.ledger import append_block

st.set_page_config(page_title="Packaging", layout="wide")
from backend.ui import apply_theme, render_navigation

apply_theme()
render_navigation("Packaging")
st.title("Step 4 · Packaging")
st.caption("Verified batch selector and serialized QR label generation.")


def make_qr_bytes(payload: str) -> bytes:
    qr = qrcode.QRCode(version=2, box_size=10, border=4)
    qr.add_data(payload)
    qr.make(fit=True)
    image = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def build_label_bundle(batch_id: str, serial_count: int) -> tuple[bytes, list[str]]:
    archive_buffer = io.BytesIO()
    manifest = io.StringIO()
    writer = csv.writer(manifest)
    writer.writerow(["batch_id", "serial", "qr_payload"])
    serials = []

    with zipfile.ZipFile(archive_buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for index in range(1, serial_count + 1):
            serial = f"{batch_id}-{index:05d}"
            payload = f"HONEYCHAIN|{batch_id}|SERIAL:{serial}"
            serials.append(serial)
            writer.writerow([batch_id, serial, payload])
            archive.writestr(f"labels/{serial}.png", make_qr_bytes(payload))
        archive.writestr("manifest.csv", manifest.getvalue())

    return archive_buffer.getvalue(), serials


db = SessionLocal()
try:
    batches = db.query(Batch).filter(Batch.status == "verified").order_by(Batch.harvested_at.desc()).all()
finally:
    db.close()

if not batches:
    st.info("No verified batches are available for packaging.")
    st.stop()

batch_id = st.selectbox("Select verified batch", [batch.id for batch in batches])
serial_count = st.number_input("Product serial count", min_value=1, max_value=2000, value=32)

if st.button("Generate QR labels"):
    bundle, serials = build_label_bundle(batch_id, int(serial_count))
    payload = f"HONEYCHAIN|{batch_id}|SERIAL:{serials[0]}"
    qr_bytes = make_qr_bytes(payload)
    st.image(qr_bytes, caption=f"QR for {batch_id}", use_container_width=True)
    st.write(f"First serial: {serials[0]} · Last serial: {serials[-1]}")
    st.download_button(
        "Download printable QR labels and manifest",
        data=bundle,
        file_name=f"{batch_id}_labels.zip",
        mime="application/zip",
    )

    db = SessionLocal()
    try:
        row = PackagingRun(batch_id=batch_id, serial_count=int(serial_count), qr_payload=payload)
        db.add(row)
        db.commit()
        append_block(batch_id, "PACKAGED", {"serial_count": int(serial_count), "qr_payload": payload})
        st.success(f"Packaging record created for {batch_id}.")
    finally:
        db.close()
