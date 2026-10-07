from __future__ import annotations

import streamlit as st


PAGES = {
    "Dashboard": None,
    "Beekeeper": "pages/1_Beekeeper.py",
    "Lab": "pages/2_Lab.py",
    "Ledger": "pages/3_Ledger.py",
    "Packaging": "pages/4_Packaging.py",
    "Verify": "pages/5_Verify.py",
}


def apply_theme() -> None:
    st.markdown(
        """
        <style>
        :root { color-scheme: dark; }
        .stApp { background: #0f172a; color: #e2e8f0; }
        [data-testid="stHeader"] { background: rgba(15, 23, 42, .94); }
        [data-testid="stSidebarNav"] { display: none; }
        .main .block-container { max-width: 1200px; padding-top: 1.5rem; }
        [data-testid="stMetric"], [data-testid="stVerticalBlockBorderWrapper"] {
            background: #172235; border: 1px solid #29384e; border-radius: 8px;
            padding: .85rem;
        }
        div[data-testid="stDataFrame"] { border: 1px solid #29384e; border-radius: 8px; }
        @media (max-width: 600px) {
            .main .block-container {
                max-width: 480px; margin: 0 auto; padding: 1rem 1rem 6rem;
            }
            div[data-testid="stElementContainer"]:has(iframe[title*="streamlit_option_menu"]) {
                position: fixed; z-index: 1000; bottom: 0; left: 0; right: 0;
                background: #111c2e; border-top: 1px solid #29384e;
                padding: .35rem max(1rem, env(safe-area-inset-left));
            }
            div[data-testid="stElementContainer"]:has(iframe[title*="streamlit_option_menu"]) iframe {
                width: 100% !important;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_navigation(current_page: str) -> None:
    labels = list(PAGES)
    icons = ["grid-1x2", "flower1", "clipboard2-pulse", "diagram-3", "box-seam", "qr-code"]
    try:
        from streamlit_option_menu import option_menu

        selected = option_menu(
            "HoneyChain",
            labels,
            icons=icons,
            menu_icon="hexagon-half",
            orientation="horizontal",
            default_index=labels.index(current_page),
            key=f"honeychain-nav-{current_page.lower()}",
            styles={
                "container": {"padding": "0", "background-color": "#111c2e"},
                "icon": {"color": "#fbbf24", "font-size": "16px"},
                "nav-link": {"color": "#cbd5e1", "font-size": "14px", "margin": "2px"},
                "nav-link-selected": {"background-color": "#334155", "color": "#ffffff"},
            },
        )
    except ImportError:
        selected = st.radio("HoneyChain", labels, horizontal=True, index=labels.index(current_page))

    if selected != current_page:
        destination = PAGES[selected] or "app.py"
        st.switch_page(destination)
