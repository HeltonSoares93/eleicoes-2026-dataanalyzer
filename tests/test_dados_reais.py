"""
Testes sobre os SEUS dados reais em data/processed/ (pulados se não existirem).

Rodar:  pytest -m dados_reais -v
"""

import pandas as pd
import pytest

from eleicoes.config import RAIZ_PADRAO, _ler_config, config, pasta_processada
from eleicoes.dados import carregar_comparecimento, carregar_votos, disponivel
from eleicoes.processar import conferir_comparecimento

pytestmark = pytest.mark.dados_reais


@pytest.fixture(autouse=True)
def usar_raiz_real(monkeypatch):
    monkeypatch.setenv("ELEICOES_RAIZ", str(RAIZ_PADRAO))


def _anos():
    cfg = _ler_config(RAIZ_PADRAO / "config.yaml")
    return [a for a in [cfg["ano_principal"], cfg.get("ano_comparacao")] if a]


@pytest.mark.parametrize("ano", _anos())
def test_base_valida(ano):
    if not disponivel(ano):
        pytest.skip(f"{ano} não processado")
    votos = carregar_votos(ano)  # valida o esquema
    assert votos["NR_TURNO"].min() == 1
    nominal = votos[votos["TP_VOTO"] == "Nominal"]
    assert nominal["NR_VOTAVEL"].nunique() >= 2
    # cobertura: praticamente todos os municípios brasileiros
    n_mun = votos.loc[~votos["SG_UF"].isin(["ZZ", "VT"]), "CD_MUNICIPIO"].nunique()
    assert n_mun > 5500, f"apenas {n_mun} municípios"


@pytest.mark.parametrize("ano", _anos())
def test_comparecimento_bate_com_votos(ano):
    comp = carregar_comparecimento(ano) if disponivel(ano) else None
    if comp is None:
        pytest.skip(f"detalhe da apuração de {ano} não processado")
    ruins = conferir_comparecimento(carregar_votos(ano), comp, tolerancia=0.001)
    assert len(ruins) == 0, f"{len(ruins)} municípios com diferença > 0,1%:\n{ruins.head(10)}"


@pytest.mark.parametrize("ano", _anos())
def test_totais_oficiais(ano):
    """Compara com os números informados em `oficial:` no config.yaml."""
    oficial = (config().get("oficial") or {}).get(ano)
    if not oficial or not disponivel(ano):
        pytest.skip("preencha `oficial:` no config.yaml para ativar")
    br = pd.read_csv(pasta_processada(ano, criar=False) / "resumo_brasil.csv")
    for turno, cands in oficial.items():
        for nr, votos in cands.items():
            obtido = br.loc[(br["NR_TURNO"] == int(turno)) & (br["NR_VOTAVEL"] == int(nr)), "QT_VOTOS"].sum()
            assert obtido == votos, f"turno {turno}, nº {nr}: base {obtido:,} x oficial {votos:,}"
