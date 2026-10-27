"""Página web: dados exportados e funcionamento no navegador."""

import functools
import http.server
import json
import shutil
import threading
from pathlib import Path

import pytest

SITE_REPO = Path(__file__).resolve().parents[1] / "site"


@pytest.fixture(scope="module")
def site(projeto):
    """Exporta os dados do projeto de teste e monta a página completa ao lado deles."""
    from eleicoes.exportar_site import exportar

    destino = exportar(avancado=True, n_boot=10)
    for nome in ["index.html", "app.js", "style.css"]:
        shutil.copy(SITE_REPO / nome, destino / nome)
    shutil.copytree(SITE_REPO / "vendor", destino / "vendor", dirs_exist_ok=True)
    return destino


def _ler(site, nome):
    return json.loads((site / "data" / nome).read_text(encoding="utf-8"))


def test_arquivos_e_tamanhos(site):
    for nome, limite_kb in [
        ("meta.json", 5),
        ("resumo.json", 20),
        ("agregados.json", 50),
        ("municipios.json", 1500),
        ("malha.json", 4000),
        ("ufs.json", 400),
        ("avancado.json", 100),
    ]:
        caminho = site / "data" / nome
        assert caminho.exists(), nome
        assert caminho.stat().st_size < limite_kb * 1000, f"{nome} grande demais"


def test_meta(site):
    meta = _ler(site, "meta.json")
    assert meta["ano"] == 2026 and meta["turnos"] == [1, 2]
    assert meta["tem_abstencao"] and meta["tem_swing"] and meta["tem_avancado"]
    assert {meta["finalistas"]["A"]["nr"], meta["finalistas"]["B"]["nr"]} == {13, 22}


def test_municipios_colunas_alinhadas(site):
    m = _ler(site, "municipios.json")
    n = len(m["cd"])
    assert n == 231
    for chave in ["nome", "uf", "lat", "lon"]:
        assert len(m[chave]) == n
    for t in ("t1", "t2"):
        for campo, valores in m[t].items():
            assert len(valores) == n, (t, campo)
        validos = [(a, b) for a, b in zip(m[t]["A"], m[t]["B"], strict=True) if a is not None]
        assert all(0 <= a <= 100 and 0 <= b <= 100 for a, b in validos)
    assert "ZZ" not in m["uf"] and "VT" not in m["uf"]


def test_malha_casa_com_municipios(site):
    cds = set(_ler(site, "municipios.json")["cd"])
    feats = _ler(site, "malha.json")["features"]
    assert {f["properties"]["c"] for f in feats} == cds
    assert len(_ler(site, "ufs.json")["features"]) == 6


def test_resumo_bate_com_agregados(site):
    resumo = _ler(site, "resumo.json")
    for t, r in resumo.items():
        assert sum(c["pct"] for c in r["candidatos"]) == pytest.approx(100, abs=0.05)
        uf = _ler(site, "agregados.json")["uf"][t]
        # exterior e trânsito ficam fora das UFs, por isso <=
        assert sum(x["validos"] for x in uf) <= r["validos"]


def test_avancado(site):
    av = _ler(site, "avancado.json")
    tr = av["transferencia"]
    for linha in tr["pct"]:
        assert sum(linha) == pytest.approx(100, abs=0.5)
    assert len(av["espacial"]["lisa"]) == 231
    assert av["regressao"]["coef"] and av["gbm"]["importancia"]


@pytest.mark.lento
def test_pagina_no_navegador(site):
    sync_api = pytest.importorskip("playwright.sync_api")
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(site))
    handler.log_message = lambda *a, **k: None
    servidor = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{servidor.server_address[1]}/"
    try:
        with sync_api.sync_playwright() as pw:
            try:
                navegador = pw.chromium.launch()
            except Exception as e:  # navegador não instalado (ex.: Windows sem `playwright install`)
                pytest.skip(f"Chromium indisponível: {e}")
            pagina = navegador.new_page(viewport={"width": 1280, "height": 900})
            erros = []
            pagina.on("pageerror", lambda e: erros.append(str(e)))
            pagina.goto(url, wait_until="networkidle")
            assert pagina.locator("#mapa path.mun").count() == 231
            assert pagina.locator("#pct-a").inner_text().endswith("%")
            assert pagina.is_visible("#avancado")
            assert pagina.locator(".matriz td").count() > 0
            for metrica in ["abst", "sw13"]:
                pagina.select_option("#ctl-metrica", metrica)
            pagina.click("#ctl-turno button >> nth=0")
            pagina.select_option("#ctl-uf", "SE")
            assert pagina.locator("#mapa path.mun").count() == 75
            pagina.click("#ctl-vista button >> nth=1")
            assert pagina.locator("#mapa circle.bolha").count() > 0
            pagina.fill("#busca", "aracaju")
            assert pagina.locator("#tabela tbody tr").count() == 1
            navegador.close()
            assert not erros, erros
    finally:
        servidor.shutdown()
