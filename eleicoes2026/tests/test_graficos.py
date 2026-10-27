"""Todo gráfico precisa renderizar e gravar o PNG sem erro."""

import matplotlib.pyplot as plt
import pytest

from eleicoes import espacial, graficos, modelo, transferencia
from eleicoes import resultados as r
from eleicoes.config import dir_figuras
from eleicoes.dados import (
    base_socioeconomica,
    carregar_comparecimento,
    carregar_malha,
    carregar_secao,
    carregar_votos,
    municipios_ibge,
)


@pytest.fixture(scope="module")
def ctx(projeto):
    votos = carregar_votos(2026)
    fin = r.finalistas(votos)
    return votos, fin, carregar_malha()


def _gerou(nome):
    assert (dir_figuras() / f"{nome}.png").stat().st_size > 5_000
    plt.close("all")


def test_barras(ctx):
    votos, fin, _ = ctx
    graficos.barras_empilhadas(r.percentuais(votos, 1, "SG_UF", fin), fin, "UF", "t_barras")
    _gerou("t_barras")


def test_mapas(ctx):
    votos, fin, malha = ctx
    mun = r.municipios(votos, 2, fin)
    graficos.mapa_margem(mun, malha, fin, 2)
    _gerou("mapa_margem_turno2")
    graficos.mapa_proporcional(mun, malha, municipios_ibge(), fin, 2)
    _gerou("mapa_proporcional_turno2")
    comp = carregar_comparecimento(2026)
    ab = r.abstencao(comp, "CD_MUNICIPIO").reset_index()
    graficos.mapa_continuo(
        malha.merge(ab, on="CD_MUNICIPIO"), "turno1", "Abstenção", "t_abst", 40, "% de abstenção", centro=None
    )
    _gerou("t_abst")


def test_halteres_e_menores(ctx):
    votos, fin, _ = ctx
    v = r.variacao_uf(votos, fin)
    graficos.halteres(v, "pct_A_t1", "pct_A_t2", "Variação", "t_halteres", ref=50)
    _gerou("t_halteres")
    menores = r.candidatos_menores(votos, fin)
    pcts = {fin["rotulos"][n]: r.pct_candidato(votos, n) for n in menores}
    nac = {fin["rotulos"][n]: r.pct_nacional(votos, n) for n in menores}
    graficos.menores_uf(pcts, nac, "Menores", "t_menores")
    _gerou("t_menores")
    graficos.dispersao_transferencia(r.transferencia_municipal(votos, fin), fin, "t_disp")
    _gerou("t_disp")


def test_matriz_lisa_coeficientes_shap(ctx):
    votos, fin, malha = ctx
    X, Y = transferencia.preparar(carregar_secao(2026), fin, r.candidatos_menores(votos, fin))
    t = transferencia.estimar(X, Y, n_boot=10)
    graficos.matriz_transferencia(t, "Matriz", "t_matriz")
    _gerou("t_matriz")
    mun = r.municipios(votos, 1, fin)
    g = espacial.lisa(malha.merge(mun, on="CD_MUNICIPIO"), "dif_A_B", permutacoes=99)
    graficos.mapa_lisa(g, fin, "LISA", "t_lisa", {"I": 0.5, "p_valor": 0.001})
    _gerou("t_lisa")
    base = modelo.montar_base(mun, base_socioeconomica())
    _, tab = modelo.regressao_linear(base)
    graficos.coeficientes(tab, "Coeficientes", "t_coef")
    _gerou("t_coef")
    graficos.shap_resumo(modelo.modelo_gbm(base, n_shap=80), "SHAP", "t_shap")
    _gerou("t_shap")
