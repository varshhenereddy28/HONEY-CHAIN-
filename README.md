# HoneyChain
# HoneyChain

HoneyChain is a Python-first honey traceability prototype. Streamlit provides the responsive workflow dashboard, FastAPI exposes the backend API, SQLAlchemy stores batches and ledger records, and SHA-256 links the append-only event chain.

## Run the dashboard

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
streamlit run app.py
```

The first run creates `honeychain.db` and seeds three sample batches with quality tests and linked ledger events.

## Run the API

```powershell
python -m uvicorn backend.main:app --reload
```

API routes include `/health`, `/batches`, `/ledger/verify`, and `/sync/status`. Set `DATABASE_URL` to a SQLAlchemy PostgreSQL URL to use a PostgreSQL database instead of the local SQLite default. The app marks local writes as pending/offline; a remote sync worker or hosted database is not configured by default.

## Mobile camera testing

Camera access requires HTTPS or localhost. Keep Streamlit running, then start a tunnel in a second terminal:

```bash
npx ngrok http 8501
```

Open the generated HTTPS URL on the phone and grant camera permission. The scanner component requests the rear-facing environment camera. Gallery QR images can also be uploaded and decoded locally. The app can be deployed to Streamlit Community Cloud for HTTPS testing using this repository and `requirements.txt`.

## Project structure

```text
app.py                     Streamlit dashboard entrypoint
backend/
  database.py              SQLAlchemy models, SQLite setup, and demo seed
  ledger.py                SHA-256 event chain
  main.py                  FastAPI routes
  ml_engine.py             Batch-volume and repeated-scan risk scoring
  ui.py                    Shared theme and workflow navigation
pages/
  1_Beekeeper.py           Harvest and GPS capture
  2_Lab.py                 Quality tests and signed PDF certificate
  3_Ledger.py              Block explorer and risk overview
  4_Packaging.py           Serialized QR label export
  5_Verify.py              Camera/gallery verification and provenance
requirements.txt           Python dependencies
tests/                     Smoke tests
```