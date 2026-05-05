"""Componentes de visualização (Plotly) — tema executivo dark, sem corte de texto."""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from .config import CATEGORIES, CATEGORY_COLORS

# ---------------------------------------------------------------------------
# Tema dark padrão para todos os gráficos
# ---------------------------------------------------------------------------
PLOT_BG = "rgba(0,0,0,0)"
PAPER_BG = "rgba(0,0,0,0)"
TEXT_COLOR = "#E8EDF5"
GRID_COLOR = "rgba(255,255,255,0.08)"
AXIS_COLOR = "rgba(255,255,255,0.35)"


def _apply_dark_layout(fig: go.Figure, *, height: int | None = None,
                       margin: dict | None = None) -> go.Figure:
    fig.update_layout(
        plot_bgcolor=PLOT_BG,
        paper_bgcolor=PAPER_BG,
        font=dict(family="Inter, system-ui, sans-serif", color=TEXT_COLOR, size=13),
        margin=margin or dict(t=10, b=10, l=10, r=10),
        hoverlabel=dict(
            bgcolor="#1B2942",
            font=dict(color=TEXT_COLOR, size=12),
            bordercolor="#FF4B6E",
        ),
    )
    if height:
        fig.update_layout(height=height)
    fig.update_xaxes(
        gridcolor=GRID_COLOR, linecolor=AXIS_COLOR, tickcolor=AXIS_COLOR,
        zerolinecolor=GRID_COLOR,
    )
    fig.update_yaxes(
        gridcolor=GRID_COLOR, linecolor=AXIS_COLOR, tickcolor=AXIS_COLOR,
        zerolinecolor=GRID_COLOR,
    )
    return fig


# ---------------------------------------------------------------------------
# Pizza por categoria — legenda HORIZONTAL embaixo (cabe nomes longos)
# ---------------------------------------------------------------------------
def pie_by_category(df: pd.DataFrame) -> go.Figure:
    grp = (
        df[df["valor"] > 0]
        .groupby("categoria", as_index=False)["valor"]
        .sum()
        .sort_values("valor", ascending=False)
    )
    fig = px.pie(
        grp,
        values="valor",
        names="categoria",
        hole=0.55,
        color="categoria",
        color_discrete_map=CATEGORY_COLORS,
    )
    # Texto DENTRO das fatias — sem leader lines, sem clipping
    fig.update_traces(
        textposition="inside",
        textinfo="percent",
        insidetextorientation="horizontal",
        textfont=dict(color="#FFFFFF", size=12, family="Inter, sans-serif"),
        marker=dict(line=dict(color="#0F1729", width=2)),
        hovertemplate="<b>%{label}</b><br>R$ %{value:,.2f}<br>%{percent}<extra></extra>",
    )
    fig.update_layout(
        showlegend=True,
        legend=dict(
            orientation="h",
            y=-0.12,
            x=0.5,
            xanchor="center",
            yanchor="top",
            bgcolor="rgba(0,0,0,0)",
            font=dict(color=TEXT_COLOR, size=11),
            itemwidth=30,
        ),
        uniformtext_minsize=10,
        uniformtext_mode="hide",
    )
    # Margem inferior generosa para acomodar legenda em até 2 linhas
    return _apply_dark_layout(
        fig, height=460,
        margin=dict(t=10, b=80, l=10, r=10),
    )


# ---------------------------------------------------------------------------
# Barras empilhadas — evolução · margem inferior para os meses não cortarem
# ---------------------------------------------------------------------------
def stacked_evolution(df: pd.DataFrame) -> go.Figure:
    pos = df[df["valor"] > 0]
    grp = pos.groupby(["mes_ref", "categoria"], as_index=False)["valor"].sum()
    grp = grp.sort_values("mes_ref")
    fig = px.bar(
        grp,
        x="mes_ref",
        y="valor",
        color="categoria",
        color_discrete_map=CATEGORY_COLORS,
        category_orders={"categoria": CATEGORIES},
    )
    fig.update_traces(
        marker=dict(line=dict(color="#0F1729", width=1)),
        hovertemplate="<b>%{x}</b><br>%{fullData.name}: R$ %{y:,.2f}<extra></extra>",
    )
    fig.update_layout(
        barmode="stack",
        xaxis_title=None,
        yaxis_title=None,
        legend=dict(
            orientation="v",
            x=1.02, y=1, xanchor="left", yanchor="top",
            bgcolor="rgba(0,0,0,0)",
            font=dict(color=TEXT_COLOR, size=11),
            title_text="",
        ),
        bargap=0.25,
    )
    fig.update_xaxes(
        type="category",
        tickangle=0,
        tickfont=dict(size=12, color=TEXT_COLOR),
    )
    fig.update_yaxes(tickformat=",.0f", tickfont=dict(size=11, color=TEXT_COLOR))
    return _apply_dark_layout(
        fig, height=460,
        margin=dict(t=10, b=50, l=50, r=180),  # r=180 para a legenda vertical
    )


# ---------------------------------------------------------------------------
# Métricas dos cards
# ---------------------------------------------------------------------------
# Padrões de pagamento de fatura anterior (não contam como "gasto" do mês)
_PAGAMENTO_FATURA_RE = (
    r"Pagamento de fatura"           # XP CSV
    r"|PAGAMENTO\s*DEBITO\s*EM\s*CONTA"  # Sicoob OFX
    r"|Pagamentos Validos Normais"   # variantes do XP
)


def summary_metrics(df: pd.DataFrame) -> dict[str, float]:
    """Métricas dos cards (com lógica robusta de fatura).

    - Total: compras menos refunds, **excluindo** pagamento da fatura anterior.
    - Nº de transações: apenas compras (valor>0, sem pagamentos).
    - Ticket médio: média das compras (positivos).
    - Parcelados: soma de compras com is_parcelado=True.
    """
    if df.empty:
        return {
            "Total no período": 0.0,
            "Ticket médio": 0.0,
            "Nº de transações": 0,
            "Parcelados (R$)": 0.0,
        }
    is_pagamento = df["estabelecimento"].str.contains(
        _PAGAMENTO_FATURA_RE, case=False, regex=True, na=False
    )
    real = df[~is_pagamento]
    pos = real[real["valor"] > 0]
    return {
        "Total no período":  float(real["valor"].sum()),
        "Ticket médio":      float(pos["valor"].mean() or 0),
        "Nº de transações":  int(len(pos)),
        "Parcelados (R$)":   float(pos.loc[pos["is_parcelado"], "valor"].sum()),
    }
