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
def _extract_ofx_tx_info(tx) -> tuple[str, str, bool]:
    """Extrai (estabelecimento, parcela, is_parcelado) de uma transação OFX.

    Se há `payee`, usa-o direto. Senão, o `memo` costuma ter o padrão
    `<NOME>  NN/NN  <CIDADE>` (Sicoob) — separamos por 2+ espaços e
    detectamos a parcela `NN/NN`.
    """
    payee = (getattr(tx, "payee", None) or "").strip()
    memo = (getattr(tx, "memo", None) or "").strip()

    text = memo if not payee else memo
    parts = re.split(r"\s{2,}", text) if text else []

    # Procura padrão NN/NN nas partes (ex: '10/10' = parcela 10 de 10)
    for i, p in enumerate(parts):
        m = re.fullmatch(r"(\d{1,2})/(\d{1,2})", p.strip())
        if not m:
            continue
        a, b = int(m.group(1)), int(m.group(2))
        if not (1 <= a <= b <= 99):
            continue
        parcela_str = f"{a} de {b}"
        is_parc = b > 1
        if payee:
            return payee, parcela_str, is_parc
        name = " ".join(parts[:i]).strip() or memo
        return name, parcela_str, is_parc

    # Sem parcela detectada
    if payee:
        return payee, "-", False
    if parts:
        return parts[0].strip(), "-", False
    return memo, "-", False


def parse_ofx(content: bytes, source: str, cartao: str | None = None) -> pd.DataFrame:
    from ofxparse import OfxParser  # import local para keep startup leve
    from ofxparse.ofxparse import AccountType  # noqa: F401  (importa enum para detecção)

    ofx = OfxParser.parse(io.BytesIO(content))
    rows: list[dict] = []
    for account in ofx.accounts:
        # Detecção de cartão de crédito — várias estratégias para diferentes
        # versões de OFX (SGML legacy x XML moderno). AccountType.CreditCard == 2.
        acc_type_int = getattr(account, "type", None)
        acc_type_str = str(getattr(account, "account_type", "") or "").upper()
        is_credit_card = (
            acc_type_int == 2
            or acc_type_str in {"CREDITLINE", "CREDITCARD"}
            or "CREDIT" in acc_type_str
        )
        for tx in account.statement.transactions:
            valor = float(tx.amount)
            if is_credit_card:
                # OFX de cartão: charges vêm negativos, refunds/pagamentos positivos.
                # Invertemos para a convenção do projeto (compras > 0).
                valor = -valor
            est, parcela, is_parc = _extract_ofx_tx_info(tx)
            rows.append({
                "data": tx.date,
                "estabelecimento": est,
                "portador": "",
                "valor": valor,
                "parcela": parcela,
                "is_parcelado": is_parc,
            })
    return _finalize(pd.DataFrame(rows), source, cartao=cartao)


# ---------------------------------------------------------------------------
# PDF — dispatcher por cartão
# ---------------------------------------------------------------------------
_PDF_DATE_LINE = re.compile(r"^(\d{2}/\d{2})\s+(.+)$")
_PDF_MONEY = re.compile(r"(\d{1,3}(?:\.\d{3})*,\d{2})")
_PDF_PARCELA_TAIL = re.compile(r"(\d{1,2}/\d{1,2})$")

# Sicoob: formato numérico em inglês (R$ 2,975.98), data DD MMM, multi-coluna
_SICOOB_MONTHS = {
    "JAN": 1, "FEV": 2, "MAR": 3, "ABR": 4, "MAI": 5, "JUN": 6,
    "JUL": 7, "AGO": 8, "SET": 9, "OUT": 10, "NOV": 11, "DEZ": 12,
}
_SICOOB_DATE = re.compile(r"\b(\d{1,2})\s+([A-Z]{3})\b")
_SICOOB_VALUE = re.compile(r"(-)?\s*R\$\s*(-?[\d,]*\.\d{2})")
_SICOOB_PARC = re.compile(r"\b(\d{1,2})/(\d{1,2})\b")


def parse_pdf(content: bytes, source: str, cartao: str | None = None) -> pd.DataFrame:
    """Dispatcher PDF — escolhe o parser certo pelo cartão.

    Sicoob e Itaú emitem PDFs com layouts completamente diferentes:
      - Sicoob: numérico em inglês (`R$ 2,975.98`), datas `DD MMM`, multi-coluna,
        extraído via `pdfplumber.extract_tables()`.
      - Itaú: numérico em PT-BR (`R$ 1.234,56`), datas `DD/MM`, seção `Lançamentos:`
        com cabeçalho `DATA ESTABELECIMENTO VALOREMR$`.
    """
    if (cartao or "").lower() == "sicoob":
        return parse_sicoob_pdf(content, source, cartao=cartao)
    return parse_itau_pdf(content, source, cartao=cartao)


# ---------------------------------------------------------------------------
# Sicoob PDF — usa pdfplumber.extract_tables() para isolar cada lançamento
# ---------------------------------------------------------------------------
def parse_sicoob_pdf(content: bytes, source: str, cartao: str | None = None) -> pd.DataFrame:
    """Extrai lançamentos do PDF do Sicoob.

    Estratégia: cada célula de cada tabela detectada pelo pdfplumber contém
    um lançamento (possivelmente multi-linha por causa do layout). Normaliza
    espaços, extrai data (`DD MMM`), valor (`R$ N,NNN.NN` com sinal opcional
    antes do R$), e parcela embutida (`NN/NN`).
    """
    import pdfplumber

    invoice_month = _invoice_month_from_filename(source)
    if invoice_month:
        fat_year = int(invoice_month[:4])
        fat_month = int(invoice_month[5:7])
    else:
        from datetime import date as _date
        fat_year, fat_month = _date.today().year, _date.today().month

    cells: list[str] = []
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables() or []:
                for row in table:
                    for cell in row:
                        if cell:
                            cells.append(cell)

    rows: list[dict] = []
    for cell in cells:
        text = " ".join(cell.split())  # normaliza whitespace (\n vira espaço)
        if not text:
            continue
        upper = text.upper()
        # Ignora linhas de resumo / totais / sem valor
        if any(skip in upper for skip in ("SALDO ANTERIOR", "TOTAL DE ", "TOTAL R$", "PROTEÇÃO")):
            continue

        date_m = _SICOOB_DATE.search(text)
        val_m = _SICOOB_VALUE.search(text)
        if not date_m or not val_m:
            continue
        mon_abbr = date_m.group(2)
        if mon_abbr not in _SICOOB_MONTHS:
            continue
        day = int(date_m.group(1))
        mon = _SICOOB_MONTHS[mon_abbr]

        sign = val_m.group(1) or ""
        raw_val = val_m.group(2)
        valor_str = (sign + raw_val).replace(",", "")  # vírgula = milhar no formato inglês
        try:
            valor = float(valor_str)
        except ValueError:
            continue

        before_date = text[: date_m.start()].strip()
        between = text[date_m.end(): val_m.start()].strip()
        after_value = text[val_m.end():].strip()
        full = " ".join(s for s in [before_date, between, after_value] if s)

        parc_m = _SICOOB_PARC.search(full)
        if parc_m:
            a, b = int(parc_m.group(1)), int(parc_m.group(2))
            if 1 <= a <= b <= 99:
                parcela = f"{a} de {b}"
                is_parc = b > 1
                full = (full[: parc_m.start()] + " " + full[parc_m.end():]).strip()
            else:
                parcela, is_parc = "-", False
        else:
            parcela, is_parc = "-", False

        year = fat_year if mon <= fat_month else fat_year - 1
        try:
            tx_date = pd.Timestamp(year=year, month=mon, day=day)
        except (ValueError, OverflowError):
            continue

        est = " ".join(full.split())
        rows.append({
            "data": tx_date,
            "estabelecimento": est,
            "portador": "",
            "valor": valor,
            "parcela": parcela,
            "is_parcelado": is_parc,
        })

    return _finalize(pd.DataFrame(rows), source, cartao=cartao)


# ---------------------------------------------------------------------------
# Itaú PDF (mantém parse original)
# ---------------------------------------------------------------------------
def parse_itau_pdf(content: bytes, source: str, cartao: str | None = None) -> pd.DataFrame:
    """Extrai lançamentos de uma fatura Itaú em PDF.

    Heurísticas:
      - Texto via pdfplumber (concatena todas as páginas).
      - Início da tabela: linha contendo `Lançamentos:` ou `DATA ESTABELECIMENTO`.
      - Fim da tabela: linha de "próximas faturas" / "Encargos" / "Total".
      - Em cada linha de transação: o PRIMEIRO valor monetário é o da transação;
        valores seguintes (ex: limite de crédito na coluna lateral) são ignorados.
      - Parcela é detectada como sufixo `NN/NN` no nome do estabelecimento
        (PDF Itaú remove os espaços entre palavras).
      - Ano é inferido pelo nome do arquivo (`mes_ref`): se mês > mês da fatura,
        usa o ano anterior; senão, ano da fatura.
    """
    import pdfplumber  # import local — só carrega se PDF for processado

    invoice_month = _invoice_month_from_filename(source)
    if invoice_month:
        fat_year = int(invoice_month[:4])
        fat_month = int(invoice_month[5:7])
    else:
        from datetime import date as _date
        fat_year, fat_month = _date.today().year, _date.today().month

    with pdfplumber.open(io.BytesIO(content)) as pdf:
        full_text = "\n".join((p.extract_text() or "") for p in pdf.pages)

    rows: list[dict] = []
    in_section = False
    section_done = False  # uma vez encerrada, não reabre (evita capturar
                          # 'Compras parceladas - próximas faturas' que tem
                          # o mesmo cabeçalho 'DATA ESTABELECIMENTO VALOREMR$')
    for raw in full_text.split("\n"):
        line = raw.strip()
        if not line:
            continue

        clean = line.replace(" ", "")

        # Início da seção (apenas uma vez!)
        if not in_section and not section_done:
            if "Lançamentos:" in line or "DATAESTABELECIMENTO" in clean:
                in_section = True
            continue

        # Já passamos da seção válida — ignora resto do PDF
        if section_done:
            continue

        # Fim da seção (próximas faturas / encargos / total / total dos lançamentos)
        if (
            "próximasfaturas" in clean.lower()
            or clean.startswith("Encargos")
            or clean.startswith("Total")
            or clean.startswith("Lançamentosnocartão")
            or clean.startswith("LTotaldoslançamentos")
        ):
            in_section = False
            section_done = True
            continue

        # Procura valores monetários — o PRIMEIRO é o da transação
        money_iter = list(_PDF_MONEY.finditer(line))
        if not money_iter:
            continue
        first_m = money_iter[0]
        value_str = first_m.group(1)
        prefix = line[: first_m.start()].rstrip()

        dm = _PDF_DATE_LINE.match(prefix)
        if not dm:
            continue
        ddmm, middle = dm.groups()

        # Parcela no sufixo do estabelecimento
        pm = _PDF_PARCELA_TAIL.search(middle)
        if pm:
            a, b = int(pm.group(1).split("/")[0]), int(pm.group(1).split("/")[1])
            if 1 <= a <= b <= 99:
                parcela = f"{a} de {b}"
                is_parc = b > 1
                est = middle[: pm.start()].rstrip()
            else:
                parcela, is_parc, est = "-", False, middle.strip()
        else:
            parcela, is_parc, est = "-", False, middle.strip()

        # Ano via heurística
        try:
            day, mon = int(ddmm[:2]), int(ddmm[3:])
        except ValueError:
            continue
        year = fat_year if mon <= fat_month else fat_year - 1
        try:
            tx_date = pd.Timestamp(year=year, month=mon, day=day)
        except (ValueError, OverflowError):
            continue

        valor = float(value_str.replace(".", "").replace(",", "."))

        rows.append({
            "data": tx_date,
            "estabelecimento": est,
            "portador": "",
            "valor": valor,
            "parcela": parcela,
            "is_parcelado": is_parc,
        })

    return _finalize(pd.DataFrame(rows), source, cartao=cartao)


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------
_SUPPORTED = {".csv", ".xlsx", ".xls", ".ofx", ".pdf"}


def parse_file(name: str, content: bytes, cartao: str | None = None) -> pd.DataFrame:
    ext = Path(name).suffix.lower()
    if ext == ".csv":
        return parse_csv(content, source=name, cartao=cartao)
    if ext in (".xlsx", ".xls"):
        return parse_xlsx(content, source=name, cartao=cartao)
    if ext == ".ofx":
        return parse_ofx(content, source=name, cartao=cartao)
    if ext == ".pdf":
        return parse_pdf(content, source=name, cartao=cartao)
    raise ValueError(f"Extensão não suportada: {ext}")


def parse_many(files: Iterable[tuple]) -> pd.DataFrame:
    """Aceita tuplas `(name, content)` ou `(name, content, cartao)`."""
    from .config import PAGAMENTO_FATURA_RE

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
    # Filtra pagamentos de fatura (não são despesas — quitação da fatura anterior)
    is_pagamento = df["estabelecimento"].str.contains(
        PAGAMENTO_FATURA_RE, case=False, regex=True, na=False
    )
    df = df.loc[~is_pagamento].copy()
    # de-duplicação básica (mesma data + estabelecimento + valor + fonte + cartao)
    df = df.drop_duplicates(
        subset=["data", "estabelecimento", "valor", "fonte", "parcela", "cartao"]
    ).reset_index(drop=True)
    df.attrs["errors"] = errors
    return df
