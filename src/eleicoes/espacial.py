"""
Autocorrelação espacial: o voto forma "manchas" geográficas de verdade?

- Moran's I global: um número entre −1 e 1. Perto de 0 = distribuição aleatória;
  positivo = municípios vizinhos votam parecido. O p-valor vem de permutações.
- LISA (Moran local): classifica cada município em
    Alto-Alto  (forte para A, cercado de vizinhos fortes para A)
    Baixo-Baixo(forte para B, cercado de vizinhos fortes para B)
    Alto-Baixo / Baixo-Alto (exceções: destoa dos vizinhos)
    Não significativo
Vizinhança: municípios que compartilham fronteira (contiguidade "Queen"); municípios
sem vizinho (ilhas) recebem o vizinho mais próximo.
"""

import warnings

import numpy as np
import pandas as pd

ROTULOS_LISA = {1: "Alto-Alto", 2: "Baixo-Alto", 3: "Baixo-Baixo", 4: "Alto-Baixo"}


def pesos(gdf):
    from libpysal.weights import KNN, Queen, attach_islands

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        w = Queen.from_dataframe(gdf, use_index=False)
        if w.islands:
            w = attach_islands(w, KNN.from_dataframe(gdf, k=1))
    w.transform = "r"
    return w


def moran(gdf, coluna: str, permutacoes: int = 999, semente: int = 0) -> dict:
    """Moran's I global da coluna (municípios sem valor são descartados)."""
    from esda.moran import Moran

    g = gdf.dropna(subset=[coluna]).reset_index(drop=True)
    np.random.seed(semente)  # noqa: NPY002 - esda usa o gerador global nas permutações
    m = Moran(g[coluna].to_numpy(), pesos(g), permutations=permutacoes)
    return {"I": float(m.I), "p_valor": float(m.p_sim), "esperado": float(m.EI), "n": len(g)}


def lisa(gdf, coluna: str, alfa: float = 0.05, permutacoes: int = 999, semente: int = 0):
    """Devolve o GeoDataFrame com a coluna 'lisa' (categoria do cluster)."""
    from esda.moran import Moran_Local

    g = gdf.dropna(subset=[coluna]).reset_index(drop=True)
    np.random.seed(semente)  # noqa: NPY002 - esda usa o gerador global nas permutações
    ml = Moran_Local(g[coluna].to_numpy(), pesos(g), permutations=permutacoes, seed=semente)
    rotulo = pd.Series(ml.q).map(ROTULOS_LISA)
    rotulo[ml.p_sim >= alfa] = "Não significativo"
    g["lisa"] = pd.Categorical(
        rotulo, categories=["Alto-Alto", "Baixo-Baixo", "Alto-Baixo", "Baixo-Alto", "Não significativo"]
    )
    g["lisa_p"] = ml.p_sim
    return g
