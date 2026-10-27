"""
App interativo: resultado por município, com filtro de turno e UF.

Rodar (com o projeto instalado e os dados processados):
    pip install -e ".[app]"
    streamlit run app/streamlit_app.py
"""

import numpy as np
import plotly.graph_objects as go
import streamlit as st
from plotly.colors import sample_colorscale

from eleicoes import resultados as r
from eleicoes.config import config, dir_processed
from eleicoes.dados import (
    carregar_comparecimento,
    carregar_malha,
    carregar_votos,
    contornos_uf,
    municipios_ibge,
)
from eleicoes.graficos import COR_A, COR_A_CLARA, COR_B, COR_B_CLARA, COR_NEUTRA, milhar

st.set_page_config(page_title="Eleições presidenciais", layout="wide")

anos = sorted(
    (int(p.name) for p in dir_processed().glob("*") if (p / "votos_municipio.parquet").exists()), reverse=True
)
if not anos:
    st.error("Nenhum dado processado. Rode `python -m eleicoes.baixar` e `python -m eleicoes.processar`.")
    st.stop()


@st.cache_data
def dados(ano: int):
    df = carregar_votos(ano)
    return df, carregar_comparecimento(ano), r.finalistas(df)


@st.cache_data
def geo():
    malha = carregar_malha()
    malha["UF_COD"] = malha["CD_IBGE"] // 100000
    return malha, municipios_ibge()


ano_padrao = int(config()["ano_principal"])
with st.sidebar:
    ano = st.selectbox("Eleição", anos, index=anos.index(ano_padrao) if ano_padrao in anos else 0)
    df, comp, fin = dados(ano)
    turno = st.radio("Turno", r.turnos(df), index=len(r.turnos(df)) - 1, format_func=lambda t: f"{t}º turno")
    ufs = sorted(set(df["SG_UF"]) - {"ZZ", "VT"})
    uf = st.selectbox("Recorte", ["Brasil", *ufs])

na, nb = r.rotulos(fin)
mun = r.municipios(df, turno, fin)
recorte = df if uf == "Brasil" else df[df["SG_UF"] == uf]
if uf != "Brasil":
    mun = mun[mun["SG_UF"] == uf]

st.title(f"Presidente {ano} — {turno}º turno" + ("" if uf == "Brasil" else f" — {uf}"))

d = recorte[(recorte["NR_TURNO"] == turno) & (recorte["TP_VOTO"] == "Nominal")]
validos = d["QT_VOTOS"].sum()
c = st.columns(4)
for col, nr, nome in [(c[0], fin["A"], na), (c[1], fin["B"], nb)]:
    v = d.loc[d["NR_VOTAVEL"] == nr, "QT_VOTOS"].sum()
    col.metric(nome, f"{v / validos * 100:.2f}%".replace(".", ","))
    col.caption(f"{milhar(v)} votos")
c[2].metric("Municípios", milhar(len(mun)))
if comp is not None:
    cc = comp[
        (comp["NR_TURNO"] == turno)
        & ((comp["SG_UF"] == uf) if uf != "Brasil" else ~comp["SG_UF"].isin(["ZZ", "VT"]))
    ]
    c[3].metric(
        "Abstenção",
        f"{cc['QT_ABSTENCOES'].sum() / cc['QT_APTOS'].sum() * 100:.1f}%".replace(".", ",")
        if len(cc)
        else "—",
    )

escala = [[0, COR_B], [0.25, COR_B_CLARA], [0.5, COR_NEUTRA], [0.75, COR_A_CLARA], [1, COR_A]]
LIMITE = 60
malha, coords = geo()


def contornos(geoms):
    """Coordenadas dos contornos (separadas por None) para desenhar com go.Scatter."""
    xs, ys = [], []
    for g in geoms:
        for p in getattr(g, "geoms", [g]):
            x, y = p.exterior.xy
            xs += [*x, None]
            ys += [*y, None]
    return xs, ys


def dica(m):
    return (
        f"<b>{m.NM_MUNICIPIO}</b> ({m.SG_UF})<br>{na}: {m.pct_A:.1f}%<br>{nb}: {m.pct_B:.1f}%"
        f"<br>Votos válidos: {milhar(m.validos)}"
    ).replace(".", ",")


# Mapa desenhado só com dados locais (não depende de mapas-base da internet)
fig = go.Figure()
cor_t = {
    "cmin": -LIMITE,
    "cmax": LIMITE,
    "colorscale": escala,
    "colorbar": {
        "title": f"← {nb} | {na} →",
        "tickvals": [-60, -30, 0, 30, 60],
        "ticktext": ["60", "30", "0", "30", "60"],
    },
}
if uf == "Brasil":
    xs, ys = contornos(contornos_uf(malha).geometry)
    fig.add_trace(
        go.Scatter(
            x=xs,
            y=ys,
            mode="lines",
            fill="toself",
            fillcolor="#efeee9",
            line={"color": "white", "width": 1},
            hoverinfo="skip",
            showlegend=False,
        )
    )
    pts = mun.merge(coords[["CD_MUNICIPIO", "LAT", "LON"]], on="CD_MUNICIPIO").sort_values(
        "validos", ascending=False
    )
    fig.add_trace(
        go.Scatter(
            x=pts["LON"],
            y=pts["LAT"],
            mode="markers",
            showlegend=False,
            hovertext=[dica(m) for m in pts.itertuples()],
            hoverinfo="text",
            marker={
                "size": pts["validos"],
                "sizemode": "area",
                "sizeref": 2 * pts["validos"].max() / 40**2,
                "sizemin": 1.5,
                "color": pts["dif_A_B"].clip(-LIMITE, LIMITE),
                "opacity": 0.85,
                "line": {"color": "white", "width": 0.5},
                **cor_t,
            },
        )
    )
    st.caption("Cada círculo é um município; área proporcional aos votos válidos.")
else:
    g = malha.merge(mun, on="CD_MUNICIPIO", how="inner")
    cores = sample_colorscale(escala, ((g["dif_A_B"].clip(-LIMITE, LIMITE) + LIMITE) / (2 * LIMITE)).tolist())
    for m, cor in zip(g.itertuples(), cores, strict=True):
        xs, ys = contornos([m.geometry])
        fig.add_trace(
            go.Scatter(
                x=xs,
                y=ys,
                mode="lines",
                fill="toself",
                fillcolor=cor,
                line={"color": "white", "width": 0.6},
                hoveron="fills",
                text=dica(m),
                hoverinfo="text",
                showlegend=False,
            )
        )
    fig.add_trace(
        go.Scatter(x=[None], y=[None], mode="markers", showlegend=False, marker={"color": [0], **cor_t})
    )
lat_media = coords["LAT"].mean() if uf == "Brasil" else coords.loc[coords["UF"] == uf, "LAT"].mean()
fig.update_xaxes(visible=False)
fig.update_yaxes(visible=False, scaleanchor="x", scaleratio=1 / np.cos(np.deg2rad(lat_media)))
fig.update_layout(
    height=640,
    margin={"l": 0, "r": 0, "t": 0, "b": 0},
    plot_bgcolor="rgba(0,0,0,0)",
    hoverlabel={"bgcolor": "white"},
)
st.plotly_chart(fig, width="stretch")

st.subheader("Municípios")
tabela = (
    mun[["SG_UF", "NM_MUNICIPIO", "validos", "nome_vencedor", "pct_A", "pct_B", "margem_pp"]]
    .rename(
        columns={
            "SG_UF": "UF",
            "NM_MUNICIPIO": "Município",
            "validos": "Votos válidos",
            "nome_vencedor": "Vencedor",
            "pct_A": f"% {na}",
            "pct_B": f"% {nb}",
            "margem_pp": "Margem (p.p.)",
        }
    )
    .sort_values("Votos válidos", ascending=False)
)
busca = st.text_input("Buscar município")
if busca:
    tabela = tabela[tabela["Município"].str.contains(busca.upper(), regex=False)]
st.dataframe(
    tabela,
    hide_index=True,
    width="stretch",
    column_config={
        "Votos válidos": st.column_config.NumberColumn(format="localized"),
        **{c: st.column_config.NumberColumn(format="%.1f") for c in [f"% {na}", f"% {nb}", "Margem (p.p.)"]},
    },
)
st.caption("Fonte: TSE (dados abertos). Exterior e voto em trânsito não aparecem no mapa.")
