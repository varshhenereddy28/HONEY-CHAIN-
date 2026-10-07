from __future__ import annotations

import streamlit as st
import pandas as pd

from backend.database import Batch, SessionLocal
from backend.ledger import get_blocks, verify_chain
from backend.ml_engine import flag_fraud

st.set_page_config(page_title="Ledger", layout="wide")
from backend.ui import apply_theme, render_navigation

apply_theme()
render_navigation("Ledger")
st.title("Step 3 · Ledger")
st.caption("Block explorer and anti-clone risk intelligence.")

valid, errors = verify_chain()
if valid:
    st.success("Blockchain integrity verified across all ledger entries.")
else:
    st.error("Ledger integrity issues detected.")
    st.json({"errors": errors})

blocks = get_blocks()
if blocks:
    block_df = pd.DataFrame(blocks)
    st.dataframe(block_df[["height", "batch_id", "event", "timestamp", "previous_hash", "hash"]], use_container_width=True)
else:
    st.info("No ledger blocks yet.")

search = st.text_input("Filter by batch, event, timestamp, hash, or payload")
if search:
    filtered = [block for block in blocks if search.lower() in str(block).lower()]
    if filtered:
        st.dataframe(pd.DataFrame(filtered), use_container_width=True)
    else:
        st.warning("No matching blocks found.")

if blocks:
    block_choices = {
        f"#{block['height']} · {block['event']} · {block['batch_id']}": block
        for block in blocks
    }
    selected_label = st.selectbox("Inspect block", list(block_choices))
    with st.expander("Selected block details", expanded=False):
        st.json(block_choices[selected_label])

st.markdown("---")

st.subheader("ML anti-clone risk overview")
db = SessionLocal()
try:
    batches = db.query(Batch).all()
    history = [
        {
            "id": row.id,
            "apiary_id": row.apiary_id,
            "quantity_kg": row.quantity_kg,
            "status": row.status,
        }
        for row in batches
    ]
    scan_counts: dict[str, int] = {}
    for block in blocks:
        if block["event"] == "SCAN_RECORDED":
            scan_counts[block["batch_id"]] = scan_counts.get(block["batch_id"], 0) + 1
    for row in batches:
        result = flag_fraud({
            "id": row.id,
            "apiary_id": row.apiary_id,
            "quantity_kg": row.quantity_kg,
            "duplicate_scan_count": max(0, scan_counts.get(row.id, 0) - 1),
            "status": row.status,
        }, [item for item in history if item["id"] != row.id])
        st.write(f"{row.id}: {result['status']} · risk {result['risk_score']:.3f}")
finally:
    db.close()
