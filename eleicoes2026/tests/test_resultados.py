import numpy as np
import pandas as pd
import pytest

from eleicoes import resultados as r
from eleicoes.dados import carregar_comparecimento, carregar_votos


@pytest.fixture(scope="module")
def votos(projeto):
    return carregar_votos(2026)


@pytest.fixture(scope="module")
def fin(votos):
    return r.finalistas(votos)


def test_finalistas_sao_os_do_segundo_turno(votos, fin):
    assert {fin["A"], fin["B"]} == {22, 13}


def test_finalistas_so_primeiro_turno(votos):
    t1 = votos[votos["NR_TURNO"] == 1]
    f = r.finalistas(t1)
    top2 = t1[t1["TP_VOTO"] == "Nominal"].groupby("NR_VOTAVEL")["QT_VOTOS"].sum().nlargest(2).index
    assert [f["A"], f["B"]] == list(top2)


def test_municipios_colunas_numericas(votos, fin):
    """Regressão: margem_pp era 'object' e nsmallest quebrava."""
    m = r.municipios(votos, 1, fin)
    for c in ["validos", "pct_vencedor", "pct_segundo", "margem_pp", "pct_A", "pct_B", "dif_A_B"]:
        assert pd.api.types.is_numeric_dtype(m[c]), c
    m.nsmallest(5, "margem_pp")
    assert (m["margem_pp"] >= 0).all()
    assert not m["SG_UF"].isin(["ZZ", "VT"]).any()


def test_vencedor_consistente(votos, fin):
    m = r.municipios(votos, 2, fin)
    venceu_a = m["vencedor"] == fin["A"]
    assert (m.loc[venceu_a, "dif_A_B"] >= 0).all()
    assert (m.loc[~venceu_a, "dif_A_B"] <= 0).all()


def test_percentuais_somam_100(votos, fin):
    for nivel in ["SG_UF", "REGIAO"]:
        t = r.percentuais(votos, 1, nivel, fin)
        np.testing.assert_allclose(t[["pct_A", "pct_B", "pct_Outros"]].sum(axis=1), 100)


def test_participacao_com_abstencao(votos):
    comp = carregar_comparecimento(2026)
    p = r.participacao(votos, comp)
    assert set(p.index) == {1, 2}
    assert ((p["pct_abstencao"] > 10) & (p["pct_abstencao"] < 30)).all()
    # comparecimento do detalhe == votos totais da votação por seção, sem exterior/trânsito
    assert (p["qt_comparecimento"] <= p["votos_totais"]).all()


def test_abstencao_por_uf(projeto):
    a = r.abstencao(carregar_comparecimento(2026), "SG_UF")
    assert list(a.columns) == ["turno1", "turno2"]
    assert a.notna().all().all()


def test_candidatos_menores(votos, fin):
    menores = r.candidatos_menores(votos, fin, minimo_pct=1.0)
    assert fin["A"] not in menores and fin["B"] not in menores
    assert set(menores) <= {70, 14, 55, 30}


def test_viradas(votos, fin):
    v = r.viradas(r.municipios(votos, 1, fin), r.municipios(votos, 2, fin))
    assert {"UF", "municipio", "nome_vencedor_t1", "nome_vencedor_t2"} <= set(v.columns)


def test_swing_mesmo_numero(projeto):
    atual, anterior = carregar_votos(2026), carregar_votos(2022)
    s = r.swing(atual, anterior, numero=13, turno=2)
    assert s["swing_pp"].between(-100, 100).all()
    np.testing.assert_allclose(s["swing_pp"], s["pct_atual"] - s["pct_anterior"])


def test_nome_curto():
    assert r.nome_curto("LUIZ INÁCIO LULA DA SILVA") == "Lula"
    assert r.nome_curto("CANDIDATO ÉPSILON ARAÚJO") == "Candidato Araújo"


def test_rotulos_unicos_quando_nomes_coincidem():
    nomes = {13: "JOSÉ DA SILVA", 22: "JOSÉ ANTÔNIO SILVA", 30: "MARIA COSTA"}
    rot = r.rotulos_unicos(nomes, [13, 22, 30])
    assert rot == {13: "José Silva (13)", 22: "José Silva (22)", 30: "Maria Costa"}
