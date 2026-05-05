"""Tema executivo dark + cores vivas — CSS compartilhado entre as páginas."""
import streamlit as st

_EXEC_CSS = """
<style>
.stApp {
    background:
        radial-gradient(circle at 0% 0%, rgba(255, 75, 110, 0.18) 0%, transparent 45%),
        radial-gradient(circle at 100% 0%, rgba(100, 65, 255, 0.20) 0%, transparent 45%),
        radial-gradient(circle at 50% 100%, rgba(0, 200, 200, 0.10) 0%, transparent 50%),
        linear-gradient(135deg, #0B1226 0%, #14102E 100%);
    background-attachment: fixed;
}

section[data-testid="stSidebar"] > div {
    background: linear-gradient(180deg, rgba(27, 41, 66, 0.90) 0%, rgba(15, 23, 41, 0.95) 100%);
    backdrop-filter: blur(12px);
    border-right: 1px solid rgba(255, 255, 255, 0.06);
}

.exec-header {
    background: linear-gradient(135deg, #FF4B6E 0%, #6441FF 50%, #00D2D2 100%);
    padding: 28px 32px;
    border-radius: 16px;
    margin-bottom: 28px;
    box-shadow:
        0 10px 40px rgba(255, 75, 110, 0.25),
        0 4px 16px rgba(100, 65, 255, 0.20);
    position: relative;
    overflow: hidden;
}
.exec-header::after {
    content: "";
    position: absolute;
    top: -50%; right: -10%;
    width: 400px; height: 400px;
    background: radial-gradient(circle, rgba(255,255,255,0.15) 0%, transparent 70%);
    pointer-events: none;
}
.exec-header h1 {
    color: #FFFFFF;
    font-size: 2.2rem;
    font-weight: 800;
    margin: 0;
    letter-spacing: -0.5px;
    text-shadow: 0 2px 12px rgba(0,0,0,0.25);
}
.exec-header p {
    color: rgba(255, 255, 255, 0.92);
    font-size: 1rem;
    margin: 6px 0 0 0;
    font-weight: 500;
}

div[data-testid="stMetric"] {
    background: linear-gradient(145deg, #1E2A47 0%, #161F38 100%);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 14px;
    padding: 22px 22px 18px 22px;
    box-shadow:
        0 8px 24px rgba(0, 0, 0, 0.35),
        inset 0 1px 0 rgba(255, 255, 255, 0.05);
    transition: transform 0.18s ease, box-shadow 0.18s ease;
}
div[data-testid="stMetric"]:hover {
    transform: translateY(-3px);
    box-shadow:
        0 14px 36px rgba(255, 75, 110, 0.25),
        inset 0 1px 0 rgba(255, 255, 255, 0.08);
}
div[data-testid="stMetric"]::before {
    content: "";
    display: block;
    height: 3px;
    margin: -22px -22px 18px -22px;
    border-radius: 14px 14px 0 0;
    background: linear-gradient(90deg, #FF4B6E, #6441FF, #00D2D2);
}
div[data-testid="stMetric"] label {
    color: #B8C4D9 !important;
    font-size: 0.78rem !important;
    font-weight: 600 !important;
    text-transform: uppercase;
    letter-spacing: 0.8px;
}
div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
    color: #FFFFFF !important;
    font-size: 1.85rem !important;
    font-weight: 800 !important;
    letter-spacing: -0.5px;
    line-height: 1.1;
}

h2, h3 {
    color: #F5F7FA !important;
    font-weight: 700 !important;
    letter-spacing: -0.3px;
}
h2 { font-size: 1.4rem !important; margin-top: 1.2rem !important; }

div[data-testid="stPlotlyChart"] {
    background: linear-gradient(145deg, #1E2A47 0%, #161F38 100%);
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 14px;
    padding: 18px;
    box-shadow: 0 6px 20px rgba(0,0,0,0.30);
}

div[data-testid="stDataFrame"] {
    background: linear-gradient(145deg, #1E2A47 0%, #161F38 100%);
    border-radius: 14px;
    padding: 4px;
    box-shadow: 0 6px 20px rgba(0,0,0,0.30);
    border: 1px solid rgba(255, 255, 255, 0.06);
}

.stButton > button, .stDownloadButton > button {
    background: linear-gradient(135deg, #FF4B6E 0%, #6441FF 100%);
    color: #FFFFFF;
    border: none;
    border-radius: 10px;
    font-weight: 700;
    padding: 0.5rem 1rem;
    box-shadow: 0 4px 14px rgba(255, 75, 110, 0.35);
    transition: transform 0.15s ease, box-shadow 0.15s ease;
}
.stButton > button:hover, .stDownloadButton > button:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 22px rgba(255, 75, 110, 0.50);
}

div[data-baseweb="tag"] {
    background: linear-gradient(135deg, #FF4B6E 0%, #6441FF 100%) !important;
    color: white !important;
    border: none !important;
}

/* ============ RESPONSIVO — Celular (≤ 768px) ============ */
@media (max-width: 768px) {
    /* Padding geral menor */
    .main .block-container {
        padding-top: 0.5rem !important;
        padding-left: 0.6rem !important;
        padding-right: 0.6rem !important;
        padding-bottom: 1rem !important;
    }

    /* Header mais compacto */
    .exec-header {
        padding: 16px 18px !important;
        margin-bottom: 16px !important;
        border-radius: 12px !important;
    }
    .exec-header h1 {
        font-size: 1.35rem !important;
        line-height: 1.2 !important;
    }
    .exec-header p {
        font-size: 0.85rem !important;
        margin-top: 4px !important;
    }

    /* Empilha colunas verticalmente em vez de lado a lado */
    [data-testid="stHorizontalBlock"] {
        flex-direction: column !important;
        gap: 10px !important;
    }
    [data-testid="stHorizontalBlock"] > [data-testid="column"] {
        width: 100% !important;
        min-width: 0 !important;
        flex: 1 1 100% !important;
    }

    /* KPI cards mais compactos */
    div[data-testid="stMetric"] {
        padding: 14px 14px 12px 14px !important;
    }
    div[data-testid="stMetric"]::before {
        margin: -14px -14px 12px -14px !important;
    }
    div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
        font-size: 1.4rem !important;
    }
    div[data-testid="stMetric"] label {
        font-size: 0.68rem !important;
        letter-spacing: 0.5px !important;
    }

    /* Sub-headers menores */
    h2 { font-size: 1.05rem !important; margin-top: 0.6rem !important; }
    h3 { font-size: 0.95rem !important; }

    /* Containers de gráfico com menos padding */
    div[data-testid="stPlotlyChart"] {
        padding: 10px !important;
    }

    /* Sidebar — abre como overlay; chip mais compacto */
    section[data-testid="stSidebar"] {
        width: 85vw !important;
    }
    div[data-baseweb="tag"] {
        font-size: 0.75rem !important;
    }
}

/* ============ Telas muito pequenas (≤ 420px) ============ */
@media (max-width: 420px) {
    .exec-header h1 { font-size: 1.15rem !important; }
    div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
        font-size: 1.2rem !important;
    }
}

/* ============ Menu de navegação (st.navigation) ============ */
section[data-testid="stSidebar"] [data-testid="stSidebarNav"] {
    padding: 1rem 0.5rem 0.5rem 0.5rem;
}
section[data-testid="stSidebar"] [data-testid="stSidebarNav"] ul {
    list-style: none;
    padding: 0;
    margin: 0;
}
section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 10px 14px;
    margin: 4px 0;
    border-radius: 10px;
    color: #B8C4D9 !important;
    text-decoration: none !important;
    font-weight: 600;
    font-size: 0.95rem;
    transition: all 0.18s ease;
    border: 1px solid transparent;
}
section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a:hover {
    background: rgba(255, 75, 110, 0.12);
    color: #FFFFFF !important;
    border-color: rgba(255, 75, 110, 0.35);
    transform: translateX(2px);
}
/* Item ATIVO — gradiente vibrante */
section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a[aria-current="page"],
section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a.active {
    background: linear-gradient(135deg, #FF4B6E 0%, #6441FF 100%);
    color: #FFFFFF !important;
    box-shadow: 0 6px 18px rgba(255, 75, 110, 0.35);
    border-color: transparent;
}
/* Ícone do item de menu */
section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a span:first-child {
    font-size: 1.15rem;
}

footer { visibility: hidden; }
#MainMenu { visibility: hidden; }
</style>
"""


def apply_theme() -> None:
    """Injeta o CSS executivo. Chame logo após `st.set_page_config`."""
    st.markdown(_EXEC_CSS, unsafe_allow_html=True)


def render_header(title: str, subtitle: str = "") -> None:
    """Renderiza o banner com gradiente vibrante."""
    st.markdown(
        f"""
        <div class="exec-header">
          <h1>{title}</h1>
          {f'<p>{subtitle}</p>' if subtitle else ''}
        </div>
        """,
        unsafe_allow_html=True,
    )
