"""Classificação de despesas em três dimensões: Categoria, Subcategoria e Tipo.

Estrutura do `data/categories.json` (manual_map):

    {
      "ESTABELECIMENTO X": {
        "categoria":    "Hospedagem",
        "subcategoria": "Viagens",
        "tipo":         "Fixo"          # opcional; null = derivar
      },
      ...
    }

Retrocompatibilidade: se uma entrada vier como string (formato antigo), é
interpretada como `{categoria: <string>}`.

Prioridade na resolução:
  1. **Override manual** — `manual_map[estabelecimento]` (cada campo independente).
  2. **Regras automáticas** — `KEYWORD_RULES` (categoria) e `SUBCATEGORY_RULES`.
  3. **Defaults** — categoria=Outros, subcategoria="" (vazia), tipo derivado de `is_parcelado`.

Tipo:
  - Override manual SEM parcelado → respeita.
  - Sem override e `is_parcelado=True` → "Parcelado".
  - Sem override e sem parcela → "Variável".
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from .config import (
    CATEGORIES_FILE,
    KEYWORD_RULES,
    SUBCATEGORY_RULES,
    TIPO_DEFAULT,
)

ManualEntry = dict[str, str | None]
ManualMap = dict[str, ManualEntry]


# ---------------------------------------------------------------------------
# Persistência
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
# Heurísticas de keyword
# ---------------------------------------------------------------------------
def _match_keyword(estabelecimento: str, rules: dict[str, list[str]]) -> str | None:
    upper = estabelecimento.upper()
    for label, palavras in rules.items():
        if any(p in upper for p in palavras):
            return label
    return None


# ---------------------------------------------------------------------------
# Aplicação row-a-row
# ---------------------------------------------------------------------------
def _resolve_row(row: pd.Series, manual: ManualMap) -> tuple[str, str, str]:
    est = str(row["estabelecimento"]).strip()
    overrides = manual.get(est, {})

    # Categoria
    cat = overrides.get("categoria") or _match_keyword(est, KEYWORD_RULES) or "Outros"

    # Subcategoria
    sub = overrides.get("subcategoria")
    if not sub:
        sub = _match_keyword(est, SUBCATEGORY_RULES) or ""

    # Tipo
    tipo_override = overrides.get("tipo")
    if tipo_override:
        tipo = tipo_override
    elif bool(row.get("is_parcelado")):
        tipo = "Parcelado"
    else:
        tipo = TIPO_DEFAULT

    return cat, sub, tipo


def classify(df: pd.DataFrame, manual_map: ManualMap | None = None) -> pd.DataFrame:
    """Preenche `categoria`, `subcategoria` e `tipo` em-place."""
    if df.empty:
        out = df.copy()
        for col in ("categoria", "subcategoria", "tipo"):
            if col not in out.columns:
                out[col] = ""
        return out

    manual = manual_map if manual_map is not None else load_manual_map()
    df = df.copy()
    resolved = df.apply(lambda r: _resolve_row(r, manual), axis=1, result_type="expand")
    resolved.columns = ["categoria", "subcategoria", "tipo"]
    df["categoria"] = resolved["categoria"]
    df["subcategoria"] = resolved["subcategoria"]
    df["tipo"] = resolved["tipo"]
    return df
