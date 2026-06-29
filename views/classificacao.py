"""Classificação manual POR DESPESA (lançamento individual).

Cada linha = uma transação. Edita Categoria / Subcategoria / Tipo e salva.
A persistência é feita em duas camadas:

  1. **`data/transaction_overrides.json`** — override granular por transação.
     Persistido APENAS quando o valor difere do que seria auto-resolvido pelo
     estabelecimento ou pelas regras automáticas (mantém o JSON enxuto).

  2. **`data/categories.json`** — defaults por estabelecimento (continua
     valendo como fallback para todas as transações daquele estabelecimento).
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from src.classifier import (
    classify,
    load_manual_map,
    load_tx_overrides,
    resolve_no_tx,
    save_tx_overrides,
    tx_key,
)
from src.config import CATEGORIES, SUBCATEGORIES, TIPOS
from src.drive_loader import current_source, fetch_invoices, filter_by_extension
from src.parsers import parse_many
from src.theme import render_header

render_header(
    "🏷️ Classificação manual",
    f"Fonte: <strong>{current_source()}</strong>",
)


@st.cache_data(ttl=300, show_spinner="Carregando faturas...")
def _load_raw() -> pd.DataFrame:
    files = filter_by_extension(fetch_invoices())
    df = parse_many(files)
    if df.empty:
        return df
    # Defensiva — garante datetime64 mesmo se algum parser deixou como object
    df["data"] = pd.to_datetime(df["data"], errors="coerce")
    return df.dropna(subset=["data"])


df = _load_raw()
if df.empty:
    st.warning("Nenhuma fatura encontrada. Adicione um arquivo em `data/raw/` ou no Drive.")
    st.stop()

manual = load_manual_map()
tx_o = load_tx_overrides()
df_class = classify(df, manual, tx_o)

# ---------------------------------------------------------------------------
# Filtros
# ---------------------------------------------------------------------------
st.markdown(
    "Cada linha é uma despesa. Edite **Categoria**, **Subcategoria** e **Tipo** "
    "diretamente e clique em **Salvar** ao final."
)

col_f1, col_f2, col_f3 = st.columns([2, 1, 1])
with col_f1:
    busca = st.text_input("🔎 Buscar estabelecimento", "")
with col_f2:
    meses_disp = sorted(df_class["mes_ref"].dropna().unique(), reverse=True)
    mes_sel = st.selectbox("Mês de Referência", ["Todos"] + meses_disp, index=0)
with col_f3:
    cartoes_disp = sorted(df_class["cartao"].dropna().unique().tolist())
    cartao_sel = st.selectbox("Cartão", ["Todos"] + cartoes_disp, index=0)

col_g1, col_g2 = st.columns([1, 1])
with col_g1:
    apenas_outros = st.checkbox("Só Categoria=Outros", value=False)
with col_g2:
    sem_sub = st.checkbox("Só sem Subcategoria", value=False)

view = df_class.copy()
if busca:
    view = view[view["estabelecimento"].str.contains(busca, case=False, na=False)]
if mes_sel != "Todos":
    view = view[view["mes_ref"] == mes_sel]
if cartao_sel != "Todos":
    view = view[view["cartao"] == cartao_sel]
if apenas_outros:
    view = view[view["categoria"] == "Outros"]
if sem_sub:
    view = view[view["subcategoria"].fillna("") == ""]

view = view.sort_values(["mes_ref", "data", "estabelecimento"], ascending=[False, False, True])
view = view.reset_index(drop=True)

# ---------------------------------------------------------------------------
# Editor — uma linha por despesa
# ---------------------------------------------------------------------------
display = view[[
    "mes_ref", "data", "cartao", "estabelecimento",
    "valor", "parcela",
    "categoria", "subcategoria", "tipo",
]].rename(columns={
    "mes_ref": "Mês Ref",
    "data": "Data",
    "cartao": "Cartão",
    "estabelecimento": "Estabelecimento",
    "valor": "Valor",
    "parcela": "Parcela",
    "categoria": "Categoria",
    "subcategoria": "Subcategoria",
    "tipo": "Tipo",
})

edited = st.data_editor(
    display,
    column_config={
        "Mês Ref":         st.column_config.TextColumn(disabled=True, width="small"),
        "Data":            st.column_config.DateColumn(disabled=True, format="DD/MM/YYYY", width="small"),
        "Cartão":          st.column_config.TextColumn(disabled=True, width="small"),
        "Estabelecimento": st.column_config.TextColumn(disabled=True, width="medium"),
        "Valor":           st.column_config.NumberColumn(disabled=True, format="R$ %.2f", width="small"),
        "Parcela":         st.column_config.TextColumn(disabled=True, width="small"),
        "Categoria":       st.column_config.SelectboxColumn(options=CATEGORIES, required=True),
        "Subcategoria":    st.column_config.SelectboxColumn(options=SUBCATEGORIES, required=False),
        "Tipo":            st.column_config.SelectboxColumn(options=TIPOS, required=True),
    },
    hide_index=True,
    use_container_width=True,
    height=560,
    num_rows="fixed",
    key="editor_despesas",
)

# ---------------------------------------------------------------------------
# Ações
# ---------------------------------------------------------------------------
col_a, col_b = st.columns([1, 3])

with col_a:
    salvar = st.button("💾 Salvar alterações", type="primary", use_container_width=True)

with col_b:
    n_total = len(df_class)
    n_view = len(view)
    n_outros = (df_class["categoria"] == "Outros").sum()
    n_sem_sub = (df_class["subcategoria"].fillna("") == "").sum()
    n_overrides = len(tx_o)
    st.info(
        f"📊 {n_total} despesas no total · {n_view} na visão atual · "
        f"{n_outros} em **Outros** · {n_sem_sub} sem subcategoria · "
        f"{n_overrides} overrides salvos por transação"
    )

if salvar:
    # Para cada linha visível: comparar valores editados com o que seria
    # resolvido SEM tx-override. Se diferentes, persistir; se iguais, limpar.
    novo_tx_o = dict(tx_o)
    n_added, n_removed = 0, 0
    for i, raw_row in view.iterrows():
        # raw_row é a linha ORIGINAL (com cartao, parcela, etc, antes do rename)
        edited_row = edited.iloc[i]
        user_cat = edited_row["Categoria"]
        user_sub = edited_row["Subcategoria"] or ""
        user_tipo = edited_row["Tipo"]

        # Auto-resolução SEM override de transação (estabelecimento + keyword + default)
        auto_cat, auto_sub, auto_tipo = resolve_no_tx(raw_row, manual)

        key = tx_key(raw_row)
        if (user_cat, user_sub, user_tipo) == (auto_cat, auto_sub, auto_tipo):
            # Nada a sobrescrever — remove override anterior se existir
            if key in novo_tx_o:
                novo_tx_o.pop(key)
                n_removed += 1
        else:
            entry: dict[str, str | None] = {}
            if user_cat != auto_cat:
                entry["categoria"] = user_cat
            else:
                entry["categoria"] = None
            if user_sub != auto_sub:
                entry["subcategoria"] = user_sub or None
            else:
                entry["subcategoria"] = None
            if user_tipo != auto_tipo:
                entry["tipo"] = user_tipo
            else:
                entry["tipo"] = None
            # remove None (save_tx_overrides já filtra mas mantém limpo aqui)
            entry = {k: v for k, v in entry.items() if v}
            if entry:
                if novo_tx_o.get(key) != entry:
                    novo_tx_o[key] = entry
                    n_added += 1

    save_tx_overrides(novo_tx_o)
    st.cache_data.clear()
    st.success(
        f"Salvo: {n_added} novo(s) override(s), {n_removed} removido(s). "
        f"Total agora: {len(novo_tx_o)} overrides por transação."
    )
    st.rerun()
