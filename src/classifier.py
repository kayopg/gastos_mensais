"""Classificação de despesas em três dimensões: Categoria, Subcategoria e Tipo.

Hierarquia de prioridade na resolução (do mais específico ao mais genérico):

  1. **Override por TRANSAÇÃO** — `data/transaction_overrides.json`, keyed por
     `mes_ref|data|estabelecimento|valor|parcela|cartao` (granularidade fina).
  2. **Override por ESTABELECIMENTO** — `data/categories.json`, keyed por nome
     do estabelecimento (para o caso comum: "GIASSI sempre é Alimentação").
  3. **Heurísticas automáticas** — `KEYWORD_RULES` (categoria) e
     `SUBCATEGORY_RULES` (subcategoria).
  4. **Defaults** — categoria=Outros, subcategoria="", tipo derivado de
     `is_parcelado` (Parcelado se True, senão "Variável").

Estrutura de cada arquivo:

    categories.json (estabelecimento → defaults)
    {"BOOKING.COM HOTEL": {"categoria": "Hospedagem", "subcategoria": "Viagens"}}

    transaction_overrides.json (transação → override granular)
    {"2026-05|2026-04-20|MP*CIPOMOTOS|348.77|1 de 10|Sicoob":
        {"categoria": "Outros", "tipo": "Parcelado"}}

Retrocompatibilidade: `categories.json` aceita string (legado) — interpretada
como `{categoria: <string>}`.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from .config import (
    CATEGORIES_FILE,
    DATA_DIR,
    KEYWORD_RULES,
    SUBCATEGORY_RULES,
    TIPO_DEFAULT,
)

ManualEntry = dict[str, str | None]
ManualMap = dict[str, ManualEntry]
TxOverridesMap = dict[str, ManualEntry]

TX_OVERRIDES_FILE = DATA_DIR / "transaction_overrides.json"


# ---------------------------------------------------------------------------
# Persistência por estabelecimento (categories.json)
# ---------------------------------------------------------------------------
def _coerce_entry(value: Any) -> ManualEntry:
    """Aceita string (legado) ou dict; devolve dict normalizado."""
    if isinstance(value, str):
        return {"categoria": value, "subcategoria": None, "tipo": None}
    if isinstance(value, dict):
        return {
            "categoria":    value.get("categoria"),
            "subcategoria": value.get("subcategoria"),
            "tipo":         value.get("tipo"),
        }
    return {"categoria": None, "subcategoria": None, "tipo": None}


def load_manual_map(path: Path = CATEGORIES_FILE) -> ManualMap:
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return {est: _coerce_entry(v) for est, v in raw.items()}


def save_manual_map(mapping: ManualMap, path: Path = CATEGORIES_FILE) -> None:
    """Grava em disco. Limpa chaves None para manter o arquivo enxuto."""
    cleaned: dict[str, dict[str, str]] = {}
    for est, entry in mapping.items():
        e = {k: v for k, v in entry.items() if v}
        if e:
            cleaned[est] = e
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(cleaned, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Persistência por transação (transaction_overrides.json)
# ---------------------------------------------------------------------------
def tx_key(row) -> str:
    """Chave estável para uma transação. Usada como índice no JSON.

    Aceita dict, pd.Series ou objeto com __getitem__. Usa indexação por
    chave (não getattr) para evitar conflito com atributos nativos do
    pd.Series (ex: Series.data é o buffer interno, não o valor da coluna).
    """
    def _g(k, default=""):
        try:
            v = row[k]
        except (KeyError, IndexError, TypeError):
            return default
        return default if v is None else v

    data = _g("data")
    if hasattr(data, "strftime"):
        data_iso = data.strftime("%Y-%m-%d")
    else:
        data_iso = str(data)[:10]

    try:
        valor_str = f"{float(_g('valor', 0)):.2f}"
    except (TypeError, ValueError):
        valor_str = "0.00"

    return "|".join([
        str(_g("mes_ref")),
        data_iso,
        str(_g("estabelecimento")).strip(),
        valor_str,
        str(_g("parcela") or "-"),
        str(_g("cartao")),
    ])


def load_tx_overrides(path: Path = TX_OVERRIDES_FILE) -> TxOverridesMap:
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return {k: _coerce_entry(v) for k, v in raw.items()}


def save_tx_overrides(mapping: TxOverridesMap, path: Path = TX_OVERRIDES_FILE) -> None:
    cleaned: dict[str, dict[str, str]] = {}
    for k, entry in mapping.items():
        e = {kk: vv for kk, vv in entry.items() if vv}
        if e:
            cleaned[k] = e
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(cleaned, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Heurísticas de keyword
# ---------------------------------------------------------------------------
def _match_keyword(estabelecimento: str, rules: dict[str, list[str]]) -> str | None:
    upper = estabelecimento.upper()
    for label, palavras in rules.items():
        if any(p in upper for p in palavras):
            return label
    return None


# ---------------------------------------------------------------------------
# Resolução
# ---------------------------------------------------------------------------
def resolve_no_tx(
    row: pd.Series, manual: ManualMap
) -> tuple[str, str, str]:
    """Resolve sem considerar override de transação.

    Útil para a UI saber qual seria o "auto" se o usuário limpasse o override.
    """
    est = str(row["estabelecimento"]).strip()
    overrides = manual.get(est, {})

    cat = overrides.get("categoria") or _match_keyword(est, KEYWORD_RULES) or "Outros"

    sub = overrides.get("subcategoria")
    if not sub:
        sub = _match_keyword(est, SUBCATEGORY_RULES) or ""

    tipo_o = overrides.get("tipo")
    if tipo_o:
        tipo = tipo_o
    elif bool(row.get("is_parcelado")):
        tipo = "Parcelado"
    else:
        tipo = TIPO_DEFAULT

    return cat, sub, tipo


def _resolve_row(
    row: pd.Series,
    manual: ManualMap,
    tx_overrides: TxOverridesMap,
) -> tuple[str, str, str]:
    cat0, sub0, tipo0 = resolve_no_tx(row, manual)
    tx_o = tx_overrides.get(tx_key(row), {})
    cat = tx_o.get("categoria") or cat0
    sub = tx_o.get("subcategoria") or sub0
    tipo = tx_o.get("tipo") or tipo0
    return cat, sub, tipo


def classify(
    df: pd.DataFrame,
    manual_map: ManualMap | None = None,
    tx_overrides: TxOverridesMap | None = None,
) -> pd.DataFrame:
    """Preenche `categoria`, `subcategoria` e `tipo` em-place."""
    if df.empty:
        out = df.copy()
        for col in ("categoria", "subcategoria", "tipo"):
            if col not in out.columns:
                out[col] = ""
        return out

    manual = manual_map if manual_map is not None else load_manual_map()
    tx_o = tx_overrides if tx_overrides is not None else load_tx_overrides()

    df = df.copy()
    resolved = df.apply(
        lambda r: _resolve_row(r, manual, tx_o),
        axis=1, result_type="expand",
    )
    resolved.columns = ["categoria", "subcategoria", "tipo"]
    df["categoria"] = resolved["categoria"]
    df["subcategoria"] = resolved["subcategoria"]
    df["tipo"] = resolved["tipo"]
    return df
