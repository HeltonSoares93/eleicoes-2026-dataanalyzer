import numpy as np
import pytest

from eleicoes import espacial, modelo
from eleicoes import resultados as r
from eleicoes.dados import base_socioeconomica, carregar_malha, carregar_votos


@pytest.fixture(scope="module")
def malha_votos(projeto):
    votos = carregar_votos(2026)
    fin = r.finalistas(votos)
    mun = r.municipios(votos, 1, fin)
    return carregar_malha().merge(mun, on="CD_MUNICIPIO", how="inner"), fin, mun


def test_malha_casa_com_tse(projeto):
    malha = carregar_malha()
    assert malha["CD_MUNICIPIO"].notna().all()
    assert len(malha) == 231


def test_moran_detecta_padrao_plantado(malha_votos):
    g, _, _ = malha_votos
    res = espacial.moran(g, "dif_A_B", permutacoes=199)
    assert res["I"] > 0.2 and res["p_valor"] < 0.05


def test_moran_aleatorio_nao_significativo(malha_votos):
    g, _, _ = malha_votos
    g = g.assign(ruido=np.random.default_rng(0).normal(size=len(g)))
    res = espacial.moran(g, "ruido", permutacoes=199)
    assert abs(res["I"]) < 0.15


def test_lisa_categorias(malha_votos):
    g, _, _ = malha_votos
    out = espacial.lisa(g, "dif_A_B", permutacoes=199)
    assert set(out["lisa"].astype(str)) <= set(espacial.ROTULOS_LISA.values()) | {"Não significativo"}
    assert (out["lisa"] != "Não significativo").any()


def test_base_socioeconomica_completa(projeto):
    s = base_socioeconomica()
    assert s["CD_MUNICIPIO"].notna().all()
    assert s[["IDHM", "RDPC", "POP_2022", "LAT"]].notna().all().all()


def test_regressao_recupera_efeito_do_idhm(malha_votos):
    _, fin, mun = malha_votos
    base = modelo.montar_base(mun, base_socioeconomica(), alvo="pct_A")
    _, tab = modelo.regressao_linear(base, efeito_regiao=False)
    # na amostra, o % do candidato 22 cresce com o IDHM (e com renda/escolaridade)
    sinal = 1 if fin["A"] == 22 else -1
    assert (
        sinal * tab.loc["Renda per capita (log)", "coef_pp"]
        + sinal * tab.loc["Superior completo 25+ (%)", "coef_pp"]
        > 0
    )
    assert modelo.vif(base).notna().all()


def test_gbm_com_shap(malha_votos):
    _, _, mun = malha_votos
    base = modelo.montar_base(mun, base_socioeconomica(), alvo="pct_A")
    res = modelo.modelo_gbm(base, n_shap=100)
    assert res["metricas"]["mae_pp"] < res["metricas"]["mae_baseline_pp"]
    assert res["shap"].values.shape == (100, res["amostra"].shape[1])
    assert res["importancia_pp"].index[0] != ""
