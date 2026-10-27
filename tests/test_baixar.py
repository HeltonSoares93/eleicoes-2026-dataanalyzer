import json

import pytest

from eleicoes.baixar import baixar, manifesto_path, sha256


def test_baixa_registra_manifesto(raiz_vazia, tmp_path):
    origem = tmp_path / "origem.csv"
    origem.write_text("a;b\n1;2\n", encoding="latin-1")
    destino = raiz_vazia / "data/raw/arquivo.csv"
    baixar(origem.as_uri(), destino)
    assert destino.read_bytes() == origem.read_bytes()
    m = json.loads(manifesto_path().read_text(encoding="utf-8"))
    assert m["arquivo.csv"]["sha256"] == sha256(origem)
    assert m["arquivo.csv"]["url"] == origem.as_uri()


def test_nao_baixa_de_novo_sem_forcar(raiz_vazia, tmp_path, capsys):
    origem = tmp_path / "o.csv"
    origem.write_text("x")
    destino = raiz_vazia / "data/raw/o.csv"
    baixar(origem.as_uri(), destino)
    origem.write_text("y")
    baixar(origem.as_uri(), destino)
    assert destino.read_text() == "x"
    assert "já existe" in capsys.readouterr().out
    baixar(origem.as_uri(), destino, forcar=True)
    assert destino.read_text() == "y"


def test_hash_diferente_falha(raiz_vazia, tmp_path):
    origem = tmp_path / "o.csv"
    origem.write_text("conteúdo alterado")
    with pytest.raises(ValueError, match="SHA-256"):
        baixar(origem.as_uri(), raiz_vazia / "data/external/o.csv", sha_esperado="0" * 64)


def test_hashes_do_config_conferem_com_fixtures():
    """As fontes externas estão fixadas por commit + SHA-256 no config.yaml."""
    from eleicoes.config import config

    for info in config()["externas"].values():
        assert len(info["sha256"]) == 64
        assert "/master/" not in info["url"] and "/main/" not in info["url"], (
            "URL deve apontar para um commit"
        )
