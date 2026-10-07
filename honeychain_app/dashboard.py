from __future__ import annotations

import io
from datetime import datetime, timezone
from typing import Any

import pandas as pd
import qrcode
import streamlit as st
from streamlit_geolocation import streamlit_geolocation

from honeychain.ledger import (
    batch_proof,
    certify_batch,
    get_batch,
    get_batches,
    record_harvest,
    record_packaging,
    verify_chain,
)


def build_dashboard_summary() -> dict[str, Any]:
    batches = get_batches()
    if not batches:
        return {
            "total_batches": 0,
            "verified_batches": 0,
            "pending_batches": 0,
            "latest_batch": None,
            "chain_valid": True,
            "block_count": 0,
        }

    valid, block_count = verify_chain()
    summary = {
        "total_batches": len(batches),
        "verified_batches": sum(1 for batch in batches if batch.get("status") == "verified"),
        "pending_batches": sum(1 for batch in batches if batch.get("status") == "pending"),
        "latest_batch": max(batches, key=lambda item: item.get("harvested_at", "")),
        "chain_valid": valid,
        "block_count": block_count,
    }
    return summary


def _safe_geolocation() -> dict[str, float | None]:
    try:
        location = streamlit_geolocation()
        if isinstance(location, dict):
            return {
                "latitude": location.get("latitude"),
                "longitude": location.get("longitude"),
            }
    except Exception:
        pass
    return {"latitude": None, "longitude": None}


def _generate_batch_id() -> str:
    timestamp = datetime.now(timezone.utc)
    suffix = timestamp.strftime("%y%m%d%H%M%S")
    return f"HC-{timestamp.strftime('%d%m%y')}-{suffix}"


def _render_qr_code(data: str, label: str) -> None:
    qr = qrcode.QRCode(version=1, box_size=8, border=4)
    qr.add_data(data)
    qr.make(fit=True)
    image = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    st.image(buf.getvalue(), caption=label, use_container_width=True)


def render_beekeeper() -> None:
    st.header("Beekeeper portal")
    st.caption("Record harvests and attach GPS coordinates from the field.")

    location = _safe_geolocation()
    col_a, col_b = st.columns(2)
    with col_a:
        beekeeper = st.text_input("Beekeeper name", value="Lakshmi Devi")
        apiary = st.text_input("Apiary ID", value="KA-AP-042")
        floral_source = st.text_input("Floral source", value="Wild forest multiflora")
    with col_b:
        region = st.text_input("Region", value="Chikkamagaluru, Karnataka")
        quantity = st.number_input("Quantity (kg)", min_value=1.0, value=92.0, step=0.5)
        harvested_at = st.datetime_input("Harvest timestamp", value=datetime.now(timezone.utc))

    latitude = st.number_input("Latitude", value=float(location["latitude"]) if location["latitude"] is not None else 13.3153, format="%.6f")
    longitude = st.number_input("Longitude", value=float(location["longitude"]) if location["longitude"] is not None else 75.7754, format="%.6f")

    with st.form("harvest_form"):
        submitted = st.form_submit_button("Record harvest")
        if submitted:
            batch_id = _generate_batch_id()
            payload = {
                "id": batch_id,
                "beekeeper": beekeeper,
                "apiary": apiary,
                "floral_source": floral_source,
                "region": region,
                "latitude": latitude,
                "longitude": longitude,
                "harvested_at": harvested_at.isoformat(),
                "quantity_kg": float(quantity),
            }
            block = record_harvest(payload)
            st.success(f"Harvest recorded: {batch_id}")
            st.json({"batch_id": batch_id, "event": block["event"], "hash": block["hash"]})


def render_lab() -> None:
    st.header("Lab portal")
    st.caption("Evaluate quality metrics and sign a demo certificate.")

    batches = get_batches()
    options = {batch["id"]: f"{batch['id']} · {batch['beekeeper']} · {batch['status']}" for batch in batches}
    batch_id = st.selectbox("Select harvest batch", list(options.keys()), format_func=lambda key: options[key]) if options else None

    if batch_id is None:
        st.info("No batches are available yet. Record a harvest first.")
        return

    current = get_batch(batch_id)
    with st.form("certify_form"):
        moisture = st.number_input("Moisture %", min_value=0.0, max_value=100.0, value=float(current["moisture"] or 18.2), step=0.1)
        hmf = st.number_input("HMF", min_value=0.0, max_value=200.0, value=float(current["hmf"] or 18.2), step=0.1)
        c4_sugar = st.number_input("C4 sugar", min_value=0.0, max_value=50.0, value=float(current["c4_sugar"] or 2.1), step=0.1)
        nmr_score = st.number_input("NMR score", min_value=0.0, max_value=1.0, value=float(current["nmr_score"] or 0.97), step=0.01)

        submitted = st.form_submit_button("Certify batch")
        if submitted:
            updated, signature = certify_batch(batch_id, {
                "moisture": float(moisture),
                "hmf": float(hmf),
                "c4_sugar": float(c4_sugar),
                "nmr_score": float(nmr_score),
            })
            st.success(f"Status: {updated['status']}")
            st.json({
                "batch_id": batch_id,
                "certificate_id": updated["certificate_id"],
                "signature": signature,
                "metrics": {
                    "moisture": updated["moisture"],
                    "hmf": updated["hmf"],
                    "c4_sugar": updated["c4_sugar"],
                    "nmr_score": updated["nmr_score"],
                },
            })


def render_ledger() -> None:
    st.header("Ledger")
    valid, block_count = verify_chain()
    st.metric("Chain status", "Valid" if valid else "Invalid", help="SHA-256 event integrity check across the append-only ledger.")
    st.metric("Blocks", block_count)

    batches = get_batches()
    df = pd.DataFrame(batches)
    if not df.empty:
        st.dataframe(df[["id", "beekeeper", "apiary", "region", "status", "certificate_id"]], use_container_width=True)
    else:
        st.info("No ledger records yet.")

    if st.button("Refresh chain health"):
        st.rerun()


def render_packaging() -> None:
    st.header("Packaging")
    st.caption("Generate pack labels and serial numbers for verified batches.")

    batches = [batch for batch in get_batches() if batch.get("status") == "verified"]
    if not batches:
        st.info("No verified batches are available for packaging yet.")
        return

    batch_id = st.selectbox("Verified batch", [batch["id"] for batch in batches])
    serial_count = st.number_input("Serial count", min_value=1, max_value=10000, value=25)

    if st.button("Create packaging record"):
        record_packaging(batch_id, int(serial_count))
        st.success(f"Packaging run created for {batch_id} with {serial_count} serials.")
        _render_qr_code(batch_id, f"Batch QR for {batch_id}")


def render_verify() -> None:
    st.header("Verify")
    st.caption("Scan or fetch a batch to confirm origin and proof.")

    batches = get_batches()
    batch_id = st.selectbox("Batch lookup", ["-"] + [batch["id"] for batch in batches], index=0)
    if batch_id != "-":
        batch = get_batch(batch_id)
        verified = batch_proof(batch) if batch else ""
        st.json({
            "batch": batch,
            "proof_hash": verified,
        })
        if batch:
            _render_qr_code(batch_id, f"Verification QR: {batch_id}")
    else:
        st.info("Choose a batch to inspect its provenance and proof.")


def main() -> None:
    summary = build_dashboard_summary()
    st.title("HoneyChain Traceability Dashboard")
    st.caption("A Python version of the supply-chain dashboard using Streamlit and the SQLite ledger.")

    total, verified, pending, blocks = (
        summary["total_batches"],
        summary["verified_batches"],
        summary["pending_batches"],
        summary["block_count"],
    )
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total batches", total)
    col2.metric("Verified", verified)
    col3.metric("Pending", pending)
    col4.metric("Ledger blocks", blocks)

    st.markdown("---")
    tabs = st.tabs(["Beekeeper", "Lab", "Ledger", "Packaging", "Verify"])

    with tabs[0]:
        render_beekeeper()
    with tabs[1]:
        render_lab()
    with tabs[2]:
        render_ledger()
    with tabs[3]:
        render_packaging()
    with tabs[4]:
        render_verify()


if __name__ == "__main__":
    main()
