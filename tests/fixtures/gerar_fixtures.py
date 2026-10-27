"""
Gera os recortes das fontes externas usados nos testes (6 UFs pequenas).

Rode uma vez, a partir dos arquivos completos baixados por `python -m eleicoes.baixar`:
    python tests/fixtures/gerar_fixtures.py data/external
Os recortes ficam versionados em tests/fixtures/external/ (poucas centenas de KB).
"""

import json
import sys
from pathlib import Path

import pandas as pd

UFS = {"AC": 12, "AP": 16, "RR": 14, "SE": 28, "AL": 27, "DF": 53}
origem = Path(sys.argv[1])
destino = Path(__file__).parent / "external"
destino.mkdir(exist_ok=True)
codigos_uf = set(UFS.values())

dep = pd.read_csv(origem / "municipios_tse_ibge.csv")
dep = dep[dep["uf"].isin(UFS)]
dep.to_csv(destino / "municipios_tse_ibge.csv", index=False)
ibge = set(dep["codigo_ibge"])

cen = pd.read_csv(origem / "municipios_censo2022.csv", dtype=str)
cen[cen["ibge_code"].astype(int).isin(ibge)].to_csv(destino / "municipios_censo2022.csv", index=False)

with open(origem / "atlas_idhm_municipal.csv", encoding="utf-8") as f:
    linhas = f.readlines()
cab = linhas[0].split(";")
i_cod = cab.index('"Codmun7"')
i_ano = cab.index('"ANO"')
sel = [linhas[0]] + [
    linha
    for linha in linhas[1:]
    if linha.split(";")[i_ano] == "2010" and int(linha.split(";")[i_cod]) in ibge
]
(destino / "atlas_idhm_municipal.csv").write_text("".join(sel), encoding="utf-8")

import geopandas as gpd  # noqa: E402

g = gpd.read_file(origem / "geojs-100-mun.json")
g = g[g["id"].astype(int).isin(ibge)].copy()
g["geometry"] = g.geometry.simplify(0.01, preserve_topology=True)
gj = json.loads(g[["id", "name", "geometry"]].to_json())
(destino / "geojs-100-mun.json").write_text(json.dumps(gj), encoding="utf-8")
print(len(dep), "municípios;", {p.name: p.stat().st_size for p in destino.iterdir()})
