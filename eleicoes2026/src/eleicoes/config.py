"""
Caminhos do projeto e leitura do config.yaml.

A raiz do projeto é a pasta que contém o config.yaml. Ela pode ser trocada pela
variável de ambiente ELEICOES_RAIZ (é assim que os testes rodam numa pasta
temporária sem tocar nos seus dados).
"""

import os
from functools import lru_cache
from pathlib import Path

import yaml

RAIZ_PADRAO = Path(__file__).resolve().parents[2]


def raiz() -> Path:
    return Path(os.environ.get("ELEICOES_RAIZ", RAIZ_PADRAO))


def dir_data() -> Path:
    return raiz() / "data"


def dir_raw() -> Path:
    return dir_data() / "raw"


def dir_external() -> Path:
    return dir_data() / "external"


def dir_processed() -> Path:
    return dir_data() / "processed"


def dir_figuras() -> Path:
    return raiz() / "figuras"


@lru_cache
def _ler_config(caminho: Path) -> dict:
    with open(caminho, encoding="utf-8") as f:
        return yaml.safe_load(f)


def config() -> dict:
    return _ler_config(raiz() / "config.yaml")


def pasta_processada(ano: int, criar: bool = True) -> Path:
    """Bases limpas de um ano: data/processed/<ano>/."""
    p = dir_processed() / str(ano)
    if criar:
        p.mkdir(parents=True, exist_ok=True)
    return p


def arquivo_tse(chave: str, ano: int) -> Path:
    """Caminho local de um arquivo do TSE (ex.: data/raw/votacao_secao_2026_BR.zip)."""
    url = config()["tse"][chave].format(ano=ano)
    return dir_raw() / url.rsplit("/", 1)[-1]


def arquivo_externo(chave: str) -> Path:
    return dir_external() / config()["externas"][chave]["arquivo"]
