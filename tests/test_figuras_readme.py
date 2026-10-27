"""O comando que gera as figuras do README roda nos dois cenários de dados."""

import pytest


@pytest.mark.lento
def test_figuras_readme_completo(projeto):
    from eleicoes.config import raiz
    from eleicoes.figuras_readme import gerar

    geradas = gerar()
    esperadas = {
        "regiao",
        "uf",
        "mapa_margem",
        "mapa_proporcional",
        "mapa_abstencao",
        "variacao_uf",
        "matriz_transferencia",
        "mapa_lisa",
        "regressao",
        "shap",
        "swing_13",
        "swing_22",
    }
    assert esperadas <= set(geradas)
    for nome in esperadas:
        assert (raiz() / "docs" / "img" / f"{nome}.png").stat().st_size > 10_000
    achados = (raiz() / "docs" / "achados.md").read_text(encoding="utf-8")
    assert "Resultado nacional" in achados and "Transferência de votos" in achados


def test_figuras_readme_rapido_com_abstencao_parcial(projeto_abstencao_parcial):
    from eleicoes.config import raiz
    from eleicoes.figuras_readme import gerar

    geradas = gerar(rapido=True)
    assert "mapa_abstencao" in geradas and "matriz_transferencia" not in geradas
    assert "| 2º | – |" in (raiz() / "docs" / "achados.md").read_text(encoding="utf-8")
