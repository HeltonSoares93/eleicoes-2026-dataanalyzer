import os
import shutil
from pathlib import Path

import matplotlib
import pytest

matplotlib.use("Agg")

from amostra import (  # noqa: E402
    FIXTURES,
    escrever_detalhe,
    escrever_votacao_secao,
    simular_secoes,
)

RAIZ_REPO = Path(__file__).resolve().parents[1]


def _montar_projeto(destino: Path) -> Path:
    """Projeto completo numa pasta temporária: config, fontes externas (recortes reais)
    e arquivos do TSE sintéticos para 2026 e 2022."""
    shutil.copy(RAIZ_REPO / "config.yaml", destino / "config.yaml")
    ext = destino / "data" / "external"
    ext.mkdir(parents=True)
    for f in FIXTURES.iterdir():
        shutil.copy(f, ext / f.name)
    raw = destino / "data" / "raw"
    for ano, semente in [(2026, 1), (2022, 2)]:
        sec = simular_secoes(ano, semente=semente)
        escrever_votacao_secao(sec, raw / f"votacao_secao_{ano}_BR.zip")
        escrever_detalhe(sec, raw / f"detalhe_votacao_munzona_{ano}.zip", semente)
    return destino


@pytest.fixture(scope="session")
def projeto(tmp_path_factory):
    """Projeto temporário já processado. ELEICOES_RAIZ aponta para ele durante a sessão."""
    raiz = _montar_projeto(tmp_path_factory.mktemp("projeto"))
    anterior = os.environ.get("ELEICOES_RAIZ")
    os.environ["ELEICOES_RAIZ"] = str(raiz)

    from eleicoes.processar import processar_ano

    for ano in (2026, 2022):
        processar_ano(ano)
    yield raiz
    if anterior is None:
        os.environ.pop("ELEICOES_RAIZ", None)
    else:
        os.environ["ELEICOES_RAIZ"] = anterior


@pytest.fixture
def raiz_vazia(tmp_path, monkeypatch):
    """Projeto vazio (só config.yaml), para testar erros e downloads."""
    shutil.copy(RAIZ_REPO / "config.yaml", tmp_path / "config.yaml")
    monkeypatch.setenv("ELEICOES_RAIZ", str(tmp_path))
    return tmp_path
