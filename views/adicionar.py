"""Página para adicionar despesas manuais (não vindas das faturas)."""
from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from src.config import (
    CATEGORIES,
    FORMAS_PAGAMENTO,
    PESSOAS,
    SUBCATEGORIES,
    TIPOS,
)
from src.manual_expenses import (
    append_manual_expense,
    delete_manual_expense,
    load_manual_expenses,
)
from src.theme import render_header

render_header(
    "➕ Adicionar despesa",
    "Registre gastos que <strong>não vêm pela fatura</strong> do cartão "
    "(PIX, dinheiro, débito).",
)


def _fmt_brl(v: float) -> str:
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


# ---------------------------------------------------------------------------
# Formulário
# ---------------------------------------------------------------------------
with st.form("nova_despesa", clear_on_submit=True):
    c1, c2 = st.columns(2)

    with c1:
        data_compra = st.date_input("Data da compra", value=date.today())
        estabelecimento = st.text_input(
            "Estabelecimento *",
            placeholder="Ex: Padaria do Bairro",
        )
        valor = st.number_input(
            "Valor (R$) *", min_value=0.01, step=1.0, format="%.2f"
        )
        forma_pagamento = st.selectbox("Forma de pagamento *", FORMAS_PAGAMENTO)

    with c2:
        quem = st.selectbox("Quem pagou", PESSOAS)
        categoria = st.selectbox("Categoria *", CATEGORIES)
        subs_validas = [s for s in SUBCATEGORIES if s]  # remove vazia
        subcategoria = st.selectbox(
            "Subcategoria", [""] + subs_validas, index=0,
            help="Opcional",
        )
        tipo = st.selectbox(
            "Tipo *", TIPOS, index=TIPOS.index("Variável"),
        )

    parcela = st.text_input(
        "Parcela (opcional)",
        placeholder="Ex: 1 de 3 (deixe em branco se não for parcelado)",
    )

    # Aviso quando for cartão de crédito (potencial duplicata com fatura)
    if forma_pagamento.startswith("Crédito"):
        st.warning(
            "⚠️ **Atenção a duplicatas.** Compras em cartão de crédito normalmente "
            "vêm pela fatura mensal. Se você adicionar manualmente AGORA e a "
            f"mesma compra aparecer na fatura {forma_pagamento.split()[-1]} "
            "depois, vai contar duas vezes. Use só se tiver certeza de que "
            "esse lançamento NÃO virá na próxima fatura."
        )

    submit = st.form_submit_button("➕ Adicionar despesa", type="primary", use_container_width=True)

    if submit:
        if not estabelecimento.strip() or valor <= 0:
            st.error("Preenche pelo menos **Estabelecimento** e **Valor**.")
        else:
            entry = {
                "data": data_compra.isoformat(),
                "estabelecimento": estabelecimento.strip(),
                "valor": float(valor),
                "forma_pagamento": forma_pagamento,
                "categoria": categoria,
                "subcategoria": subcategoria,
                "tipo": tipo,
                "parcela": parcela.strip() or "-",
                "quem": quem,
            }
            try:
                append_manual_expense(entry)
                st.cache_data.clear()
                st.success(
                    f"✅ Adicionada: **{estabelecimento}** · {_fmt_brl(valor)} · "
                    f"{forma_pagamento}"
                )
                st.rerun()
            except Exception as e:  # noqa: BLE001
                from src.drive_loader import DriveFileMissing
                if isinstance(e, DriveFileMissing):
                    st.error(
                        "❌ **Setup necessário (uma vez só).** "
                        "Service Accounts não conseguem criar arquivos novos em "
                        "My Drive pessoal — só atualizar os existentes. Por isso "
                        "você precisa criar o arquivo `manual_expenses.json` uma "
                        "única vez, manualmente."
                    )
                    st.markdown(
                        "**Jeito mais fácil — pelo PowerShell:**\n"
                        "1. Crie um arquivo local vazio:\n"
                        "   ```powershell\n"
                        "   '[]' | Out-File -FilePath manual_expenses.json -Encoding utf8\n"
                        "   ```\n"
                        "2. Abra a pasta `Gastos Cartão` no Google Drive (web ou app)\n"
                        "3. Arraste o arquivo `manual_expenses.json` pra dentro da pasta (faz o upload)\n"
                        "4. Volte aqui e clique em **Adicionar despesa** de novo\n\n"
                        "**Alternativa pela interface web:**\n"
                        "Drive → pasta `Gastos Cartão` → **+ Novo → Upload de arquivo** → "
                        "selecione qualquer .json com conteúdo `[]` e nome `manual_expenses.json`"
                    )
                else:
                    msg = str(e)
                    if "403" in msg or "Forbidden" in msg or "insufficient" in msg.lower():
                        st.error(
                            "❌ A Service Account não tem permissão para **gravar** no Drive. "
                            "Vá na pasta `Gastos Cartão` do Google Drive, abra **Compartilhar**, "
                            "encontre o e-mail da SA e mude de **Leitor** para **Editor**. "
                            "Depois tente salvar novamente."
                        )
                    else:
                        st.error(f"Falha ao salvar: {e}")

# ---------------------------------------------------------------------------
# Últimas despesas registradas
# ---------------------------------------------------------------------------
st.markdown("---")
st.markdown("### 📋 Últimas despesas manuais")

items = load_manual_expenses()
if not items:
    st.info("Nenhuma despesa manual registrada ainda. Use o formulário acima.")
else:
    # Ordena por registrado_em (mais recentes primeiro), fallback para data
    items_with_idx = list(enumerate(items))
    items_with_idx.sort(
        key=lambda x: (x[1].get("registrado_em") or x[1].get("data") or ""),
        reverse=True,
    )
    df = pd.DataFrame([
        {
            "Data":            it.get("data", ""),
            "Estabelecimento": it.get("estabelecimento", ""),
            "Valor":           it.get("valor", 0),
            "Forma":           it.get("forma_pagamento", ""),
            "Quem":            it.get("quem", ""),
            "Categoria":       it.get("categoria", ""),
            "Subcategoria":    it.get("subcategoria", ""),
            "Tipo":            it.get("tipo", ""),
            "Parcela":         it.get("parcela", "-"),
        }
        for _, it in items_with_idx
    ])

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Data":  st.column_config.DateColumn(format="DD/MM/YYYY"),
            "Valor": st.column_config.NumberColumn(format="R$ %.2f"),
        },
        height=360,
    )

    # Exclusão de uma despesa específica
    with st.expander("🗑️ Remover uma despesa"):
        labels = [
            f"{it.get('data','')} · {it.get('estabelecimento','')} · "
            f"{_fmt_brl(float(it.get('valor', 0)))} · {it.get('forma_pagamento','')}"
            for _, it in items_with_idx
        ]
        indices = [i for i, _ in items_with_idx]
        if labels:
            escolha = st.selectbox("Escolha a despesa para remover", labels)
            if st.button("Remover esta despesa", type="secondary"):
                idx_remover = indices[labels.index(escolha)]
                delete_manual_expense(idx_remover)
                st.cache_data.clear()
                st.success("Despesa removida.")
                st.rerun()

    total_manual = sum(float(it.get("valor", 0)) for it in items)
    st.caption(
        f"📊 **{len(items)}** despesas manuais registradas · "
        f"Total acumulado: **{_fmt_brl(total_manual)}**"
    )
