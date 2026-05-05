"""Testes dos parsers — geram fixtures sintéticas em memória.

Rode com:
    pytest tests/ -v
"""
from __future__ import annotations

import io
from datetime import datetime

import pandas as pd
import pytest

from src.parsers import (
    _invoice_month_from_filename,
    _parse_parcela,
    _parse_valor_brl,
    parse_csv,
    parse_many,
    parse_xlsx,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
class TestValorBRL:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("R$ 193,00", 193.00),
            ("R$ 1.800,00", 1800.00),
            ("R$ -6.786,87", -6786.87),
            ("193.00", 193.00),
            ("1800", 1800.00),
            ("(123,45)", -123.45),  # parênteses = negativo
            ("-", 0.0),
            ("", 0.0),
            (None, 0.0),
            (193.0, 193.0),
        ],
    )
    def test_parse_brl(self, raw, expected):
        assert _parse_valor_brl(raw) == pytest.approx(expected)


class TestParcela:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("-", (False, "-")),
            ("", (False, "-")),
            (None, (False, "-")),
            ("1 de 6", (True, "1 de 6")),
            ("3/12", (True, "3 de 12")),
            ("1 de 1", (True, "1 de 1")),
        ],
    )
    def test_parcela(self, raw, expected):
        assert _parse_parcela(raw) == expected


class TestInvoiceMonth:
    @pytest.mark.parametrize(
        "name,expected",
        [
            ("Fatura2026-01-10 (1).csv", "2026-01"),
            ("Fatura_2025-12-15.xlsx", "2025-12"),
            ("fatura-2024-03-08.csv", "2024-03"),
            ("Fatura20260110.csv", "2026-01"),
            ("extrato_marco.ofx", None),
            ("", None),
            ("Fatura2026-13-10.csv", None),  # mês inválido
        ],
    )
    def test_invoice_month(self, name, expected):
        assert _invoice_month_from_filename(name) == expected


# ---------------------------------------------------------------------------
# CSV
# ---------------------------------------------------------------------------
SAMPLE_CSV = b"""Data;Estabelecimento;Portador;Valor;Parcela
02/12/2025;ESSENZA FARMACIA;ARI GOMES;R$ 193,00;-
03/12/2025;CENTER CAR ROMANO;ARI GOMES;R$ 208,00;1 de 2
03/12/2025;Pagamento de fatura;ARI GOMES;R$ -6.786,87; de 1
"""


class TestParseCSV:
    def test_basic_parse(self):
        df = parse_csv(SAMPLE_CSV, source="Fatura2026-01-10.csv")
        assert len(df) == 3
        assert list(df.columns) == [
            "data", "estabelecimento", "portador", "cartao", "valor", "parcela",
            "is_parcelado", "categoria", "subcategoria", "tipo",
            "mes_ref", "fonte",
        ]

    def test_default_cartao(self):
        df = parse_csv(SAMPLE_CSV, source="Fatura2026-01-10.csv")
        assert (df["cartao"] == "XP").all()

    def test_explicit_cartao(self):
        df = parse_csv(SAMPLE_CSV, source="Fatura2026-01-10.csv", cartao="Sicoob")
        assert (df["cartao"] == "Sicoob").all()

    def test_invoice_month_overrides_purchase_date(self):
        df = parse_csv(SAMPLE_CSV, source="Fatura2026-01-10.csv")
        # compras feitas em 12/2025, mas a fatura é a de janeiro/2026
        assert df["mes_ref"].unique().tolist() == ["2026-01"]

    def test_value_signs(self):
        df = parse_csv(SAMPLE_CSV, source="Fatura2026-01-10.csv")
        assert (df["valor"] > 0).sum() == 2
        assert (df["valor"] < 0).sum() == 1
        assert df["valor"].sum() == pytest.approx(193 + 208 - 6786.87)

    def test_parcelado_detection(self):
        df = parse_csv(SAMPLE_CSV, source="Fatura2026-01-10.csv")
        assert df["is_parcelado"].sum() == 1
        assert df.loc[df["is_parcelado"], "parcela"].iat[0] == "1 de 2"

    def test_fallback_when_no_invoice_in_filename(self):
        df = parse_csv(SAMPLE_CSV, source="extrato_solto.csv")
        assert df["mes_ref"].unique().tolist() == ["2025-12"]


# ---------------------------------------------------------------------------
# XLSX (gera o fixture programaticamente)
# ---------------------------------------------------------------------------
def _build_xlsx() -> bytes:
    df = pd.DataFrame({
        "Data Compra": ["02/12/2025", "15/12/2025"],
        "Estabelecimento": ["POSTO X", "MERCADO Y"],
        "Valor (R$)": ["100,50", "75,00"],
        "Parcela": ["-", "1 de 3"],
    })
    buf = io.BytesIO()
    df.to_excel(buf, index=False, engine="openpyxl")
    return buf.getvalue()


class TestParseXLSX:
    def test_basic(self):
        df = parse_xlsx(_build_xlsx(), source="Fatura2026-01-10.xlsx")
        assert len(df) == 2
        assert df["valor"].sum() == pytest.approx(175.50)
        assert df["mes_ref"].unique().tolist() == ["2026-01"]
        assert df["is_parcelado"].sum() == 1

    def test_xlsx_cartao(self):
        df = parse_xlsx(_build_xlsx(), source="Fatura2026-01-10.xlsx", cartao="Itaú")
        assert (df["cartao"] == "Itaú").all()


# ---------------------------------------------------------------------------
# parse_many — múltiplos arquivos + de-duplicação
# ---------------------------------------------------------------------------
class TestParseMany:
    def test_combines_multiple_sources(self):
        files = [
            ("Fatura2026-01-10.csv", SAMPLE_CSV),
            ("Fatura2026-02-10.csv", SAMPLE_CSV),  # mesmas linhas, fatura diferente
        ]
        df = parse_many(files)
        # mesma fatura aparece 2 vezes (faturas distintas)
        assert sorted(df["mes_ref"].unique()) == ["2026-01", "2026-02"]
        assert len(df) == 6

    def test_skips_unsupported(self):
        files = [
            ("Fatura2026-01-10.csv", SAMPLE_CSV),
            ("readme.txt", b"not a fatura"),
        ]
        df = parse_many(files)
        assert len(df) == 3
        assert df.attrs.get("errors")  # registrou o erro do .txt

    def test_per_file_cartao(self):
        files = [
            ("Fatura2026-01-10.csv", SAMPLE_CSV, "XP"),
            ("Fatura2026-02-10.csv", SAMPLE_CSV, "Sicoob"),
        ]
        df = parse_many(files)
        assert sorted(df["cartao"].unique()) == ["Sicoob", "XP"]
        # dedup respeita o cartao — 2 faturas distintas + cartoes distintos = 6 linhas
        assert len(df) == 6


class TestClassifierNewSchema:
    """Garante que classify() preenche as 3 dimensões e respeita os defaults."""

    def test_tipo_default_variavel(self):
        from src.classifier import classify
        df = parse_csv(SAMPLE_CSV, source="Fatura2026-01-10.csv")
        df = classify(df, manual_map={})
        # linhas sem parcela devem ser "Variável"
        sem_parc = df[~df["is_parcelado"]]
        assert (sem_parc["tipo"] == "Variável").all()

    def test_tipo_parcelado_quando_tem_parcela(self):
        from src.classifier import classify
        df = parse_csv(SAMPLE_CSV, source="Fatura2026-01-10.csv")
        df = classify(df, manual_map={})
        com_parc = df[df["is_parcelado"]]
        assert (com_parc["tipo"] == "Parcelado").all()

    def test_manual_override_vence_parcelado(self):
        """Se o estabelecimento tem categoria manual, vence is_parcelado para tipo."""
        from src.classifier import classify
        df = parse_csv(SAMPLE_CSV, source="Fatura2026-01-10.csv")
        manual = {
            "CENTER CAR ROMANO": {
                "categoria": "Manutenção Veículo",
                "subcategoria": "Rotina",
                "tipo": "Fixo",
            }
        }
        df = classify(df, manual_map=manual)
        center = df[df["estabelecimento"] == "CENTER CAR ROMANO"]
        assert (center["categoria"] == "Manutenção Veículo").all()
        assert (center["subcategoria"] == "Rotina").all()
        assert (center["tipo"] == "Fixo").all()

    def test_legacy_string_format_compat(self):
        """`{est: 'Categoria'}` (formato antigo) deve ser aceito."""
        from src.classifier import _coerce_entry
        e = _coerce_entry("Hospedagem")
        assert e == {"categoria": "Hospedagem", "subcategoria": None, "tipo": None}
