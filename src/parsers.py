"""Parsers das faturas em CSV / XLSX / OFX → DataFrame normalizado.

Schema de saída (ver `src/config.COLUMNS`):
    data | estabelecimento | portador | valor | parcela
    is_parcelado | categoria | mes_ref | fonte

Convenção de sinal: `valor > 0` = compra/débito; `valor < 0` = pagamento/crédito.
"""
from __future__ import annotations

import io
import re
from pathlib import Path
from typing import Iterable

import pandas as pd

# ---------------------------------------------------------------------------
# Helpers comuns
# ---------------------------------------------------------------------------
_VALOR_RE = re.compile(r"(-?\s*[\d\.\,]+)")


def _parse_valor_brl(s) -> float:
    """Converte valores em PT-BR para float.

    Aceita: 'R$ 1.800,00', '-6.786,87', '193,00', '193.00', 1800 (já numérico).
    """
    if s is None or (isinstance(s, float) and pd.isna(s)):
        return 0.0
    if isinstance(s, (int, float)):
        return float(s)
    txt = str(s).strip()
    if not txt or txt.lower() in {"nan", "none", "-"}:
        return 0.0
    # remove "R$" e espaços
    txt = txt.replace("R$", "").replace("r$", "").strip()
    # parênteses indicam valor negativo (alguns relatórios contábeis)
    neg = txt.startswith("(") and txt.endswith(")")
    if neg:
        txt = txt[1:-1]
    m = _VALOR_RE.search(txt)
    if not m:
        return 0.0
    raw = m.group(1).replace(" ", "")
    # se tem vírgula → formato BR (ponto = milhar, vírgula = decimal)
    if "," in raw:
        raw = raw.replace(".", "").replace(",", ".")
    val = float(raw)
    return -val if neg else val


def _parse_parcela(s) -> tuple[bool, str]:
    """'-' / NaN / '' → (False, '-') ; '1 de 6' / '1/6' → (True, '1 de 6')"""
    if s is None or (isinstance(s, float) and pd.isna(s)):
        return False, "-"
    txt = str(s).strip()
    if txt in ("", "-"):
        return False, "-"
    # normaliza '1/6' para '1 de 6'
    if "/" in txt and "de" not in txt:
        try:
            a, b = txt.split("/", 1)
            if a.strip().isdigit() and b.strip().isdigit():
                txt = f"{a.strip()} de {b.strip()}"
        except ValueError:
            pass
    if "de" in txt:
        head = txt.split("de")[0].strip()
        if head.isdigit():
            return True, txt
    return False, txt


def _empty_frame() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "data", "estabelecimento", "portador", "cartao", "valor", "parcela",
            "is_parcelado", "categoria", "subcategoria", "tipo",
            "mes_ref", "fonte",
        ]
    )


# ---------------------------------------------------------------------------
# Mês de referência da FATURA (vindo do nome do arquivo, não da data da compra)
# ---------------------------------------------------------------------------
# O cartão fecha em um dia X — compras feitas nos meses anteriores aparecem
# na fatura do mês corrente. Para agrupar corretamente os gastos por "fatura",
# extraímos o YYYY-MM do nome do arquivo (ex: 'Fatura2026-01-10.csv' → '2026-01').
_INVOICE_DATE_RE = re.compile(r"(\d{4})[-_]?(\d{2})[-_]?(\d{2})?")


def _invoice_month_from_filename(name: str) -> str | None:
    """Extrai 'YYYY-MM' do nome do arquivo. Retorna None se não encontrar."""
    if not name:
        return None
    m = _INVOICE_DATE_RE.search(Path(name).stem)
    if not m:
        return None
    year = int(m.group(1))
    month = int(m.group(2))
    if not (1 <= month <= 12) or not (2000 <= year <= 2100):
        return None
    return f"{year:04d}-{month:02d}"


def _finalize(df: pd.DataFrame, source: str, cartao: str | None = None) -> pd.DataFrame:
    """Aplica o schema final: tipos, ordenação de colunas, drops."""
    from .config import DEFAULT_CARTAO

    if df.empty:
        return _empty_frame()
    df["data"] = pd.to_datetime(df["data"], errors="coerce")
    df = df.dropna(subset=["data"]).copy()
    df["estabelecimento"] = df["estabelecimento"].fillna("").astype(str).str.strip()
    df["portador"] = df.get("portador", "").fillna("").astype(str).str.strip()
    df["cartao"] = cartao or DEFAULT_CARTAO
    df["valor"] = df["valor"].astype(float)
    df["parcela"] = df.get("parcela", "-").fillna("-").astype(str)
    df["is_parcelado"] = df.get("is_parcelado", False).astype(bool)
    # placeholders — `classify()` preenche em seguida
    df["categoria"] = ""
    df["subcategoria"] = ""
    df["tipo"] = ""

    # mes_ref vem PRIMEIRO do nome do arquivo (mês da fatura);
    # fallback = mês da data da compra (caso o arquivo não siga o padrão)
    invoice_month = _invoice_month_from_filename(source)
    if invoice_month:
        df["mes_ref"] = invoice_month
    else:
        df["mes_ref"] = df["data"].dt.strftime("%Y-%m")

    df["fonte"] = source
    return df[
        [
            "data", "estabelecimento", "portador", "cartao", "valor", "parcela",
            "is_parcelado", "categoria", "subcategoria", "tipo",
            "mes_ref", "fonte",
        ]
    ].reset_index(drop=True)


# ---------------------------------------------------------------------------
# CSV (formato Sicredi/Betha visto no exemplo)
# Colunas: Data;Estabelecimento;Portador;Valor;Parcela
# ---------------------------------------------------------------------------
def parse_csv(content: bytes, source: str, cartao: str | None = None) -> pd.DataFrame:
    # tentativa robusta de encoding
    for enc in ("utf-8", "latin-1", "cp1252"):
        try:
            df = pd.read_csv(io.BytesIO(content), sep=";", dtype=str, encoding=enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise UnicodeDecodeError("utf-8/latin-1/cp1252 falharam para o CSV.")

    df.columns = [c.strip().lower() for c in df.columns]

    df["data"] = pd.to_datetime(df["data"], format="%d/%m/%Y", errors="coerce")
    df["valor"] = df["valor"].map(_parse_valor_brl)
    parc = df["parcela"].map(_parse_parcela) if "parcela" in df.columns else pd.Series([(False, "-")] * len(df))
    df["is_parcelado"] = parc.map(lambda t: t[0])
    df["parcela"] = parc.map(lambda t: t[1])

    if "portador" not in df.columns:
        df["portador"] = ""
    return _finalize(df, source, cartao=cartao)


# ---------------------------------------------------------------------------
# XLSX (genérico — detecta as colunas pelo nome)
# ---------------------------------------------------------------------------
_COL_ALIASES = {
    "data":            ["data", "data compra", "data da compra", "date", "dt", "data lanc", "data lançamento"],
    "estabelecimento": ["estabelecimento", "histórico", "historico", "descrição", "descricao",
                         "memo", "lançamento", "lancamento", "merchant", "payee"],
    "portador":        ["portador", "titular", "cartão", "cartao", "responsável", "responsavel"],
    "valor":           ["valor", "valor (r$)", "valor (brl)", "amount", "total", "vlr"],
    "parcela":         ["parcela", "parcelas", "parcelamento"],
}


def _find_header_row(raw: pd.DataFrame) -> int | None:
    """Localiza a linha com cabeçalhos (procura 'data' + 'valor' nas primeiras 10 linhas)."""
    needles = {"data", "valor"}
    for i in range(min(10, len(raw))):
        cells = {str(c).strip().lower() for c in raw.iloc[i].tolist()}
        if needles.issubset(cells) or any("data" in c for c in cells) and any("valor" in c for c in cells):
            return i
    return None


def _resolve_columns(cols: list[str]) -> dict[str, str | None]:
    out: dict[str, str | None] = {}
    lower = {c.strip().lower(): c for c in cols}
    for canonical, aliases in _COL_ALIASES.items():
        out[canonical] = None
        for alias in aliases:
            if alias in lower:
                out[canonical] = lower[alias]
                break
        if out[canonical] is None:
            # fuzzy: contém alguma alias como substring
            for k, original in lower.items():
                if any(alias in k for alias in aliases):
                    out[canonical] = original
                    break
    return out


def parse_xlsx(content: bytes, source: str, cartao: str | None = None) -> pd.DataFrame:
    raw = pd.read_excel(io.BytesIO(content), header=None, dtype=object, engine="openpyxl")
    header_row = _find_header_row(raw)
    if header_row is None:
        # tenta com header=0 mesmo
        df = pd.read_excel(io.BytesIO(content), dtype=object, engine="openpyxl")
    else:
        df = pd.read_excel(
            io.BytesIO(content), header=header_row, dtype=object, engine="openpyxl"
        )

    df.columns = [str(c) for c in df.columns]
    cols = _resolve_columns(df.columns.tolist())

    if not cols.get("data") or not cols.get("valor"):
        raise ValueError(
            f"XLSX sem colunas de Data/Valor reconhecíveis. Encontradas: {list(df.columns)}"
        )

    out = pd.DataFrame()
    out["data"] = pd.to_datetime(df[cols["data"]], dayfirst=True, errors="coerce")
    out["valor"] = df[cols["valor"]].map(_parse_valor_brl)

    out["estabelecimento"] = (
        df[cols["estabelecimento"]] if cols["estabelecimento"] else ""
    )
    out["portador"] = df[cols["portador"]] if cols["portador"] else ""

    if cols["parcela"]:
        parc = df[cols["parcela"]].map(_parse_parcela)
        out["is_parcelado"] = parc.map(lambda t: t[0])
        out["parcela"] = parc.map(lambda t: t[1])
    else:
        out["is_parcelado"] = False
        out["parcela"] = "-"

    return _finalize(out, source, cartao=cartao)


# ---------------------------------------------------------------------------
# OFX
# ---------------------------------------------------------------------------
def parse_ofx(content: bytes, source: str, cartao: str | None = None) -> pd.DataFrame:
    from ofxparse import OfxParser  # import local para keep startup leve

    ofx = OfxParser.parse(io.BytesIO(content))
    rows: list[dict] = []
    for account in ofx.accounts:
        # Em statements de cartão, débitos vêm negativos. Para manter a
        # convenção do projeto (compras > 0), invertemos o sinal.
        is_credit_card = getattr(account, "account_type", "").upper() in {"CREDITLINE", "CREDITCARD"} \
            or (getattr(account, "type", "") or "").lower() == "creditline"
        for tx in account.statement.transactions:
            est = (tx.payee or tx.memo or "").strip()
            valor = float(tx.amount)
            if is_credit_card:
                valor = -valor
            rows.append({
                "data": tx.date,
                "estabelecimento": est,
                "portador": "",
                "valor": valor,
                "parcela": "-",
                "is_parcelado": False,
            })
    return _finalize(pd.DataFrame(rows), source, cartao=cartao)


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------
_SUPPORTED = {".csv", ".xlsx", ".xls", ".ofx"}


def parse_file(name: str, content: bytes, cartao: str | None = None) -> pd.DataFrame:
    ext = Path(name).suffix.lower()
    if ext == ".csv":
        return parse_csv(content, source=name, cartao=cartao)
    if ext in (".xlsx", ".xls"):
        return parse_xlsx(content, source=name, cartao=cartao)
    if ext == ".ofx":
        return parse_ofx(content, source=name, cartao=cartao)
    raise ValueError(f"Extensão não suportada: {ext}")


def parse_many(files: Iterable[tuple]) -> pd.DataFrame:
    """Aceita tuplas `(name, content)` ou `(name, content, cartao)`."""
    frames: list[pd.DataFrame] = []
    errors: list[tuple[str, str]] = []
    for entry in files:
        if len(entry) == 3:
            name, content, cartao = entry
        else:
            name, content = entry
            cartao = None
        try:
            frames.append(parse_file(name, content, cartao=cartao))
        except Exception as e:  # noqa: BLE001
            errors.append((name, str(e)))
    if not frames:
        return _empty_frame()
    df = pd.concat(frames, ignore_index=True)
    # de-duplicação básica (mesma data + estabelecimento + valor + fonte + cartao)
    df = df.drop_duplicates(
        subset=["data", "estabelecimento", "valor", "fonte", "parcela", "cartao"]
    ).reset_index(drop=True)
    df.attrs["errors"] = errors
    return df
