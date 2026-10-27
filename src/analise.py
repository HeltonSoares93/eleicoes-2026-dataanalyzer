"""
Funções de análise usadas no notebook 01_analise_turnos.ipynb.

Tudo é calculado a partir de data/processed/votos_municipio.parquet,
gerado por src/processar_votacao.py. Nenhum candidato é fixado no código:
os finalistas são detectados nos dados (os dois do 2º turno, se existir;
senão, os dois mais votados do 1º).
"""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm

RAIZ = Path(__file__).resolve().parents[1]
RAW = RAIZ / "data" / "raw"
PROCESSED = RAIZ / "data" / "processed"
FIGURAS = RAIZ / "figuras"

# Malha municipal (IBGE 2010) com o código IBGE de 7 dígitos na coluna "id".
# Municípios criados depois de 2010 (6 no total) ficam sem polígono e aparecem em cinza.
URL_MALHA = (
    "https://raw.githubusercontent.com/tbrugz/geodata-br/master/"
    "geojson/geojs-100-mun.json"
)
URL_DEPARA = (
    "https://raw.githubusercontent.com/betafcc/Municipios-Brasileiros-TSE/"
    "master/municipios_brasileiros_tse.csv"
)

REGIOES = {
    "AC": "Norte", "AP": "Norte", "AM": "Norte", "PA": "Norte", "RO": "Norte",
    "RR": "Norte", "TO": "Norte",
    "AL": "Nordeste", "BA": "Nordeste", "CE": "Nordeste", "MA": "Nordeste",
    "PB": "Nordeste", "PE": "Nordeste", "PI": "Nordeste", "RN": "Nordeste",
    "SE": "Nordeste",
    "DF": "Centro-Oeste", "GO": "Centro-Oeste", "MT": "Centro-Oeste",
    "MS": "Centro-Oeste",
    "ES": "Sudeste", "MG": "Sudeste", "RJ": "Sudeste", "SP": "Sudeste",
    "PR": "Sul", "RS": "Sul", "SC": "Sul",
    "ZZ": "Exterior", "VT": "Em trânsito",
}
ORDEM_REGIOES = ["Norte", "Nordeste", "Centro-Oeste", "Sudeste", "Sul",
                 "Exterior", "Em trânsito"]

# Paleta (validada para daltonismo): finalista A = azul, finalista B = laranja,
# demais = cinza neutro. A cor segue o candidato, não a posição.
COR_A = "#2a78d6"
COR_B = "#eb6834"
COR_OUTROS = "#b5b4ad"
COR_NEUTRA = "#f0efec"
COR_TEXTO = "#0b0b0b"
COR_TEXTO_2 = "#52514e"
FUNDO = "#fcfcfb"

plt.rcParams.update({
    "figure.facecolor": FUNDO, "axes.facecolor": FUNDO,
    "axes.edgecolor": "#d8d7d2", "axes.labelcolor": COR_TEXTO_2,
    "xtick.color": COR_TEXTO_2, "ytick.color": COR_TEXTO_2,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.titleweight": "bold", "axes.titlesize": 13,
    "axes.titlelocation": "left", "font.size": 10,
    "savefig.dpi": 150, "savefig.bbox": "tight",
})


# ---------------------------------------------------------------- dados

def carregar() -> pd.DataFrame:
    df = pd.read_parquet(PROCESSED / "votos_municipio.parquet")
    # O parquet usa inteiros "anuláveis" (Int32/Int8); convertemos para inteiros
    # comuns para que as contas com numpy devolvam números, e não 'object'.
    df["QT_VOTOS"] = df["QT_VOTOS"].fillna(0).astype("int64")
    df["NR_VOTAVEL"] = df["NR_VOTAVEL"].astype("int64")
    df["NR_TURNO"] = df["NR_TURNO"].astype("int64")
    df["CD_MUNICIPIO"] = df["CD_MUNICIPIO"].astype("int64")
    df["SG_UF"] = df["SG_UF"].astype(str)
    df["NM_VOTAVEL"] = df["NM_VOTAVEL"].astype(str)
    df["TP_VOTO"] = df["TP_VOTO"].astype(str)
    df["REGIAO"] = df["SG_UF"].map(REGIOES).fillna("Outros")
    return df


def turnos(df: pd.DataFrame) -> list[int]:
    return sorted(int(t) for t in df["NR_TURNO"].dropna().unique())


def finalistas(df: pd.DataFrame) -> dict:
    """Retorna {'A': nr, 'B': nr, 'nomes': {nr: nome}}.
    A = mais votado do 1º turno entre os dois finalistas."""
    nom = df[df["TP_VOTO"] == "Nominal"]
    t1 = nom[nom["NR_TURNO"] == 1].groupby("NR_VOTAVEL")["QT_VOTOS"].sum()
    if 2 in turnos(df):
        pares = nom[nom["NR_TURNO"] == 2]["NR_VOTAVEL"].unique()
        pares = sorted(pares, key=lambda n: -t1.get(n, 0))[:2]
    else:
        pares = t1.sort_values(ascending=False).index[:2].tolist()
    nomes = (nom.drop_duplicates("NR_VOTAVEL")
             .set_index("NR_VOTAVEL")["NM_VOTAVEL"].to_dict())
    return {"A": int(pares[0]), "B": int(pares[1]), "nomes": nomes}


# Nomes de exibição para quem não é conhecido por "primeiro + último nome".
# Edite à vontade (chave = nome como está no arquivo do TSE, em maiúsculas).
APELIDOS = {
    "LUIZ INÁCIO LULA DA SILVA": "Lula",
}


def nome_curto(nome: str) -> str:
    if nome.upper() in APELIDOS:
        return APELIDOS[nome.upper()]
    partes = nome.title().split()
    return f"{partes[0]} {partes[-1]}" if len(partes) > 1 else nome.title()


def resumo_nacional(df: pd.DataFrame) -> pd.DataFrame:
    """Votos e % por candidato, mais comparecimento, brancos e nulos, por turno."""
    linhas = []
    for t in turnos(df):
        d = df[df["NR_TURNO"] == t]
        total = d["QT_VOTOS"].sum()
        validos = d.loc[d["TP_VOTO"] == "Nominal", "QT_VOTOS"].sum()
        por = d.groupby(["NR_VOTAVEL", "NM_VOTAVEL", "TP_VOTO"])["QT_VOTOS"].sum()
        for (nr, nm, tp), v in por.items():
            linhas.append({
                "turno": t, "nr": nr, "nome": nm, "tipo": tp, "votos": int(v),
                "pct_validos": round(v / validos * 100, 2) if tp == "Nominal" else np.nan,
                "pct_total": round(v / total * 100, 2),
            })
    return (pd.DataFrame(linhas)
            .sort_values(["turno", "votos"], ascending=[True, False])
            .reset_index(drop=True))


def percentuais(df: pd.DataFrame, turno: int, nivel: str, fin: dict) -> pd.DataFrame:
    """% dos votos válidos de A, B e Outros por nível (SG_UF, REGIAO...)."""
    d = df[(df["NR_TURNO"] == turno) & (df["TP_VOTO"] == "Nominal")].copy()
    d["grupo"] = np.select(
        [d["NR_VOTAVEL"] == fin["A"], d["NR_VOTAVEL"] == fin["B"]],
        ["A", "B"], "Outros")
    tab = d.pivot_table(index=nivel, columns="grupo", values="QT_VOTOS",
                        aggfunc="sum", fill_value=0)
    for c in ["A", "B", "Outros"]:
        if c not in tab:
            tab[c] = 0
    tab["validos"] = tab[["A", "B", "Outros"]].sum(axis=1)
    for c in ["A", "B", "Outros"]:
        tab[f"pct_{c}"] = tab[c] / tab["validos"] * 100
    return tab


def municipios(df: pd.DataFrame, turno: int, fin: dict) -> pd.DataFrame:
    """Uma linha por município: vencedor, margem sobre o 2º colocado e
    diferença A − B (em pontos percentuais dos válidos)."""
    d = df[(df["NR_TURNO"] == turno) & (df["TP_VOTO"] == "Nominal")
           & ~df["SG_UF"].isin(["ZZ", "VT"])]
    chave = ["SG_UF", "CD_MUNICIPIO", "NM_MUNICIPIO"]
    piv = d.pivot_table(index=chave, columns="NR_VOTAVEL", values="QT_VOTOS",
                        aggfunc="sum", fill_value=0).astype("float64")
    validos = piv.sum(axis=1)
    pct = piv.div(validos, axis=0) * 100
    ordem = np.argsort(-pct.values, axis=1)
    cols = pct.columns.to_numpy()
    out = pd.DataFrame(index=pct.index)
    out["validos"] = validos.astype("int64")
    out["vencedor"] = cols[ordem[:, 0]]
    out["pct_vencedor"] = np.take_along_axis(pct.values, ordem[:, :1], 1)[:, 0]
    out["pct_segundo"] = np.take_along_axis(pct.values, ordem[:, 1:2], 1)[:, 0]
    out["margem_pp"] = out["pct_vencedor"] - out["pct_segundo"]
    out["pct_A"] = pct.get(fin["A"], 0)
    out["pct_B"] = pct.get(fin["B"], 0)
    out["dif_A_B"] = out["pct_A"] - out["pct_B"]
    out["nome_vencedor"] = out["vencedor"].map(fin["nomes"]).map(nome_curto)
    return out.reset_index()


# ---------------------------------------------------------------- gráficos

def _salvar(fig, nome):
    FIGURAS.mkdir(exist_ok=True)
    fig.savefig(FIGURAS / f"{nome}.png")


def barras_empilhadas(tab: pd.DataFrame, fin: dict, titulo: str, nome_arquivo: str):
    """Barras horizontais 100%: A | Outros | B, ordenadas pela vantagem de A."""
    tab = tab.sort_values("pct_A")
    n = len(tab)
    fig, ax = plt.subplots(figsize=(9, max(2.5, 0.32 * n + 1.2)))
    y = np.arange(n)
    esq = np.zeros(n)
    for col, cor in [("pct_A", COR_A), ("pct_Outros", COR_OUTROS), ("pct_B", COR_B)]:
        ax.barh(y, tab[col], left=esq, color=cor, height=0.72,
                edgecolor=FUNDO, linewidth=1.5)
        esq += tab[col].to_numpy()
    for i, (a, b) in enumerate(zip(tab["pct_A"], tab["pct_B"])):
        ax.text(1, i, f"{a:.1f}%", va="center", ha="left", color="white",
                fontsize=8.5, fontweight="bold")
        ax.text(99, i, f"{b:.1f}%", va="center", ha="right", color="white",
                fontsize=8.5, fontweight="bold")
    ax.axvline(50, color=COR_TEXTO_2, lw=0.8, ls=":")
    ax.set_yticks(y, tab.index)
    ax.set_xlim(0, 100)
    ax.set_xticks([0, 25, 50, 75, 100], ["0%", "25%", "50%", "75%", "100%"])
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)
    ax.set_title(titulo, pad=26)
    na, nb = nome_curto(fin["nomes"][fin["A"]]), nome_curto(fin["nomes"][fin["B"]])
    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in (COR_A, COR_OUTROS, COR_B)]
    ax.legend(handles, [na, "Outros", nb], ncol=3, frameon=False,
              loc="lower left", bbox_to_anchor=(-0.01, 1.0), fontsize=9,
              borderaxespad=0.2, handlelength=1.2)
    ax.set_xlabel("% dos votos válidos")
    fig.tight_layout()
    _salvar(fig, nome_arquivo)
    return fig


def _cmap_divergente():
    return LinearSegmentedColormap.from_list(
        "b_neutro_a", [COR_B, "#f5c3ab", COR_NEUTRA, "#b7d3f6", COR_A])


# ---------------------------------------------------------------- mapa

def carregar_malha():
    """Baixa (uma única vez) a malha municipal do IBGE e a tabela TSE→IBGE,
    guarda em data/raw e devolve o GeoDataFrame com CD_MUNICIPIO (código TSE)."""
    import geopandas as gpd

    RAW.mkdir(parents=True, exist_ok=True)
    arq_malha = RAW / "malha_municipios_ibge.geojson"
    arq_depara = RAW / "municipios_tse_ibge.csv"
    if not arq_malha.exists():
        print("Baixando malha municipal (~22 MB, só na primeira vez)...")
        bruta = gpd.read_file(URL_MALHA)
        bruta = bruta[["id", "geometry"]].rename(columns={"id": "codigo_ibge"})
        # simplifica os contornos: arquivo bem menor e mapa muito mais rápido
        bruta["geometry"] = bruta.geometry.simplify(0.01, preserve_topology=True)
        bruta.to_file(arq_malha, driver="GeoJSON")
    if not arq_depara.exists():
        print("Baixando tabela de correspondência TSE→IBGE...")
        pd.read_csv(URL_DEPARA).to_csv(arq_depara, index=False)

    malha = gpd.read_file(arq_malha)
    malha["codigo_ibge"] = malha["codigo_ibge"].astype(int)
    depara = pd.read_csv(arq_depara)[["codigo_tse", "codigo_ibge"]]
    malha = malha.merge(depara, on="codigo_ibge", how="left")
    malha = malha.rename(columns={"codigo_tse": "CD_MUNICIPIO"})
    return malha[["CD_MUNICIPIO", "codigo_ibge", "geometry"]]


def mapa_margem(mun: pd.DataFrame, malha, fin: dict, turno: int, limite: float = 60):
    """Mapa divergente: azul = vantagem de A, laranja = vantagem de B,
    intensidade = margem em pontos percentuais. Municípios vencidos por um
    terceiro candidato aparecem hachurados."""
    g = malha.merge(mun, on="CD_MUNICIPIO", how="left")
    sem_dado = g["dif_A_B"].isna().sum()
    if sem_dado:
        print(f"Aviso: {sem_dado} municípios da malha sem dados de votação.")

    fig, ax = plt.subplots(figsize=(10, 10))
    norm = TwoSlopeNorm(vmin=-limite, vcenter=0, vmax=limite)
    g.plot(column=g["dif_A_B"].clip(-limite, limite), cmap=_cmap_divergente(),
           norm=norm, ax=ax, linewidth=0.05, edgecolor=FUNDO,
           missing_kwds={"color": "#e2e1dc"})
    terceiros = g[g["vencedor"].notna() & ~g["vencedor"].isin([fin["A"], fin["B"]])]
    if len(terceiros):
        terceiros.plot(ax=ax, facecolor="none", edgecolor=COR_TEXTO_2,
                       hatch="////", linewidth=0.2)
    ax.set_axis_off()

    na, nb = nome_curto(fin["nomes"][fin["A"]]), nome_curto(fin["nomes"][fin["B"]])
    sm = plt.cm.ScalarMappable(cmap=_cmap_divergente(), norm=norm)
    cb = fig.colorbar(sm, ax=ax, orientation="horizontal", fraction=0.035,
                      pad=0.01, aspect=40)
    ticks = [-limite, -limite / 2, 0, limite / 2, limite]
    cb.set_ticks(ticks, labels=[f"{abs(t):.0f}" for t in ticks])
    cb.set_label(f"← vantagem de {nb}   |   margem (p.p.)   |   vantagem de {na} →",
                 color=COR_TEXTO_2)
    cb.outline.set_visible(False)
    venc = mun["vencedor"].value_counts()
    sub = (f"{na}: {venc.get(fin['A'], 0):,} municípios  ·  "
           f"{nb}: {venc.get(fin['B'], 0):,} municípios").replace(",", ".")
    if len(terceiros):
        sub += f"  ·  outros (hachurado): {len(terceiros)}"
    ax.set_title(f"Quem venceu em cada município — {turno}º turno\n", loc="left")
    ax.text(0, 1.0, sub, transform=ax.transAxes, color=COR_TEXTO_2, fontsize=10)
    _salvar(fig, f"mapa_margem_turno{turno}")
    return fig


# ---------------------------------------------------------------- candidatos menores

def candidatos_menores(df: pd.DataFrame, fin: dict, minimo_pct: float = 1.0) -> list[int]:
    """Candidatos não finalistas com pelo menos `minimo_pct` dos válidos no 1º turno."""
    r = resumo_nacional(df)
    r = r[(r["turno"] == 1) & (r["tipo"] == "Nominal")]
    r = r[~r["nr"].isin([fin["A"], fin["B"]]) & (r["pct_validos"] >= minimo_pct)]
    return r["nr"].astype(int).tolist()


def pct_candidato_uf(df: pd.DataFrame, nr: int) -> pd.Series:
    d = df[(df["NR_TURNO"] == 1) & (df["TP_VOTO"] == "Nominal")]
    validos = d.groupby("SG_UF")["QT_VOTOS"].sum()
    cand = d[d["NR_VOTAVEL"] == nr].groupby("SG_UF")["QT_VOTOS"].sum()
    return (cand / validos * 100).fillna(0).drop(["ZZ", "VT"], errors="ignore")


def grafico_menores_uf(df: pd.DataFrame, fin: dict, nrs: list[int]):
    """Pequenos múltiplos: % de cada candidato menor por UF (1º turno)."""
    n = len(nrs)
    fig, axes = plt.subplots(1, n, figsize=(3.6 * n, 7.5), sharey=False)
    axes = np.atleast_1d(axes)
    for ax, nr in zip(axes, nrs):
        s = pct_candidato_uf(df, nr).sort_values()
        nacional = (df[(df["NR_TURNO"] == 1) & (df["NR_VOTAVEL"] == nr)]["QT_VOTOS"].sum()
                    / df[(df["NR_TURNO"] == 1) & (df["TP_VOTO"] == "Nominal")]["QT_VOTOS"].sum() * 100)
        ax.barh(s.index, s.values, color="#6da7ec", height=0.7)
        top = s.tail(3).index
        ax.barh(top, s[top].values, color="#1c5cab", height=0.7)
        ax.axvline(nacional, color=COR_TEXTO_2, lw=0.8, ls=":")
        ax.text(nacional, len(s) - 0.3, f" Brasil {nacional:.1f}%", fontsize=8,
                color=COR_TEXTO_2, va="bottom")
        for uf in top:
            ax.text(s[uf], uf, f" {s[uf]:.1f}%", va="center", fontsize=8, color=COR_TEXTO)
        ax.set_title(nome_curto(fin["nomes"][nr]), fontsize=11)
        ax.tick_params(axis="y", length=0, labelsize=8)
        ax.spines["left"].set_visible(False)
        ax.set_xlabel("% dos válidos na UF")
    fig.suptitle("Onde se concentraram os votos dos demais candidatos — 1º turno",
                 x=0.01, ha="left", fontweight="bold", fontsize=13)
    fig.tight_layout()
    _salvar(fig, "candidatos_menores_uf")
    return fig


def top_municipios(df: pd.DataFrame, nr: int, n: int = 10, min_validos: int = 10_000):
    """Municípios onde o candidato teve maior % (com piso de votos válidos)."""
    d = df[(df["NR_TURNO"] == 1) & (df["TP_VOTO"] == "Nominal")
           & ~df["SG_UF"].isin(["ZZ", "VT"])]
    chave = ["SG_UF", "NM_MUNICIPIO"]
    validos = d.groupby(chave)["QT_VOTOS"].sum()
    cand = d[d["NR_VOTAVEL"] == nr].groupby(chave)["QT_VOTOS"].sum()
    t = pd.DataFrame({"validos": validos, "votos": cand}).fillna(0)
    t = t[t["validos"] >= min_validos]
    t["pct"] = (t["votos"] / t["validos"] * 100).round(2)
    return t.sort_values("pct", ascending=False).head(n).reset_index()


# ---------------------------------------------------------------- 2º turno

def comparecimento(df: pd.DataFrame) -> pd.DataFrame:
    """Votos totais (≈ comparecimento), brancos e nulos por turno.
    Abstenção exige o arquivo 'Detalhe da apuração'."""
    g = df.groupby(["NR_TURNO", "TP_VOTO"])["QT_VOTOS"].sum().unstack(fill_value=0)
    g["total_votos"] = g.sum(axis=1)
    g["pct_brancos"] = g.get("Branco", 0) / g["total_votos"] * 100
    g["pct_nulos"] = (g.get("Nulo", 0) + g.get("Anulado", 0)) / g["total_votos"] * 100
    return g.round(2)


def variacao_uf(df: pd.DataFrame, fin: dict) -> pd.DataFrame:
    t1 = percentuais(df, 1, "SG_UF", fin)
    t2 = percentuais(df, 2, "SG_UF", fin)
    v = pd.DataFrame({
        "pct_A_t1": t1["pct_A"], "pct_A_t2": t2["pct_A"],
        "pct_B_t1": t1["pct_B"], "pct_B_t2": t2["pct_B"],
        "pct_outros_t1": t1["pct_Outros"],
    }).dropna()
    v["ganho_A"] = v["pct_A_t2"] - v["pct_A_t1"]
    v["ganho_B"] = v["pct_B_t2"] - v["pct_B_t1"]
    return v.round(2)


def grafico_variacao_uf(v: pd.DataFrame, fin: dict):
    """Dumbbell: % de A no 1º turno → 2º turno, por UF."""
    v = v.drop(["ZZ", "VT"], errors="ignore").sort_values("pct_A_t2")
    fig, ax = plt.subplots(figsize=(8, 0.3 * len(v) + 1.5))
    y = np.arange(len(v))
    ax.hlines(y, v["pct_A_t1"], v["pct_A_t2"], color="#cfcec8", lw=2)
    ax.scatter(v["pct_A_t1"], y, s=36, color="white", edgecolor=COR_A, lw=1.5,
               zorder=3, label="1º turno")
    ax.scatter(v["pct_A_t2"], y, s=40, color=COR_A, edgecolor=FUNDO, lw=1.5,
               zorder=4, label="2º turno")
    ax.axvline(50, color=COR_TEXTO_2, lw=0.8, ls=":")
    ax.set_yticks(y, v.index)
    ax.tick_params(axis="y", length=0)
    ax.spines["left"].set_visible(False)
    na = nome_curto(fin["nomes"][fin["A"]])
    ax.set_title(f"{na}: % dos válidos no 1º e no 2º turno, por UF")
    ax.set_xlabel("% dos votos válidos")
    ax.legend(frameon=False, loc="lower right")
    fig.tight_layout()
    _salvar(fig, "variacao_uf")
    return fig


def grafico_transferencia(df: pd.DataFrame, fin: dict):
    """Por município: % dos 'outros' no 1º turno (x) vs. ganho de A em p.p. (y).
    Leitura ecológica: mostra associação entre municípios, não o voto individual."""
    m1 = municipios(df, 1, fin).set_index("CD_MUNICIPIO")
    m2 = municipios(df, 2, fin).set_index("CD_MUNICIPIO")
    x = 100 - m1["pct_A"] - m1["pct_B"]
    y = m2["pct_A"] - m1["pct_A"]
    t = pd.DataFrame({"outros_t1": x, "ganho_A": y, "validos": m1["validos"]}).dropna()
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.scatter(t["outros_t1"], t["ganho_A"], s=np.clip(t["validos"] / 2000, 4, 120),
               color=COR_A, alpha=0.35, edgecolor="white", linewidth=0.4)
    na = nome_curto(fin["nomes"][fin["A"]])
    ax.plot([0, t["outros_t1"].max()], [0, t["outros_t1"].max()], color=COR_TEXTO_2,
            lw=0.8, ls="--")
    ax.text(t["outros_t1"].max(), t["outros_t1"].max(),
            f" se {na} ficasse com\n 100% dos 'outros'",
            fontsize=8, color=COR_TEXTO_2, va="center")
    ax.axhline(0, color="#cfcec8", lw=0.8)
    ax.set_title(f"Para onde foram os votos dos demais candidatos? (ganho de {na})")
    ax.set_xlabel("% dos válidos dados aos demais candidatos no 1º turno")
    ax.set_ylabel(f"Ganho de {na} do 1º para o 2º turno (p.p.)")
    corr = t[["outros_t1", "ganho_A"]].corr().iloc[0, 1]
    ax.text(0.01, 0.98, f"correlação = {corr:.2f}   (tamanho = votos válidos)",
            transform=ax.transAxes, va="top", color=COR_TEXTO_2, fontsize=9)
    fig.tight_layout()
    _salvar(fig, "transferencia_votos")
    return fig, t
