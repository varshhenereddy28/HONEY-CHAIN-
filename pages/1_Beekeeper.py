from __future__ import annotations

from datetime import datetime, timezone

import streamlit as st

from backend.database import Batch, SessionLocal
from backend.ledger import append_block

try:
    from streamlit_geolocation import streamlit_geolocation
except Exception:  # pragma: no cover
    streamlit_geolocation = None

st.set_page_config(page_title="Beekeeper", layout="wide")
from backend.ui import apply_theme, render_navigation

apply_theme()
render_navigation("Beekeeper")
st.title("Step 1 · Beekeeper")
st.caption("Offline-first harvest registration and GPS capture.")

location = None
if streamlit_geolocation is not None:
    try:
        location = streamlit_geolocation()
        if location and isinstance(location, dict):
            st.success("GPS capture available in the browser context.")
    except Exception:
        st.warning("Browser geolocation is not available in this context; you can still enter coordinates manually.")

with st.form("beekeeper_form"):
    col1, col2 = st.columns(2)
    with col1:
        beekeeper = st.text_input("Beekeeper name", value="Lakshmi Devi")
        apiary_id = st.text_input("Apiary ID", value="KA-AP-042")
        floral_source = st.text_input("Floral source", value="Wild forest multiflora")
    with col2:
        region = st.text_input("Region", value="Chikkamagaluru, Karnataka")
        quantity_kg = st.number_input("Quantity (kg)", min_value=1.0, value=186.0, step=0.5)
        latitude = st.number_input(
            "Latitude",
            value=float(location.get("latitude") or 13.3153) if location else 13.3153,
            format="%.6f",
        )
        longitude = st.number_input(
            "Longitude",
            value=float(location.get("longitude") or 75.7754) if location else 75.7754,
            format="%.6f",
        )

    submitted = st.form_submit_button("Log harvest")

if submitted:
    batch_id = f"HC-{datetime.now(timezone.utc).strftime('%y%m%d%H%M%S')}"
    db = SessionLocal()
    try:
        batch = Batch(
            id=batch_id,
            beekeeper=beekeeper,
            apiary_id=apiary_id,
            floral_source=floral_source,
            region=region,
            latitude=float(latitude),
            longitude=float(longitude),
            harvested_at=datetime.now(timezone.utc),
            quantity_kg=float(quantity_kg),
            status="pending",
            sync_status="offline",
            cloud_status="local-cache",
            purity_badge="pending",
        )
        db.add(batch)
        db.commit()
        append_block(batch_id, "HARVEST_RECORDED", {
            "apiary_id": apiary_id,
            "floral_source": floral_source,
            "quantity_kg": float(quantity_kg),
            "region": region,
        })
        st.success(f"Harvest logged in local cache: {batch_id}")
        st.info("Sync status: local-cache. Cloud synchronization is pending.")
        st.json({
            "batch_id": batch_id,
            "sync_status": "offline",
            "google_maps": f"https://maps.google.com/?q={latitude},{longitude}",
        })
    finally:
        db.close()

st.markdown("---")
st.subheader("Recent local harvests")
db = SessionLocal()
try:
    rows = db.query(Batch).order_by(Batch.harvested_at.desc()).limit(5).all()
    if rows:
        for row in rows:
            st.write(f"- {row.id} | {row.beekeeper} | {row.apiary_id} | {row.quantity_kg} kg")
    else:
        st.info("No harvests logged yet.")
finally:
    db.close()
