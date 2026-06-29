"""Página principal — Painel Executivo de gastos."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from src.charts import pie_by_category, stacked_evolution, summary_metrics
from src.classifier import classify
from src.config import CATEGORIES, SUBCATEGORIES, TIPOS
from src.drive_loader import current_source, fetch_invoices, filter_by_extension
from src.manual_expenses import manual_to_df
from src.parsers import parse_many
from src.theme import render_header


@st.cache_data(ttl=300, show_spinner="Processando faturas...")
def _load_dataset() -> pd.DataFrame:
    # 1. Carrega e classifica as faturas dos cartões
    files = filter_by_extension(fetch_invoices())
    df_faturas = parse_many(files)
    if not df_faturas.empty:
        df_faturas["data"] = pd.to_datetime(df_faturas["data"], errors="coerce")
        df_faturas = df_faturas.dropna(subset=["data"])
        df_faturas = classify(df_faturas)

    # 2. Carrega despesas manuais (já vêm pré-classificadas pelo formulário)
    df_manual = manual_to_df()

    # 3. Concat — manuais NÃO passam por classify (preserva escolhas do usuário)
    if df_faturas.empty and df_manual.empty:
        return df_faturas
    if df_faturas.empty:
        return df_manual
    if df_manual.empty:
        return df_faturas
    return pd.concat([df_faturas, df_manual], ignore_index=True)


def _fmt_brl(v: float) -> str:
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
render_header(
    "💳 Gastos Mensais — Painel Executivo",
    f"Fonte: <strong>{current_source()}</strong> · Use a barra lateral para filtrar e o botão 🔄 para atualizar.",
)

# ---------------------------------------------------------------------------
# Carga
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("### ⚙️ Controles")
    if st.button("🔄 Recarregar dados", use_container_width=True):
        st.cache_data.clear()
        st.cache_resource.clear()
        st.rerun()

try:
    df = _load_dataset()
except Exception as e:  # noqa: BLE001
    st.error(f"Falha ao carregar dados: {e}")
    st.stop()

if df.empty:
    st.warning(
        "Nenhuma fatura encontrada. "
        "Adicione arquivos em `data/raw/` (ou em `data/raw/<NomeDoCartão>/`)."
    )
    st.stop()

# ---------------------------------------------------------------------------
# Sidebar — filtros
# ---------------------------------------------------------------------------
st.sidebar.markdown("### 🔎 Filtros")

meses = sorted(df["mes_ref"].dropna().unique(), reverse=True)
mes_sel = st.sidebar.selectbox("Mês de Referência (fatura)", meses, index=0)

min_d, max_d = df["data"].min(), df["data"].max()
periodo = st.sidebar.date_input(
    "Período (data da compra)",
    value=(min_d.date(), max_d.date()),
    min_value=min_d.date(),
    max_value=max_d.date(),
)

cartoes_disp = sorted(df["cartao"].dropna().unique().tolist())
cartoes_sel = st.sidebar.multiselect(
    "Cartão", options=cartoes_disp, default=[], placeholder="Todos",
)

estabs = st.sidebar.multiselect(
    "Estabelecimento",
    options=sorted(df["estabelecimento"].unique()),
    default=[],
    placeholder="Todos",
)

cats_sel = st.sidebar.multiselect(
    "Categoria", options=CATEGORIES, default=[], placeholder="Todas",
)

subs_disp = [s for s in SUBCATEGORIES if s and s in set(df["subcategoria"].unique())]
subs_sel = st.sidebar.multiselect(
    "Subcategoria", options=subs_disp, default=[], placeholder="Todas",
)

tipos_sel = st.sidebar.multiselect(
    "Tipo", options=TIPOS, default=[], placeholder="Todos",
)

# Quem pagou — só mostra opções existentes (vem das despesas manuais)
quem_disp = sorted(
    [q for q in df["portador"].dropna().unique() if str(q).strip()]
)
quem_sel = st.sidebar.multiselect(
    "Quem pagou", options=quem_disp, default=[], placeholder="Todos",
)

# ---------------------------------------------------------------------------
# Aplicação dos filtros
#
# `mask_base` aplica TUDO menos o mês de referência — usada pela evolução
# (que precisa de múltiplos meses).
# `mask_view` adiciona o mês — usada pelos cards, pizza e tabela.
# ---------------------------------------------------------------------------
mask_base = pd.Series(True, index=df.index)

if isinstance(periodo, tuple) and len(periodo) == 2:
    d_ini, d_fim = periodo
    mask_base &= (df["data"].dt.date >= d_ini) & (df["data"].dt.date <= d_fim)

if cartoes_sel:
    mask_base &= df["cartao"].isin(cartoes_sel)
if estabs:
    mask_base &= df["estabelecimento"].isin(estabs)
if cats_sel:
    mask_base &= df["categoria"].isin(cats_sel)
if subs_sel:
    mask_base &= df["subcategoria"].isin(subs_sel)
if tipos_sel:
    mask_base &= df["tipo"].isin(tipos_sel)
if quem_sel:
    mask_base &= df["portador"].isin(quem_sel)

mask_view = mask_base & (df["mes_ref"] == mes_sel)
df_view = df.loc[mask_view].copy()
df_evol_base = df.loc[mask_base].copy()

# ---------------------------------------------------------------------------
# KPI Cards
# ---------------------------------------------------------------------------
st.markdown(f"## 📊 Resumo — {mes_sel}")
metrics = summary_metrics(df_view)
cols = st.columns(len(metrics))
for col, (label, value) in zip(cols, metrics.items()):
    if isinstance(value, float):
        col.metric(label, _fmt_brl(value))
    else:
        col.metric(label, value)

st.markdown("")

# ---------------------------------------------------------------------------
# Gráficos
# ---------------------------------------------------------------------------
g1, g2 = st.columns([1, 1.4])

with g1:
    st.markdown("### Distribuição por Categoria")
    if df_view.empty:
        st.info("Sem dados para o mês selecionado.")
    else:
        st.plotly_chart(pie_by_category(df_view), use_container_width=True)

with g2:
    st.markdown("### Evolução — últimos 6 meses")
    ult6 = sorted(df["mes_ref"].dropna().unique())[-6:]
    df_evol = df_evol_base[df_evol_base["mes_ref"].isin(ult6)]
    if df_evol.empty:
        st.info("Sem dados nos últimos 6 meses.")
    else:
        st.plotly_chart(stacked_evolution(df_evol), use_container_width=True)

# ---------------------------------------------------------------------------
# Tabela de detalhamento
# ---------------------------------------------------------------------------
st.markdown("## 📋 Detalhamento de despesas")
st.caption(
    f"Mostrando **{len(df_view)}** lançamentos · "
    f"Reage a todos os filtros da barra lateral (incluindo Mês = {mes_sel})."
)

show = (
    df_view[
        ["data", "estabelecimento", "cartao", "portador",
         "categoria", "subcategoria", "tipo", "valor", "parcela"]
    ]
    .sort_values("data", ascending=False)
    .rename(columns={
        "data": "Data",
        "estabelecimento": "Estabelecimento",
        "cartao": "Cartão",
        "portador": "Quem",
        "categoria": "Categoria",
        "subcategoria": "Subcategoria",
        "tipo": "Tipo",
        "valor": "Valor",
        "parcela": "Parcela",
    })
)
st.dataframe(
    show,
    use_container_width=True,
    hide_index=True,
    height=480,
    column_config={
        "Data": st.column_config.DateColumn(format="DD/MM/YYYY"),
        "Valor": st.column_config.NumberColumn(format="R$ %.2f"),
    },
)
