"""Página de Classificação manual (Categoria + Subcategoria + Tipo)."""
from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from src.classifier import classify, load_manual_map, save_manual_map
from src.config import CATEGORIES, CATEGORIES_FILE, SUBCATEGORIES, TIPOS
from src.drive_loader import current_source, fetch_invoices, filter_by_extension
from src.parsers import parse_many
from src.theme import render_header

render_header(
    "🏷️ Classificação manual",
    f"Fonte: <strong>{current_source()}</strong> · Override gravado em <code>data/categories.json</code>",
)


@st.cache_data(ttl=300, show_spinner="Carregando faturas...")
def _load_raw() -> pd.DataFrame:
    files = filter_by_extension(fetch_invoices())
    return parse_many(files)


df = _load_raw()
if df.empty:
    st.warning("Nenhuma fatura encontrada. Adicione um arquivo em `data/raw/` ou no Drive.")
    st.stop()

manual = load_manual_map()
df_class = classify(df, manual)

# ---------------------------------------------------------------------------
# Tabela agregada por estabelecimento
# ---------------------------------------------------------------------------
agg = (
    df_class.groupby("estabelecimento", as_index=False)
    .agg(
        Lançamentos=("valor", "size"),
        Total=("valor", "sum"),
        Cartões=("cartao", lambda s: ", ".join(sorted(s.unique()))),
        Categoria_atual=("categoria", lambda s: s.mode().iat[0] if not s.empty else "Outros"),
        Subcat_atual=("subcategoria", lambda s: s.mode().iat[0] if not s.empty else ""),
        Tipo_atual=("tipo", lambda s: s.mode().iat[0] if not s.empty else "Variável"),
    )
    .sort_values("Total", ascending=False)
)


def _override(estab: str, field: str, fallback) -> str:
    return manual.get(estab, {}).get(field) or fallback


agg["Categoria"] = [
    _override(e, "categoria", c) for e, c in zip(agg["estabelecimento"], agg["Categoria_atual"])
]
agg["Subcategoria"] = [
    _override(e, "subcategoria", s) for e, s in zip(agg["estabelecimento"], agg["Subcat_atual"])
]
agg["Tipo"] = [
    _override(e, "tipo", t) for e, t in zip(agg["estabelecimento"], agg["Tipo_atual"])
]
agg = agg.rename(columns={"estabelecimento": "Estabelecimento"})

# ---------------------------------------------------------------------------
# Filtros
# ---------------------------------------------------------------------------
st.markdown(
    "Edite **Categoria**, **Subcategoria** e **Tipo** linha a linha. "
    "As colunas *_atual* mostram o que a heurística automática (palavras-chave) sugere — "
    "ao salvar, a coluna editada vira a fonte da verdade no `categories.json`."
)

col_f1, col_f2, col_f3 = st.columns([2, 1, 1])
with col_f1:
    busca = st.text_input("🔎 Buscar estabelecimento", "")
with col_f2:
    apenas_outros = st.checkbox("Só Categoria=Outros", value=False)
with col_f3:
    sem_sub = st.checkbox("Só sem Subcategoria", value=False)

view = agg.copy()
if busca:
    view = view[view["Estabelecimento"].str.contains(busca, case=False, na=False)]
if apenas_outros:
    view = view[view["Categoria"] == "Outros"]
if sem_sub:
    view = view[view["Subcategoria"].fillna("") == ""]

# ---------------------------------------------------------------------------
# Editor
# ---------------------------------------------------------------------------
edited = st.data_editor(
    view[["Estabelecimento", "Categoria", "Subcategoria", "Tipo",
          "Lançamentos", "Total", "Cartões"]],
    column_config={
        "Categoria": st.column_config.SelectboxColumn(
            options=CATEGORIES, required=True,
        ),
        "Subcategoria": st.column_config.SelectboxColumn(
            options=SUBCATEGORIES, required=False,
            help="Vazio = sem subcategoria",
        ),
        "Tipo": st.column_config.SelectboxColumn(
            options=TIPOS, required=True,
            help="Default: Parcelado se houver parcela, senão Variável. Marque Fixo p/ assinaturas.",
        ),
        "Cartões": st.column_config.TextColumn(disabled=True),
        "Lançamentos": st.column_config.NumberColumn(disabled=True, format="%d"),
        "Total": st.column_config.NumberColumn(disabled=True, format="R$ %.2f"),
    },
    hide_index=True,
    use_container_width=True,
    num_rows="fixed",
    key="editor_classificacao",
)

# ---------------------------------------------------------------------------
# Ações
# ---------------------------------------------------------------------------
col_a, col_b, col_c = st.columns([1, 1, 2])

with col_a:
    if st.button("💾 Salvar", type="primary", use_container_width=True):
        novo = dict(manual)
        for _, row in edited.iterrows():
            entry: dict = {}
            if row["Categoria"]:
                entry["categoria"] = row["Categoria"]
            if row["Subcategoria"]:
                entry["subcategoria"] = row["Subcategoria"]
            if row["Tipo"] and row["Tipo"] != "Variável":
                entry["tipo"] = row["Tipo"]
            novo[row["Estabelecimento"]] = entry
        save_manual_map(novo)
        st.cache_data.clear()
        st.success(f"Salvo em `{CATEGORIES_FILE.relative_to(CATEGORIES_FILE.parents[1])}`.")
        st.rerun()

with col_b:
    payload = json.dumps(
        {k: {kk: vv for kk, vv in v.items() if vv} for k, v in manual.items()},
        ensure_ascii=False, indent=2, sort_keys=True,
    )
    st.download_button(
        "⬇️ Baixar JSON",
        data=payload,
        file_name="categories.json",
        mime="application/json",
        use_container_width=True,
    )

with col_c:
    pendentes = (agg["Categoria"] == "Outros").sum()
    sem_sub_n = (agg["Subcategoria"].fillna("") == "").sum()
    st.info(
        f"📊 {len(agg)} estabelecimentos · {pendentes} em **Outros** · "
        f"{sem_sub_n} sem subcategoria"
    )
