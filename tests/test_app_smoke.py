import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "app.py"


def test_app_module_exists_and_exports_dashboard_builder():
    assert APP_PATH.exists(), "app.py is required for the Streamlit dashboard entrypoint"

    spec = importlib.util.spec_from_file_location("honeychain_app", APP_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)

    assert hasattr(module, "build_dashboard_summary")
    assert callable(module.build_dashboard_summary)
