"""
Gera as figuras e o resumo de achados usados no README.

Uso:
    python -m eleicoes.figuras_readme            # tudo (inclui transferência de votos: 1 a 3 min)
    python -m eleicoes.figuras_readme --rapido   # pula a transferência e os modelos

Saídas (vão para o GitHub, ao contrário de figuras/):
    docs/img/*.png     figuras referenciadas no README
    docs/achados.md    números principais calculados dos dados (para conferir e citar)
"""

import argparse
import shutil

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from eleicoes import graficos as gr  # noqa: E402
from eleicoes import resultados as r  # noqa: E402
from eleicoes.config import config, dir_figuras, raiz  # noqa: E402
from eleicoes.dados import (  # noqa: E402
    ORDEM_REGIOES,
    carregar_comparecimento,
    carregar_malha,
    carregar_votos,
    disponivel,
    municipios_ibge,
)


def _br(x: float, casas: int = 1) -> str:
    return f"{x:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _copiar(nome: str, destino: str, geradas: list):
    origem = dir_figuras() / f"{nome}.png"
    if origem.exists():
        shutil.copy(origem, raiz() / "docs" / "img" / f"{destino}.png")
        geradas.append(destino)
    plt.close("all")


def gerar(rapido: bool = False) -> list[str]:
    (raiz() / "docs" / "img").mkdir(parents=True, exist_ok=True)
    ano = int(config()["ano_principal"])
    df = carregar_votos(ano)
    comp = carregar_comparecimento(ano)
    fin = r.finalistas(df)
    na, nb = r.rotulos(fin)
    turnos = r.turnos(df)
    ultimo = turnos[-1]
    malha = carregar_malha()
    geradas: list[str] = []
    linhas = [
        f"# Achados — eleição presidencial {ano}",
        "",
        "Gerado por `python -m eleicoes.figuras_readme` a partir dos dados do TSE.",
        "",
    ]

    # resultado nacional
    resumo = r.resumo_nacional(df)
    linhas += [
        "## Resultado nacional",
        "",
        "| Turno | Candidato | Votos | % válidos |",
        "|---|---|---:|---:|",
    ]
    for _, x in resumo[resumo["tipo"] == "Nominal"].iterrows():
        if x["pct_validos"] >= 1:
            linhas.append(
                f"| {x['turno']}º | {fin['rotulos'][x['nr']]} | {_br(x['votos'], 0)} | "
                f"{_br(x['pct_validos'], 2)}% |"
            )
    part = r.participacao(df, comp)
    if "pct_abstencao" in part:
        linhas += ["", "| Turno | Abstenção | Brancos | Nulos |", "|---|---:|---:|---:|"]
        for t, p in part.iterrows():
            ab = "–" if pd.isna(p.get("pct_abstencao")) else f"{_br(p['pct_abstencao'])}%"
            linhas.append(f"| {t}º | {ab} | {_br(p['pct_brancos'])}% | {_br(p['pct_nulos'])}% |")

    # regiões e UFs
    tab = r.percentuais(df, ultimo, "REGIAO", fin)
    tab = tab.reindex([x for x in ORDEM_REGIOES if x in tab.index])
    gr.barras_empilhadas(tab, fin, f"Votos válidos por região — {ultimo}º turno", "x_regiao")
    _copiar("x_regiao", "regiao", geradas)
    linhas += ["", f"## Por região ({ultimo}º turno)", "", f"| Região | {na} | {nb} |", "|---|---:|---:|"]
    for reg, x in tab.iterrows():
        linhas.append(f"| {reg} | {_br(x['pct_A'])}% | {_br(x['pct_B'])}% |")
    uf = r.percentuais(df, ultimo, "SG_UF", fin).drop(["ZZ", "VT"], errors="ignore")
    gr.barras_empilhadas(uf, fin, f"Votos válidos por UF — {ultimo}º turno", "x_uf")
    _copiar("x_uf", "uf", geradas)

    # mapas
    mun = r.municipios(df, ultimo, fin)
    gr.mapa_margem(mun, malha, fin, ultimo)
    _copiar(f"mapa_margem_turno{ultimo}", "mapa_margem", geradas)
    gr.mapa_proporcional(mun, malha, municipios_ibge(), fin, ultimo)
    _copiar(f"mapa_proporcional_turno{ultimo}", "mapa_proporcional", geradas)
    venc = mun["nome_vencedor"].value_counts()
    linhas += ["", f"## Municípios ({ultimo}º turno)", ""]
    linhas += [f"- {k}: venceu em {_br(v, 0)} municípios" for k, v in venc.items()]

    ab_turnos = r.turnos_com_abstencao(comp)
    if ab_turnos:
        t_ab = ab_turnos[-1]
        ab_mun = r.abstencao(comp[~comp["SG_UF"].isin(["ZZ", "VT"])], "CD_MUNICIPIO").reset_index()
        gr.mapa_continuo(
            malha.merge(ab_mun, on="CD_MUNICIPIO", how="left"),
            f"turno{t_ab}",
            f"Abstenção por município — {t_ab}º turno",
            "x_abstencao",
            limite=40,
            rotulo="% dos eleitores aptos que não votaram",
            centro=None,
        )
        _copiar("x_abstencao", "mapa_abstencao", geradas)

    # 1º -> 2º turno
    if 2 in turnos:
        var = r.variacao_uf(df, fin)
        gr.halteres(
            var,
            "pct_A_t1",
            "pct_A_t2",
            f"{na}: % dos válidos no 1º e no 2º turno, por UF",
            "x_variacao",
            xlabel="% dos votos válidos",
            ref=50,
        )
        _copiar("x_variacao", "variacao_uf", geradas)
        vir = r.viradas(r.municipios(df, 1, fin), mun)
        linhas += [f"- {_br(len(vir), 0)} municípios mudaram de vencedor entre os turnos"]

    if not rapido:
        from eleicoes import espacial, modelo
        from eleicoes import transferencia as tr
        from eleicoes.dados import base_socioeconomica, carregar_secao

        if 2 in turnos:
            print("Transferência de votos (1 a 3 minutos)...")
            menores = r.candidatos_menores(df, fin, minimo_pct=1.0)
            X, Y = tr.preparar(carregar_secao(ano), fin, menores)
            t = tr.estimar(X, Y, n_boot=200)
            gr.matriz_transferencia(t, "Para onde foram os votos do 1º turno", "x_transf")
            _copiar("x_transf", "matriz_transferencia", geradas)
            linhas += [
                "",
                "## Transferência de votos (estimativa, IC 95%)",
                "",
                f"| 1º turno | {' | '.join(t.matriz.columns)} |",
                "|---|" + "---:|" * len(t.matriz.columns),
            ]
            for lin in t.matriz.index:
                cel = [
                    f"{_br(t.matriz.loc[lin, c], 0)}% ({_br(t.ic_inf.loc[lin, c], 0)}–{_br(t.ic_sup.loc[lin, c], 0)})"
                    for c in t.matriz.columns
                ]
                linhas.append(f"| {lin} | {' | '.join(cel)} |")

        print("Análise espacial e modelos...")
        g = malha.merge(mun, on="CD_MUNICIPIO", how="inner")
        mg = espacial.moran(g, "dif_A_B")
        gr.mapa_lisa(
            espacial.lisa(g, "dif_A_B"),
            fin,
            f"Blocos geográficos de voto — {ultimo}º turno",
            "x_lisa",
            moran_global=mg,
        )
        _copiar("x_lisa", "mapa_lisa", geradas)
        base = modelo.montar_base(mun, base_socioeconomica(), alvo="pct_A")
        res, coef = modelo.regressao_linear(base)
        gr.coeficientes(coef, f"% de {na}: efeito de cada variável (regressão ponderada)", "x_coef")
        _copiar("x_coef", "regressao", geradas)
        gbm = modelo.modelo_gbm(base)
        gr.shap_resumo(gbm, f"O que mais explica o % de {na} por município (SHAP)", "x_shap")
        _copiar("x_shap", "shap", geradas)
        m = gbm["metricas"]
        linhas += [
            "",
            "## Análises avançadas",
            "",
            f"- Moran's I = {_br(mg['I'], 3)} (p = {_br(mg['p_valor'], 3)})",
            f"- Regressão ponderada: R² = {_br(res.rsquared, 3)} ({_br(len(base), 0)} municípios)",
            f"- Gradient boosting (validação por UF): R² = {_br(m['r2_validacao_por_uf'], 3)}, "
            f"erro médio {_br(m['mae_pp'])} p.p. (palpite pela média: {_br(m['mae_baseline_pp'])} p.p.)",
            f"- Indicadores mais importantes: {', '.join(gbm['importancia_pp'].index[:3])}",
        ]

    ant = config().get("ano_comparacao")
    if ant and disponivel(int(ant)):
        df_ant = carregar_votos(int(ant))
        t_cmp = ultimo if ultimo in r.turnos(df_ant) else 1
        for numero in [fin["A"], fin["B"]]:
            if numero in set(df_ant.loc[df_ant["TP_VOTO"] == "Nominal", "NR_VOTAVEL"]):
                sw = r.swing(df, df_ant, numero, t_cmp)
                gr.mapa_continuo(
                    malha.merge(sw, on="CD_MUNICIPIO", how="left"),
                    "swing_pp",
                    f"Nº {numero} ({fin['rotulos'][numero]}): variação de {ant} para {ano} — {t_cmp}º turno",
                    "x_swing",
                    limite=20,
                    cmap=gr.cores_numero(numero, fin),
                    rotulo="← perdeu   |   variação (p.p.)   |   ganhou →",
                )
                _copiar("x_swing", f"swing_{numero}", geradas)

    (raiz() / "docs" / "achados.md").write_text("\n".join(linhas) + "\n", encoding="utf-8")
    print(f"{len(geradas)} figuras em docs/img/ e resumo em docs/achados.md")
    return geradas


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--rapido", action="store_true", help="pula a transferência de votos e os modelos")
    gerar(rapido=p.parse_args(argv).rapido)


if __name__ == "__main__":
    main()
