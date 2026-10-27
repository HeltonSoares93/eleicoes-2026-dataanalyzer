"""
Gráficos do projeto (matplotlib). Todas as figuras são salvas em figuras/.

Paleta (validada para daltonismo): finalista A = azul, finalista B = laranja,
demais candidatos = cinza neutro. A cor segue o candidato, nunca a posição.
"""

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

from eleicoes.config import dir_figuras
from eleicoes.resultados import rotulos

COR_A = "#2a78d6"
COR_A_CLARA = "#b7d3f6"
COR_A_ESCURA = "#1c5cab"
COR_B = "#eb6834"
COR_B_CLARA = "#f5c3ab"
COR_OUTROS = "#b5b4ad"
COR_NEUTRA = "#f0efec"
COR_SEM_DADO = "#e2e1dc"
COR_TEXTO = "#0b0b0b"
COR_TEXTO_2 = "#52514e"
COR_GRADE = "#cfcec8"
FUNDO = "#fcfcfb"

plt.rcParams.update(
    {
        "figure.facecolor": FUNDO,
        "axes.facecolor": FUNDO,
        "savefig.facecolor": FUNDO,
        "axes.edgecolor": "#d8d7d2",
        "axes.labelcolor": COR_TEXTO_2,
        "xtick.color": COR_TEXTO_2,
        "ytick.color": COR_TEXTO_2,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.titleweight": "bold",
        "axes.titlesize": 13,
        "axes.titlelocation": "left",
        "font.size": 10,
        "savefig.dpi": 150,
        "savefig.bbox": "tight",
    }
)


def milhar(n) -> str:
    """12345 -> '12.345' (separador de milhar brasileiro)."""
    return f"{n:,.0f}".replace(",", ".")


def decimal(x: float, casas: int = 1) -> str:
    """1.25 -> '1,3' (vírgula decimal)."""
    return f"{x:.{casas}f}".replace(".", ",")


def salvar(fig, nome: str):
    dir_figuras().mkdir(parents=True, exist_ok=True)
    fig.savefig(dir_figuras() / f"{nome}.png")
    return fig


def divergente(cor_neg=COR_B, cor_pos=COR_A, clara_neg=COR_B_CLARA, clara_pos=COR_A_CLARA):
    return LinearSegmentedColormap.from_list("div", [cor_neg, clara_neg, COR_NEUTRA, clara_pos, cor_pos])


def sequencial(cor=COR_A_ESCURA):
    return LinearSegmentedColormap.from_list("seq", ["#eef4fc", "#9ec5f4", "#3987e5", cor])


def _sem_eixo_y(ax):
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)


# ------------------------------------------------------------------ barras


def barras_empilhadas(tab: pd.DataFrame, fin: dict, titulo: str, nome: str):
    """Barras 100%: A | Outros | B, ordenadas pela vantagem de A."""
    tab = tab.sort_values("pct_A")
    n = len(tab)
    fig, ax = plt.subplots(figsize=(9, max(2.5, 0.32 * n + 1.4)))
    y, esq = np.arange(n), np.zeros(n)
    for col, cor in [("pct_A", COR_A), ("pct_Outros", COR_OUTROS), ("pct_B", COR_B)]:
        ax.barh(y, tab[col], left=esq, color=cor, height=0.72, edgecolor=FUNDO, linewidth=1.5)
        esq += tab[col].to_numpy()
    for i, (a, b) in enumerate(zip(tab["pct_A"], tab["pct_B"], strict=True)):
        ax.text(1, i, f"{a:.1f}%", va="center", ha="left", color="white", fontsize=8.5, fontweight="bold")
        ax.text(99, i, f"{b:.1f}%", va="center", ha="right", color="white", fontsize=8.5, fontweight="bold")
    ax.axvline(50, color=COR_TEXTO_2, lw=0.8, ls=":")
    ax.set_yticks(y, tab.index)
    ax.set_xlim(0, 100)
    ax.set_xticks([0, 25, 50, 75, 100], ["0%", "25%", "50%", "75%", "100%"])
    _sem_eixo_y(ax)
    ax.set_title(titulo, pad=26)
    na, nb = rotulos(fin)
    ax.legend(
        [Patch(color=c) for c in (COR_A, COR_OUTROS, COR_B)],
        [na, "Outros", nb],
        ncol=3,
        frameon=False,
        loc="lower left",
        bbox_to_anchor=(-0.01, 1.0),
        fontsize=9,
        borderaxespad=0.2,
        handlelength=1.2,
    )
    ax.set_xlabel("% dos votos válidos")
    fig.tight_layout()
    return salvar(fig, nome)


def halteres(
    df: pd.DataFrame,
    col_ini: str,
    col_fim: str,
    titulo: str,
    nome: str,
    rotulo_ini="1º turno",
    rotulo_fim="2º turno",
    cor=COR_A,
    xlabel="%",
    ref=None,
):
    """Gráfico de halteres: valor inicial (círculo vazado) → final (círculo cheio) por linha."""
    df = df.sort_values(col_fim)
    fig, ax = plt.subplots(figsize=(8, 0.3 * len(df) + 1.6))
    y = np.arange(len(df))
    ax.hlines(y, df[col_ini], df[col_fim], color=COR_GRADE, lw=2)
    ax.scatter(df[col_ini], y, s=36, color="white", edgecolor=cor, lw=1.5, zorder=3, label=rotulo_ini)
    ax.scatter(df[col_fim], y, s=40, color=cor, edgecolor=FUNDO, lw=1.5, zorder=4, label=rotulo_fim)
    if ref is not None:
        ax.axvline(ref, color=COR_TEXTO_2, lw=0.8, ls=":")
    ax.set_yticks(y, df.index)
    _sem_eixo_y(ax)
    ax.set_title(titulo)
    ax.set_xlabel(xlabel)
    ax.legend(frameon=False, loc="lower right")
    fig.tight_layout()
    return salvar(fig, nome)


def menores_uf(pcts: dict, nacionais: dict, titulo: str, nome: str):
    """Pequenos múltiplos: % de cada candidato menor por UF. pcts = {nome: Series por UF}."""
    n = len(pcts)
    fig, axes = plt.subplots(1, n, figsize=(3.6 * n, 7.5))
    for ax, (nm, s) in zip(np.atleast_1d(axes), pcts.items(), strict=True):
        s = s.sort_values()
        top = s.tail(3).index
        ax.barh(s.index, s.values, color="#6da7ec", height=0.7)
        ax.barh(top, s[top].values, color=COR_A_ESCURA, height=0.7)
        nac = nacionais[nm]
        ax.axvline(nac, color=COR_TEXTO_2, lw=0.8, ls=":")
        ax.text(nac, len(s) - 0.3, f" Brasil {nac:.1f}%", fontsize=8, color=COR_TEXTO_2, va="bottom")
        for uf in top:
            ax.text(s[uf], uf, f" {s[uf]:.1f}%", va="center", fontsize=8, color=COR_TEXTO)
        ax.set_title(nm, fontsize=11)
        ax.tick_params(axis="y", length=0, labelsize=8)
        ax.spines["left"].set_visible(False)
        ax.set_xlabel("% dos válidos na UF")
    fig.suptitle(titulo, x=0.01, ha="left", fontweight="bold", fontsize=13)
    fig.tight_layout()
    return salvar(fig, nome)


def dispersao_transferencia(t: pd.DataFrame, fin: dict, nome: str = "transferencia_municipios"):
    na, _ = rotulos(fin)
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.scatter(
        t["outros_t1"],
        t["ganho_A"],
        s=np.clip(t["validos"] / 2000, 4, 120),
        color=COR_A,
        alpha=0.35,
        edgecolor="white",
        linewidth=0.4,
    )
    mx = t["outros_t1"].max()
    ax.plot([0, mx], [0, mx], color=COR_TEXTO_2, lw=0.8, ls="--")
    ax.text(mx, mx, f" se {na} ficasse com\n 100% dos 'outros'", fontsize=8, color=COR_TEXTO_2, va="center")
    ax.axhline(0, color=COR_GRADE, lw=0.8)
    ax.set_title(f"Ganho de {na} x votos dos demais candidatos, por município")
    ax.set_xlabel("% dos válidos dados aos demais candidatos no 1º turno")
    ax.set_ylabel(f"Ganho de {na} do 1º para o 2º turno (p.p.)")
    corr = t[["outros_t1", "ganho_A"]].corr().iloc[0, 1]
    ax.text(
        0.01,
        0.98,
        f"correlação = {corr:.2f}   (tamanho = votos válidos)",
        transform=ax.transAxes,
        va="top",
        color=COR_TEXTO_2,
        fontsize=9,
    )
    fig.tight_layout()
    return salvar(fig, nome)


def matriz_transferencia(tr, titulo: str, nome: str = "matriz_transferencia"):
    """Mapa de calor da matriz de transferência com IC 95%."""
    m = tr.matriz
    fig, ax = plt.subplots(figsize=(1.9 * m.shape[1] + 2.5, 0.75 * m.shape[0] + 1.6))
    ax.imshow(m.to_numpy(), cmap=sequencial(), vmin=0, vmax=100, aspect="auto")
    for i in range(m.shape[0]):
        for j in range(m.shape[1]):
            v = m.iat[i, j]
            cor = "white" if v > 55 else COR_TEXTO
            ax.text(
                j, i - 0.08, f"{v:.0f}%", ha="center", va="center", color=cor, fontsize=11, fontweight="bold"
            )
            ax.text(
                j,
                i + 0.24,
                f"{tr.ic_inf.iat[i, j]:.0f}–{tr.ic_sup.iat[i, j]:.0f}",
                ha="center",
                va="center",
                color=cor,
                fontsize=7.5,
            )
    ax.set_xticks(range(m.shape[1]), m.columns)
    ax.set_yticks(range(m.shape[0]), m.index)
    ax.xaxis.tick_top()
    ax.set_xlabel("2º turno", labelpad=8)
    ax.xaxis.set_label_position("top")
    ax.set_ylabel("1º turno")
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(length=0)
    ax.set_title(titulo, pad=34)
    fig.text(
        0.01,
        0.01,
        "Linha soma 100%. Faixa = IC 95% (bootstrap por município). "
        f"{milhar(tr.n_secoes)} seções; erro médio de ajuste {decimal(tr.erro_ajuste)} p.p.",
        color=COR_TEXTO_2,
        fontsize=8,
    )
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    return salvar(fig, nome)


def coeficientes(tab: pd.DataFrame, titulo: str, nome: str = "regressao_coeficientes"):
    """Forest plot: coeficiente e IC 95%."""
    tab = tab.iloc[::-1]
    fig, ax = plt.subplots(figsize=(8, 0.42 * len(tab) + 1.4))
    y = np.arange(len(tab))
    sig = tab["p_valor"] < 0.05
    ax.hlines(y, tab["ic_inf"], tab["ic_sup"], color=np.where(sig, COR_A, COR_GRADE), lw=2.5)
    ax.scatter(tab["coef_pp"], y, color=np.where(sig, COR_A, COR_OUTROS), zorder=3, s=36, edgecolor=FUNDO)
    ax.axvline(0, color=COR_TEXTO_2, lw=0.8)
    ax.set_yticks(y, tab.index)
    _sem_eixo_y(ax)
    ax.set_xlabel("Efeito em p.p. (variáveis: +1 desvio-padrão; regiões: vs. Centro-Oeste)")
    ax.set_title(titulo)
    ax.legend(
        [Line2D([], [], color=COR_A, lw=2.5), Line2D([], [], color=COR_GRADE, lw=2.5)],
        ["p < 0,05", "não significativo"],
        frameon=False,
        loc="lower right",
        fontsize=8.5,
    )
    fig.tight_layout()
    return salvar(fig, nome)


def shap_resumo(resultado: dict, titulo: str, nome: str = "shap_resumo"):
    import shap

    plt.figure()
    shap.plots.beeswarm(resultado["shap"], max_display=12, show=False, color=sequencial())
    fig = plt.gcf()
    fig.set_size_inches(9, 6)
    ax = fig.axes[0]
    ax.set_title(titulo, loc="left", fontweight="bold")
    ax.set_xlabel("Contribuição para a previsão (p.p.)")
    rot_y = [
        t.get_text().replace("Sum of", "Soma de outras").replace(" other features", "")
        for t in ax.get_yticklabels()
    ]
    ax.set_yticks(ax.get_yticks(), rot_y)
    if len(fig.axes) > 1:  # barra de cores do SHAP
        cb = fig.axes[-1]
        cb.set_ylabel("Valor da variável", color=COR_TEXTO_2)
        cb.set_yticks(
            cb.get_yticks(), ["Baixo" if t.get_text() == "Low" else "Alto" for t in cb.get_yticklabels()]
        )
    fig.tight_layout()
    return salvar(fig, nome)


# ------------------------------------------------------------------ mapas


def _contorno_ufs(malha):
    from eleicoes.dados import contornos_uf

    return contornos_uf(malha, simplificar=0.005)


def _legenda_divergente(fig, ax, cmap, norm, limite, rotulo):
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    cb = fig.colorbar(sm, ax=ax, orientation="horizontal", fraction=0.035, pad=0.01, aspect=40)
    ticks = [-limite, -limite / 2, 0, limite / 2, limite]
    cb.set_ticks(ticks, labels=[f"{abs(t):.0f}" for t in ticks])
    cb.set_label(rotulo, color=COR_TEXTO_2)
    cb.outline.set_visible(False)
    return cb


def mapa_continuo(
    gdf,
    coluna: str,
    titulo: str,
    nome: str,
    limite: float,
    rotulo: str,
    cmap=None,
    subtitulo: str = "",
    centro: float | None = 0,
):
    """Mapa coroplético de uma variável contínua (divergente se `centro` não for None)."""
    fig, ax = plt.subplots(figsize=(10, 10))
    if centro is None:
        from matplotlib.colors import Normalize

        norm, cmap = Normalize(0, limite), cmap or sequencial()
    else:
        norm, cmap = TwoSlopeNorm(vmin=-limite, vcenter=centro, vmax=limite), cmap or divergente()
    gdf.plot(
        column=gdf[coluna].clip(-limite if centro is not None else 0, limite),
        cmap=cmap,
        norm=norm,
        ax=ax,
        linewidth=0.05,
        edgecolor=FUNDO,
        missing_kwds={"color": COR_SEM_DADO},
    )
    _contorno_ufs(gdf).boundary.plot(ax=ax, color="white", linewidth=0.6)
    ax.set_axis_off()
    if centro is None:
        sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
        cb = fig.colorbar(sm, ax=ax, orientation="horizontal", fraction=0.035, pad=0.01, aspect=40)
        cb.set_label(rotulo, color=COR_TEXTO_2)
        cb.outline.set_visible(False)
    else:
        _legenda_divergente(fig, ax, cmap, norm, limite, rotulo)
    ax.set_title(titulo + ("\n" if subtitulo else ""), loc="left")
    if subtitulo:
        ax.text(0, 1.0, subtitulo, transform=ax.transAxes, color=COR_TEXTO_2, fontsize=10)
    return salvar(fig, nome)


def mapa_margem(mun: pd.DataFrame, malha, fin: dict, turno: int, limite: float = 60):
    """Azul = vantagem de A, laranja = vantagem de B; intensidade = margem (p.p.).
    Municípios vencidos por um terceiro aparecem hachurados."""
    g = malha.merge(mun, on="CD_MUNICIPIO", how="left")
    na, nb = rotulos(fin)
    venc = mun["vencedor"].value_counts()
    terceiros = g[g["vencedor"].notna() & ~g["vencedor"].isin([fin["A"], fin["B"]])]
    sub = f"{na}: {venc.get(fin['A'], 0):,} municípios  ·  {nb}: {venc.get(fin['B'], 0):,} municípios"
    if len(terceiros):
        sub += f"  ·  outros (hachurado): {len(terceiros)}"
    fig = mapa_continuo(
        g,
        "dif_A_B",
        f"Quem venceu em cada município — {turno}º turno",
        f"mapa_margem_turno{turno}",
        limite,
        f"← vantagem de {nb}   |   margem (p.p.)   |   vantagem de {na} →",
        subtitulo=sub.replace(",", "."),
    )
    if len(terceiros):
        terceiros.plot(ax=fig.axes[0], facecolor="none", edgecolor=COR_TEXTO_2, hatch="////", linewidth=0.2)
        salvar(fig, f"mapa_margem_turno{turno}")
    return fig


def mapa_proporcional(
    mun: pd.DataFrame, malha, coords: pd.DataFrame, fin: dict, turno: int, limite: float = 60
):
    """Círculos com área proporcional aos votos válidos: mostra ONDE ESTÃO OS VOTOS,
    corrigindo o viés visual de municípios grandes e pouco populosos."""
    d = mun.merge(coords[["CD_MUNICIPIO", "LAT", "LON"]], on="CD_MUNICIPIO", how="inner")
    d = d.sort_values("validos", ascending=False)
    fig, ax = plt.subplots(figsize=(10, 10))
    _contorno_ufs(malha).plot(ax=ax, color="#efeee9", edgecolor="white", linewidth=0.8)
    norm = TwoSlopeNorm(vmin=-limite, vcenter=0, vmax=limite)
    cmap = divergente()
    tamanho = d["validos"] / d["validos"].max() * 1400
    ax.scatter(
        d["LON"],
        d["LAT"],
        s=tamanho,
        c=d["dif_A_B"].clip(-limite, limite),
        cmap=cmap,
        norm=norm,
        alpha=0.85,
        edgecolor=FUNDO,
        linewidth=0.4,
    )
    ax.set_axis_off()
    ax.set_aspect(1 / np.cos(np.deg2rad(-15)))
    na, nb = rotulos(fin)
    _legenda_divergente(
        fig, ax, cmap, norm, limite, f"← vantagem de {nb}   |   margem (p.p.)   |   vantagem de {na} →"
    )
    # legenda de tamanho
    # referências "redondas" abaixo do maior município (ex.: 5 milhões, 500 mil, 50 mil)
    maximo = d["validos"].max()
    topo = 10 ** np.floor(np.log10(maximo))
    topo = max(m * topo for m in (1, 2, 5) if m * topo <= maximo)
    ref = [topo / 100, topo / 10, topo]
    for v in ref:
        ax.scatter(
            [],
            [],
            s=v / d["validos"].max() * 1400,
            color=COR_OUTROS,
            edgecolor=FUNDO,
            label=f"{milhar(v)} votos",
        )
    ax.legend(
        frameon=False,
        loc="lower left",
        labelspacing=2.2,
        borderpad=1.5,
        fontsize=9,
        title="Votos válidos",
        title_fontsize=9,
    )
    ax.set_title(f"Onde estão os votos — {turno}º turno\n", loc="left")
    ax.text(
        0,
        1.0,
        "Cada círculo é um município; a área é proporcional aos votos válidos.",
        transform=ax.transAxes,
        color=COR_TEXTO_2,
        fontsize=10,
    )
    return salvar(fig, f"mapa_proporcional_turno{turno}")


CORES_LISA = {
    "Alto-Alto": COR_A,
    "Baixo-Baixo": COR_B,
    "Alto-Baixo": COR_A_CLARA,
    "Baixo-Alto": COR_B_CLARA,
    "Não significativo": "#ecebe6",
}


def mapa_lisa(g, fin: dict, titulo: str, nome: str = "mapa_lisa", moran_global: dict | None = None):
    na, nb = rotulos(fin)
    legendas = {
        "Alto-Alto": f"Bloco de {na}",
        "Baixo-Baixo": f"Bloco de {nb}",
        "Alto-Baixo": f"{na} forte, vizinhos não",
        "Baixo-Alto": f"{nb} forte, vizinhos não",
        "Não significativo": "Sem padrão significativo",
    }
    fig, ax = plt.subplots(figsize=(10, 10))
    g.plot(color=g["lisa"].astype(str).map(CORES_LISA), ax=ax, linewidth=0.05, edgecolor=FUNDO)
    _contorno_ufs(g).boundary.plot(ax=ax, color="white", linewidth=0.6)
    ax.set_axis_off()
    contagem = g["lisa"].value_counts()
    ax.legend(
        [Patch(color=CORES_LISA[k]) for k in CORES_LISA],
        [f"{legendas[k]} ({milhar(contagem.get(k, 0))})" for k in CORES_LISA],
        frameon=False,
        loc="lower left",
        fontsize=9,
    )
    sub = ""
    if moran_global:
        sub = (
            f"Moran's I global = {decimal(moran_global['I'], 2)} (p = {decimal(moran_global['p_valor'], 3)})"
        )
    ax.set_title(titulo + ("\n" if sub else ""), loc="left")
    if sub:
        ax.text(0, 1.0, sub, transform=ax.transAxes, color=COR_TEXTO_2, fontsize=10)
    return salvar(fig, nome)


def cores_numero(numero: int, fin: dict):
    """Cor de um número de urna se ele for um dos finalistas; senão, azul."""
    if numero == fin["B"]:
        return divergente(COR_A, COR_B, COR_A_CLARA, COR_B_CLARA)
    return divergente()
