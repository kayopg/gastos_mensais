"""Despesas manuais — registradas via formulário no app.

Cada entrada é um dicionário com os campos:

    {
      "data": "2026-06-29",                  # YYYY-MM-DD
      "estabelecimento": "Padaria da Esquina",
      "valor": 12.50,
      "forma_pagamento": "PIX",              # FORMAS_PAGAMENTO
      "categoria": "Alimentação",
      "subcategoria": "Rotina",
      "tipo": "Variável",
      "parcela": "-",                        # ou "1 de 3"
      "quem": "Ari",                         # PESSOAS
      "registrado_em": "2026-06-29T15:30:00" # auditoria
    }

Persistência:
  - Em produção (Streamlit Cloud), grava no Google Drive como
    `manual_expenses.json` na pasta raiz das faturas.
  - Em dev local (sem Drive secrets), usa `data/manual_expenses.json`.

Requisito de Drive: a Service Account precisa de permissão **Editor** (não
apenas Leitor) na pasta `Gastos Cartão`. Se faltar permissão, save dá
erro 403 e a UI orienta o usuário a corrigir.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from .config import MANUAL_EXPENSES_FILE, ROOT_DIR
from .drive_loader import (
    drive_download_text,
    drive_find_file,
    drive_upload_or_update_text,
    has_drive_secrets,
)

LOCAL_FALLBACK = ROOT_DIR / "data" / "manual_expenses.json"


# ---------------------------------------------------------------------------
# Persistência
# ---------------------------------------------------------------------------
def load_manual_expenses() -> list[dict]:
    """Lê a lista de despesas manuais. Retorna [] se não existir."""
    if has_drive_secrets():
        file_id = drive_find_file(MANUAL_EXPENSES_FILE)
        if not file_id:
            return []
        try:
            return json.loads(drive_download_text(file_id))
        except (json.JSONDecodeError, ValueError):
            return []
    # Fallback local (dev)
    if not LOCAL_FALLBACK.exists():
        return []
    try:
        return json.loads(LOCAL_FALLBACK.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, ValueError):
        return []


def save_manual_expenses(items: list[dict]) -> None:
    """Grava a lista no Drive (produção) ou local (dev)."""
    payload = json.dumps(items, ensure_ascii=False, indent=2)
    if has_drive_secrets():
        drive_upload_or_update_text(MANUAL_EXPENSES_FILE, payload)
        return
    LOCAL_FALLBACK.parent.mkdir(parents=True, exist_ok=True)
    LOCAL_FALLBACK.write_text(payload, encoding="utf-8")


def append_manual_expense(entry: dict) -> None:
    """Adiciona uma despesa preservando as existentes."""
    items = load_manual_expenses()
    if "registrado_em" not in entry:
        entry["registrado_em"] = datetime.now().isoformat(timespec="seconds")
    items.append(entry)
    save_manual_expenses(items)


def delete_manual_expense(index: int) -> None:
    """Remove a despesa de índice `index` (na ordem de inserção)."""
    items = load_manual_expenses()
    if 0 <= index < len(items):
        del items[index]
        save_manual_expenses(items)


# ---------------------------------------------------------------------------
# Conversão para o schema padrão (compatível com parse_many)
# ---------------------------------------------------------------------------
def _empty_schema_frame() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "data", "estabelecimento", "portador", "cartao", "valor", "parcela",
            "is_parcelado", "categoria", "subcategoria", "tipo",
            "mes_ref", "fonte",
        ]
    )


def manual_to_df() -> pd.DataFrame:
    """Converte as despesas manuais em DataFrame com o mesmo schema das faturas.

    Mapeamentos:
      - `forma_pagamento` → coluna `cartao` (ex: 'PIX', 'Dinheiro', 'Crédito XP')
      - `quem` → coluna `portador`
      - `parcela` ≠ '-' → `is_parcelado=True`
      - `fonte` = "Manual"
      - `mes_ref` derivado da `data` da compra

    Defensivo a campos ausentes ou tipos inesperados.
    """
    items = load_manual_expenses()
    if not items:
        return _empty_schema_frame()

    # Garante que todos os items são dicts (filtra lixo)
    items = [it for it in items if isinstance(it, dict)]
    if not items:
        return _empty_schema_frame()

    # Pre-normaliza cada item antes de criar o DataFrame
    rows = []
    for it in items:
        try:
            v = float(it.get("valor", 0) or 0)
        except (TypeError, ValueError):
            v = 0.0
        parcela = str(it.get("parcela") or "-").strip() or "-"
        is_parc = parcela != "-" and "de" in parcela.lower()
        rows.append({
            "data":            it.get("data", ""),
            "estabelecimento": str(it.get("estabelecimento") or "").strip(),
            "portador":        str(it.get("quem") or ""),
            "cartao":          str(it.get("forma_pagamento") or "Manual"),
            "valor":           v,
            "parcela":         parcela,
            "is_parcelado":    is_parc,
            "categoria":       str(it.get("categoria") or "Outros"),
            "subcategoria":    str(it.get("subcategoria") or ""),
            "tipo":            str(it.get("tipo") or "Variável"),
            "fonte":           "Manual",
        })

    df = pd.DataFrame(rows)
    df["data"] = pd.to_datetime(df["data"], errors="coerce")
    df = df.dropna(subset=["data"]).copy()
    if df.empty:
        return _empty_schema_frame()
    df["mes_ref"] = df["data"].dt.strftime("%Y-%m")

    return df[
        [
            "data", "estabelecimento", "portador", "cartao", "valor", "parcela",
            "is_parcelado", "categoria", "subcategoria", "tipo",
            "mes_ref", "fonte",
        ]
    ].reset_index(drop=True)
