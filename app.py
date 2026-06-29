"""Entrypoint do Streamlit — orquestra o tema e a navegação multi-página.

A navegação fica visível na sidebar com nomes amigáveis e ícones (não os
nomes brutos dos arquivos `.py`). Adicionar novas páginas é só
acrescentar uma linha em `pages_config` apontando para o módulo em `views/`.
"""
from __future__ import annotations

import streamlit as st

from src.theme import apply_theme

# ---------------------------------------------------------------------------
# Configuração global
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Gastos Mensais — Executivo",
    page_icon="💳",
    layout="wide",
    initial_sidebar_state="expanded",
)
apply_theme()

# ---------------------------------------------------------------------------
# Menu lateral (st.navigation)
# ---------------------------------------------------------------------------
pages_config = [
    st.Page(
        "views/dashboard.py",
        title="Dashboard",
        icon="📊",
        default=True,
    ),
    st.Page(
        "views/adicionar.py",
        title="Adicionar",
        icon="➕",
    ),
    st.Page(
        "views/classificacao.py",
        title="Classificação",
        icon="🏷️",
    ),
]

navegacao = st.navigation(pages_config, position="sidebar", expanded=True)
navegacao.run()
