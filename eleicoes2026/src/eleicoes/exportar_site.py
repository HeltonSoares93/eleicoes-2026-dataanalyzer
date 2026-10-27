"""
Exporta os dados da página web (site/data/) a partir das bases processadas.

Uso:
    python -m eleicoes.exportar_site                 # tudo, inclusive análises avançadas
    python -m eleicoes.exportar_site --sem-avancado  # mais rápido: pula modelos

Depois, para ver localmente:
    python -m http.server -d site 8000      e abra http://localhost:8000

Arquivos gerados (pequenos, só números agregados de dados públicos):
    meta.json         ano, turnos, finalistas, o que está disponível
    resumo.json       resultado nacional e participação por turno
    agregados.json    % por UF e por região, por turno
    municipios.json   resultado de cada município (formato colunar)
    malha.json        contornos dos municípios (GeoJSON simplificado)
    ufs.json          contornos das UFs
    avancado.json     transferência de votos, LISA, regressão, gradient boosting
"""

import argparse
import json
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from eleicoes import resultados as r
from eleicoes.config import config, raiz
from eleicoes.dados import (
    FORA_DO_MAPA,
    ORDEM_REGIOES,
    REGIOES,
    base_socioeconomica,
    carregar_comparecimento,
    carregar_malha,
    carregar_secao,
    carregar_votos,
    contornos_uf,
    disponivel,
    municipios_ibge,
)

TOLERANCIA_MALHA = 0.015  # graus (~1,5 km): equilíbrio entre detalhe e tamanho do arquivo
CASAS = 2  # casas decimais dos percentuais


def pasta_site() -> Path:
    return raiz() / "site"


def _num(x, casas=CASAS):
    """float -> número arredondado; NaN -> None (vira null no JSON)."""
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return None
    return round(float(x), casas)


def _lista(serie, casas=CASAS):
    return [_num(v, casas) for v in serie]


def _gravar(nome: str, obj) -> Path:
    destino = pasta_site() / "data" / nome
    destino.parent.mkdir(parents=True, exist_ok=True)
    texto = json.dumps(obj, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    destino.write_text(texto, encoding="utf-8")
    print(f"  {nome:<16} {len(texto.encode()) / 1e3:>8,.0f} KB")
    return destino


# ------------------------------------------------------------------ partes


def exportar_resumo(df, comp, fin) -> dict:
    part = r.participacao(df, comp)
    out = {}
    for t in r.turnos(df):
        d = df[(df["NR_TURNO"] == t) & (df["TP_VOTO"] == "Nominal")]
        validos = d["QT_VOTOS"].sum()
        cands = d.groupby("NR_VOTAVEL")["QT_VOTOS"].sum().sort_values(ascending=False)
        p = part.loc[t]
        out[str(t)] = {
            "candidatos": [
                {"nr": int(nr), "rotulo": fin["rotulos"][nr], "votos": int(v), "pct": _num(v / validos * 100)}
                for nr, v in cands.items()
            ],
            "validos": int(validos),
            "votos_totais": int(p["votos_totais"]),
            "brancos": int(p["brancos"]),
            "nulos": int(p["nulos"]),
            "aptos": int(p["qt_aptos"]) if "qt_aptos" in p else None,
            "abstencao_pct": _num(p["pct_abstencao"]) if "pct_abstencao" in p else None,
        }
    return out


def exportar_agregados(df, comp, fin) -> dict:
    out = {"uf": {}, "regiao": {}}
    for t in r.turnos(df):
        for nivel, chave in [("SG_UF", "uf"), ("REGIAO", "regiao")]:
            tab = r.percentuais(df, t, nivel, fin)
            if nivel == "SG_UF":
                tab = tab.drop(FORA_DO_MAPA, errors="ignore")
            else:
                tab = tab.reindex([x for x in ORDEM_REGIOES if x in tab.index])
            abst = None
            if comp is not None:
                abst = r.abstencao(comp, nivel).get(f"turno{t}")
            linhas = []
            for nome, row in tab.iterrows():
                linha = {
                    "nome": nome,
                    "validos": int(row["validos"]),
                    "A": _num(row["pct_A"]),
                    "B": _num(row["pct_B"]),
                    "O": _num(row["pct_Outros"]),
                    "abst": _num(abst.get(nome)) if abst is not None else None,
                }
                if nivel == "SG_UF":
                    linha["regiao"] = REGIOES.get(nome)
                linhas.append(linha)
            out[chave][str(t)] = linhas
    return out


def exportar_municipios(df, comp, fin, df_ant=None) -> tuple[dict, pd.Index]:
    """Formato colunar: uma lista por campo, todas na mesma ordem de municípios."""
    base = municipios_ibge()[["CD_MUNICIPIO", "LAT", "LON"]].dropna(subset=["CD_MUNICIPIO"])
    base["CD_MUNICIPIO"] = base["CD_MUNICIPIO"].astype("int64")
    nomes = df[~df["SG_UF"].isin(FORA_DO_MAPA)].drop_duplicates("CD_MUNICIPIO")[
        ["CD_MUNICIPIO", "SG_UF", "NM_MUNICIPIO"]
    ]
    m = nomes.merge(base, on="CD_MUNICIPIO", how="left").sort_values(["SG_UF", "NM_MUNICIPIO"])
    m = m.reset_index(drop=True)
    out = {
        "cd": m["CD_MUNICIPIO"].astype(int).tolist(),
        "nome": m["NM_MUNICIPIO"].str.title().tolist(),
        "uf": m["SG_UF"].tolist(),
        "lat": _lista(m["LAT"], 3),
        "lon": _lista(m["LON"], 3),
    }
    idx = pd.Index(m["CD_MUNICIPIO"])
    for t in r.turnos(df):
        mt = r.municipios(df, t, fin).set_index("CD_MUNICIPIO").reindex(idx)
        bloco = {
            "validos": [None if pd.isna(v) else int(v) for v in mt["validos"]],
            "A": _lista(mt["pct_A"]),
            "B": _lista(mt["pct_B"]),
            "venc": [None if pd.isna(v) else int(v) for v in mt["vencedor"]],
            "margem": _lista(mt["margem_pp"]),
        }
        if comp is not None:
            ab = r.abstencao(comp[~comp["SG_UF"].isin(FORA_DO_MAPA)], "CD_MUNICIPIO").reindex(idx)
            bloco["abst"] = _lista(ab.get(f"turno{t}", pd.Series(index=idx, dtype=float)))
        out[f"t{t}"] = bloco
    if df_ant is not None:
        t_cmp = r.turnos(df)[-1] if r.turnos(df)[-1] in r.turnos(df_ant) else 1
        nominais_ant = set(df_ant.loc[df_ant["TP_VOTO"] == "Nominal", "NR_VOTAVEL"])
        sw = {}
        for nr in [fin["A"], fin["B"]]:
            if nr in nominais_ant:
                s = r.swing(df, df_ant, nr, t_cmp).set_index("CD_MUNICIPIO").reindex(idx)
                sw[str(nr)] = _lista(s["swing_pp"])
        out["swing"] = {"turno": t_cmp, "por_numero": sw}
    return out, idx


def exportar_malha() -> tuple[dict, dict]:
    import shapely

    malha = carregar_malha().dropna(subset=["CD_MUNICIPIO"])
    g = malha[["CD_MUNICIPIO", "CD_IBGE", "geometry"]].copy()
    g["geometry"] = g.geometry.simplify(TOLERANCIA_MALHA, preserve_topology=True).make_valid().buffer(0)
    g["geometry"] = shapely.set_precision(g.geometry.values, 0.001)
    g = g[~g.geometry.is_empty]
    mun = json.loads(
        g.rename(columns={"CD_MUNICIPIO": "c"})[["c", "geometry"]].astype({"c": int}).to_json(drop_id=True)
    )
    ufs = contornos_uf(malha)
    ufs["geometry"] = shapely.set_precision(ufs.geometry.values, 0.01)
    return mun, json.loads(ufs[["uf", "geometry"]].to_json(drop_id=True))


def exportar_avancado(df, fin, idx: pd.Index, n_boot: int) -> dict:
    from eleicoes import espacial, modelo
    from eleicoes import transferencia as tr

    turnos = r.turnos(df)
    ultimo = turnos[-1]
    out = {"turno": ultimo, "transferencia": None, "espacial": None, "regressao": None, "gbm": None}

    if 2 in turnos:
        print("  transferência de votos (inferência ecológica)...")
        menores = r.candidatos_menores(df, fin, minimo_pct=1.0)
        X, Y = tr.preparar(carregar_secao(ano_principal()), fin, menores)
        t = tr.estimar(X, Y, n_boot=n_boot)
        out["transferencia"] = {
            "linhas": list(t.matriz.index),
            "colunas": list(t.matriz.columns),
            "pct": [_lista(linha, 1) for linha in t.matriz.to_numpy()],
            "ic_inf": [_lista(linha, 1) for linha in t.ic_inf.to_numpy()],
            "ic_sup": [_lista(linha, 1) for linha in t.ic_sup.to_numpy()],
            "votos": [[int(v) for v in linha] for linha in t.fluxos.to_numpy()],
            "n_secoes": t.n_secoes,
            "erro_ajuste": _num(t.erro_ajuste),
        }

    print("  análise espacial (Moran's I e LISA)...")
    mun = r.municipios(df, ultimo, fin)
    g = carregar_malha().merge(mun, on="CD_MUNICIPIO", how="inner")
    mg = espacial.moran(g, "dif_A_B")
    gl = espacial.lisa(g, "dif_A_B").set_index("CD_MUNICIPIO")
    cats = list(gl["lisa"].cat.categories)
    codigo = gl["lisa"].cat.codes.reindex(idx)
    out["espacial"] = {
        "I": _num(mg["I"], 3),
        "p_valor": _num(mg["p_valor"], 3),
        "n": mg["n"],
        "categorias": cats,
        "lisa": [None if pd.isna(c) else int(c) for c in codigo],
    }

    print("  modelos socioeconômicos...")
    base = modelo.montar_base(mun, base_socioeconomica(), alvo="pct_A")
    res, coef = modelo.regressao_linear(base)
    out["regressao"] = {
        "r2": _num(res.rsquared, 3),
        "n": len(base),
        "coef": [
            {
                "var": v,
                "coef": _num(c["coef_pp"]),
                "ic_inf": _num(c["ic_inf"]),
                "ic_sup": _num(c["ic_sup"]),
                "p": _num(c["p_valor"], 4),
            }
            for v, c in coef.iterrows()
        ],
    }
    gbm = modelo.modelo_gbm(base)
    met = gbm["metricas"]
    out["gbm"] = {
        "r2": _num(met["r2_validacao_por_uf"], 3),
        "mae": _num(met["mae_pp"]),
        "mae_base": _num(met["mae_baseline_pp"]),
        "importancia": [{"var": v, "valor": _num(x)} for v, x in gbm["importancia_pp"].head(10).items()],
    }
    return out


def ano_principal() -> int:
    return int(config()["ano_principal"])


def exportar(avancado: bool = True, n_boot: int = 200) -> Path:
    ano = ano_principal()
    df = carregar_votos(ano)
    comp = carregar_comparecimento(ano)
    fin = r.finalistas(df)
    ant = config().get("ano_comparacao")
    df_ant = carregar_votos(int(ant)) if ant and disponivel(int(ant)) else None

    print(f"Exportando dados da página ({ano}) para {pasta_site() / 'data'}")
    resumo = exportar_resumo(df, comp, fin)
    _gravar("resumo.json", resumo)
    _gravar("agregados.json", exportar_agregados(df, comp, fin))
    muni, idx = exportar_municipios(df, comp, fin, df_ant)
    _gravar("municipios.json", muni)
    malha, ufs = exportar_malha()
    _gravar("malha.json", malha)
    _gravar("ufs.json", ufs)
    tem_avancado = False
    if avancado:
        _gravar("avancado.json", exportar_avancado(df, fin, idx, n_boot))
        tem_avancado = True
    else:
        (pasta_site() / "data" / "avancado.json").unlink(missing_ok=True)

    meta = {
        "ano": ano,
        "ano_comparacao": int(ant) if df_ant is not None else None,
        "turnos": r.turnos(df),
        "finalistas": {k: {"nr": fin[k], "rotulo": fin["rotulos"][fin[k]]} for k in ("A", "B")},
        "candidatos": {str(k): v for k, v in fin["rotulos"].items()},
        "tem_abstencao": comp is not None,
        "tem_swing": bool(muni.get("swing", {}).get("por_numero")),
        "tem_avancado": tem_avancado,
        "gerado_em": datetime.now().strftime("%d/%m/%Y %H:%M"),
    }
    _gravar("meta.json", meta)
    print("Pronto. Para ver: python -m http.server -d site 8000  ->  http://localhost:8000")
    return pasta_site()


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--sem-avancado", action="store_true", help="não calcula as análises avançadas")
    p.add_argument("--n-boot", type=int, default=200, help="réplicas do bootstrap da transferência")
    a = p.parse_args(argv)
    exportar(avancado=not a.sem_avancado, n_boot=a.n_boot)


if __name__ == "__main__":
    main()
