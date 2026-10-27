"""
Cálculos sobre os resultados (sem gráficos). Usado pelos notebooks e pelo app.

Nenhum candidato é fixado no código: os finalistas são detectados nos dados
(os dois do 2º turno, se houver; senão, os dois mais votados do 1º).
"""

import numpy as np
import pandas as pd

from eleicoes.dados import FORA_DO_MAPA

# Nomes de exibição para quem não é conhecido por "primeiro + último nome".
# Chave = nome como está no arquivo do TSE (maiúsculas).
APELIDOS = {
    "LUIZ INÁCIO LULA DA SILVA": "Lula",
    "JAIR MESSIAS BOLSONARO": "Jair Bolsonaro",
    "FLAVIO NANTES BOLSONARO": "Flávio Bolsonaro",
    "AUGUSTO JORGE CURY": "Augusto Cury",
    "RENAN ANTONIO FERREIRA DOS SANTOS": "Renan Santos",
    "RONALDO RAMOS CAIADO": "Ronaldo Caiado",
    "ROMEU ZEMA NETO": "Romeu Zema",
}


def nome_curto(nome: str) -> str:
    if nome.upper() in APELIDOS:
        return APELIDOS[nome.upper()]
    partes = nome.title().split()
    return f"{partes[0]} {partes[-1]}" if len(partes) > 1 else nome.title()


def turnos(df: pd.DataFrame) -> list[int]:
    return sorted(int(t) for t in df["NR_TURNO"].unique())


def rotulos_unicos(nomes: dict[int, str], numeros) -> dict[int, str]:
    """Nome curto de cada número; se dois coincidirem, acrescenta o número: 'Fulano Silva (13)'."""
    base = {int(nr): nome_curto(nomes[nr]) for nr in numeros}
    contagem = pd.Series(list(base.values())).value_counts()
    return {nr: f"{n} ({nr})" if contagem[n] > 1 else n for nr, n in base.items()}


def nomes_votaveis(df: pd.DataFrame) -> dict[int, str]:
    return df.drop_duplicates("NR_VOTAVEL").set_index("NR_VOTAVEL")["NM_VOTAVEL"].to_dict()


def finalistas(df: pd.DataFrame) -> dict:
    """{'A': nr, 'B': nr, 'nomes': {nr: nome}}. A = o mais votado do 1º turno."""
    nom = df[df["TP_VOTO"] == "Nominal"]
    t1 = nom[nom["NR_TURNO"] == 1].groupby("NR_VOTAVEL")["QT_VOTOS"].sum()
    if 2 in turnos(df):
        pares = sorted(nom.loc[nom["NR_TURNO"] == 2, "NR_VOTAVEL"].unique(), key=lambda n: -t1.get(n, 0))
    else:
        pares = t1.sort_values(ascending=False).index.tolist()
    if len(pares) < 2:
        raise ValueError("Menos de dois candidatos nominais nos dados.")
    nomes = nomes_votaveis(df)
    nominais = sorted(nom["NR_VOTAVEL"].unique())
    # 'rotulos': nome de exibição de cada candidato, sem repetição
    return {
        "A": int(pares[0]),
        "B": int(pares[1]),
        "nomes": nomes,
        "rotulos": rotulos_unicos(nomes, nominais),
    }


def rotulos(fin: dict) -> tuple[str, str]:
    return fin["rotulos"][fin["A"]], fin["rotulos"][fin["B"]]


# ------------------------------------------------------------------ nacional


def resumo_nacional(df: pd.DataFrame) -> pd.DataFrame:
    linhas = []
    for t in turnos(df):
        d = df[df["NR_TURNO"] == t]
        total = d["QT_VOTOS"].sum()
        validos = d.loc[d["TP_VOTO"] == "Nominal", "QT_VOTOS"].sum()
        for (nr, nm, tp), v in d.groupby(["NR_VOTAVEL", "NM_VOTAVEL", "TP_VOTO"])["QT_VOTOS"].sum().items():
            linhas.append(
                {
                    "turno": t,
                    "nr": nr,
                    "nome": nm,
                    "tipo": tp,
                    "votos": int(v),
                    "pct_validos": v / validos * 100 if tp == "Nominal" else np.nan,
                    "pct_total": v / total * 100,
                }
            )
    return (
        pd.DataFrame(linhas).sort_values(["turno", "votos"], ascending=[True, False]).reset_index(drop=True)
    )


def participacao(df: pd.DataFrame, comp: pd.DataFrame | None = None) -> pd.DataFrame:
    """Por turno: votos totais, brancos, nulos e, se houver o detalhe da apuração,
    eleitores aptos, comparecimento e abstenção."""
    g = df.groupby(["NR_TURNO", "TP_VOTO"])["QT_VOTOS"].sum().unstack(fill_value=0)
    out = pd.DataFrame(index=g.index)
    out["votos_totais"] = g.sum(axis=1)
    out["validos"] = g.get("Nominal", 0)
    out["brancos"] = g.get("Branco", 0)
    out["nulos"] = g.get("Nulo", 0) + g.get("Anulado", 0)
    out["pct_brancos"] = out["brancos"] / out["votos_totais"] * 100
    out["pct_nulos"] = out["nulos"] / out["votos_totais"] * 100
    if comp is not None:
        c = comp.groupby("NR_TURNO")[["QT_APTOS", "QT_COMPARECIMENTO", "QT_ABSTENCOES"]].sum()
        out = out.join(c.rename(columns=str.lower))
        out["pct_abstencao"] = out["qt_abstencoes"] / out["qt_aptos"] * 100
    return out


# ------------------------------------------------------------------ por nível geográfico


def percentuais(df: pd.DataFrame, turno: int, nivel: str, fin: dict) -> pd.DataFrame:
    """% dos válidos de A, B e Outros por nível (SG_UF, REGIAO...)."""
    d = df[(df["NR_TURNO"] == turno) & (df["TP_VOTO"] == "Nominal")]
    grupo = np.select([d["NR_VOTAVEL"] == fin["A"], d["NR_VOTAVEL"] == fin["B"]], ["A", "B"], "Outros")
    tab = d.assign(grupo=grupo).pivot_table(
        index=nivel, columns="grupo", values="QT_VOTOS", aggfunc="sum", fill_value=0
    )
    tab = tab.reindex(columns=["A", "B", "Outros"], fill_value=0).astype("int64")
    tab["validos"] = tab[["A", "B", "Outros"]].sum(axis=1)
    for c in ["A", "B", "Outros"]:
        tab[f"pct_{c}"] = tab[c] / tab["validos"] * 100
    return tab


def municipios(df: pd.DataFrame, turno: int, fin: dict) -> pd.DataFrame:
    """Uma linha por município: vencedor, margem sobre o 2º colocado (p.p.) e diferença A − B."""
    d = df[(df["NR_TURNO"] == turno) & (df["TP_VOTO"] == "Nominal") & ~df["SG_UF"].isin(FORA_DO_MAPA)]
    chave = ["SG_UF", "CD_MUNICIPIO", "NM_MUNICIPIO"]
    piv = d.pivot_table(
        index=chave, columns="NR_VOTAVEL", values="QT_VOTOS", aggfunc="sum", fill_value=0
    ).astype("float64")
    validos = piv.sum(axis=1)
    pct = piv.div(validos, axis=0) * 100
    ordem = np.argsort(-pct.to_numpy(), axis=1)
    vals = pct.to_numpy()
    out = pd.DataFrame(index=pct.index)
    out["validos"] = validos.astype("int64")
    out["vencedor"] = pct.columns.to_numpy()[ordem[:, 0]]
    out["pct_vencedor"] = np.take_along_axis(vals, ordem[:, :1], 1)[:, 0]
    out["pct_segundo"] = np.take_along_axis(vals, ordem[:, 1:2], 1)[:, 0] if vals.shape[1] > 1 else 0.0
    out["margem_pp"] = out["pct_vencedor"] - out["pct_segundo"]
    out["pct_A"] = pct[fin["A"]] if fin["A"] in pct else 0.0
    out["pct_B"] = pct[fin["B"]] if fin["B"] in pct else 0.0
    out["dif_A_B"] = out["pct_A"] - out["pct_B"]
    out["nome_vencedor"] = out["vencedor"].map(fin["rotulos"])
    return out.reset_index()


def turnos_com_abstencao(comp: pd.DataFrame | None) -> list[int]:
    """Turnos presentes no detalhe da apuração (pode ter só o 1º enquanto o TSE não atualiza)."""
    return [] if comp is None else sorted(int(t) for t in comp["NR_TURNO"].unique())


def abstencao(comp: pd.DataFrame, nivel: str) -> pd.DataFrame:
    """% de abstenção por turno e nível (SG_UF, REGIAO ou CD_MUNICIPIO)."""
    g = comp.groupby([nivel, "NR_TURNO"])[["QT_APTOS", "QT_ABSTENCOES"]].sum()
    g["pct_abstencao"] = g["QT_ABSTENCOES"] / g["QT_APTOS"] * 100
    return g["pct_abstencao"].unstack("NR_TURNO").rename(columns=lambda t: f"turno{t}")


# ------------------------------------------------------------------ demais candidatos


def candidatos_menores(df: pd.DataFrame, fin: dict, minimo_pct: float = 1.0) -> list[int]:
    r = resumo_nacional(df)
    r = r[(r["turno"] == 1) & (r["tipo"] == "Nominal")]
    r = r[~r["nr"].isin([fin["A"], fin["B"]]) & (r["pct_validos"] >= minimo_pct)]
    return r["nr"].astype(int).tolist()


def pct_candidato(df: pd.DataFrame, nr: int, nivel: str = "SG_UF", turno: int = 1) -> pd.Series:
    d = df[(df["NR_TURNO"] == turno) & (df["TP_VOTO"] == "Nominal") & ~df["SG_UF"].isin(FORA_DO_MAPA)]
    validos = d.groupby(nivel)["QT_VOTOS"].sum()
    cand = d[d["NR_VOTAVEL"] == nr].groupby(nivel)["QT_VOTOS"].sum()
    return cand.reindex(validos.index, fill_value=0) / validos * 100


def pct_nacional(df: pd.DataFrame, nr: int, turno: int = 1) -> float:
    d = df[(df["NR_TURNO"] == turno) & (df["TP_VOTO"] == "Nominal")]
    return float(d.loc[d["NR_VOTAVEL"] == nr, "QT_VOTOS"].sum() / d["QT_VOTOS"].sum() * 100)


def top_municipios(df: pd.DataFrame, nr: int, n: int = 10, min_validos: int = 10_000) -> pd.DataFrame:
    d = df[(df["NR_TURNO"] == 1) & (df["TP_VOTO"] == "Nominal") & ~df["SG_UF"].isin(FORA_DO_MAPA)]
    chave = ["SG_UF", "NM_MUNICIPIO"]
    validos = d.groupby(chave)["QT_VOTOS"].sum()
    cand = d[d["NR_VOTAVEL"] == nr].groupby(chave)["QT_VOTOS"].sum()
    t = pd.DataFrame({"validos": validos, "votos": cand.reindex(validos.index, fill_value=0)})
    t = t[t["validos"] >= min_validos]
    t["pct"] = t["votos"] / t["validos"] * 100
    return t.sort_values("pct", ascending=False).head(n).reset_index()


# ------------------------------------------------------------------ 1º → 2º turno


def variacao_uf(df: pd.DataFrame, fin: dict) -> pd.DataFrame:
    t1, t2 = percentuais(df, 1, "SG_UF", fin), percentuais(df, 2, "SG_UF", fin)
    v = pd.DataFrame(
        {
            "pct_A_t1": t1["pct_A"],
            "pct_A_t2": t2["pct_A"],
            "pct_B_t1": t1["pct_B"],
            "pct_B_t2": t2["pct_B"],
            "pct_outros_t1": t1["pct_Outros"],
        }
    ).dropna()
    v["ganho_A"] = v["pct_A_t2"] - v["pct_A_t1"]
    v["ganho_B"] = v["pct_B_t2"] - v["pct_B_t1"]
    return v.drop(FORA_DO_MAPA, errors="ignore")


def transferencia_municipal(df: pd.DataFrame, fin: dict) -> pd.DataFrame:
    """Por município: % dos demais no 1º turno e ganho de A (p.p.) no 2º."""
    m1 = municipios(df, 1, fin).set_index("CD_MUNICIPIO")
    m2 = municipios(df, 2, fin).set_index("CD_MUNICIPIO")
    return pd.DataFrame(
        {
            "outros_t1": 100 - m1["pct_A"] - m1["pct_B"],
            "ganho_A": m2["pct_A"] - m1["pct_A"],
            "validos": m1["validos"],
        }
    ).dropna()


def viradas(mun_t1: pd.DataFrame, mun_t2: pd.DataFrame) -> pd.DataFrame:
    j = mun_t1.set_index("CD_MUNICIPIO").join(
        mun_t2.set_index("CD_MUNICIPIO"), lsuffix="_t1", rsuffix="_t2", how="inner"
    )
    j = j[j["vencedor_t1"] != j["vencedor_t2"]]
    return (
        j[
            [
                "SG_UF_t1",
                "NM_MUNICIPIO_t1",
                "nome_vencedor_t1",
                "nome_vencedor_t2",
                "margem_pp_t2",
                "validos_t2",
            ]
        ]
        .rename(columns={"SG_UF_t1": "UF", "NM_MUNICIPIO_t1": "municipio"})
        .sort_values("validos_t2", ascending=False)
    )


# ------------------------------------------------------------------ entre eleições


def pct_numero_municipio(df: pd.DataFrame, numero: int, turno: int) -> pd.Series:
    """% dos válidos do número de urna `numero` em cada município (código TSE)."""
    d = df[(df["NR_TURNO"] == turno) & (df["TP_VOTO"] == "Nominal") & ~df["SG_UF"].isin(FORA_DO_MAPA)]
    validos = d.groupby("CD_MUNICIPIO")["QT_VOTOS"].sum()
    cand = d[d["NR_VOTAVEL"] == numero].groupby("CD_MUNICIPIO")["QT_VOTOS"].sum()
    return cand.reindex(validos.index, fill_value=0) / validos * 100


def swing(df_atual: pd.DataFrame, df_anterior: pd.DataFrame, numero: int, turno: int) -> pd.DataFrame:
    """Variação (p.p.) da votação de um mesmo número de urna (partido) entre duas eleições.
    Usa o mesmo turno nas duas; códigos TSE de município são estáveis entre eleições."""
    atual = pct_numero_municipio(df_atual, numero, turno)
    anterior = pct_numero_municipio(df_anterior, numero, turno)
    validos = (
        df_atual[(df_atual["NR_TURNO"] == turno) & (df_atual["TP_VOTO"] == "Nominal")]
        .groupby("CD_MUNICIPIO")["QT_VOTOS"]
        .sum()
    )
    out = pd.DataFrame({"pct_anterior": anterior, "pct_atual": atual, "validos": validos}).dropna()
    out["swing_pp"] = out["pct_atual"] - out["pct_anterior"]
    return out.reset_index()
