import numpy as np
import pandas as pd
import pytest
from amostra import VERDADE_P

from eleicoes import resultados as r
from eleicoes import transferencia as tr
from eleicoes.dados import carregar_secao, carregar_votos


def test_resolver_respeita_restricoes():
    rng = np.random.default_rng(0)
    x = rng.dirichlet(np.ones(4), 500)
    y = rng.dirichlet(np.ones(3), 500)
    P = tr.resolver(x.T @ x, x.T @ y)
    assert (P >= 0).all()
    np.testing.assert_allclose(P.sum(axis=1), 1, atol=1e-8)


def test_recupera_matriz_conhecida():
    rng = np.random.default_rng(1)
    P = np.array([[0.9, 0.05, 0.05], [0.1, 0.85, 0.05], [0.5, 0.3, 0.2], [0.3, 0.3, 0.4]])
    idx, X, Y = [], [], []
    for uf in ["PE", "SP", "RS"]:
        for m in range(150):
            base = rng.dirichlet([4, 4, 1, 1])
            for s in range(15):
                c1 = rng.multinomial(int(rng.integers(150, 400)), rng.dirichlet(base * 50))
                c2 = sum(rng.multinomial(c1[k], P[k]) for k in range(4))
                idx.append((uf, m, 1, s))
                X.append(c1)
                Y.append(c2)
    mi = pd.MultiIndex.from_tuples(idx, names=tr.CHAVE_SECAO)
    t = tr.estimar(
        pd.DataFrame(X, index=mi, columns=list("ABCD")).astype(float),
        pd.DataFrame(Y, index=mi, columns=list("ABZ")).astype(float),
        n_boot=50,
    )
    np.testing.assert_allclose(t.matriz.to_numpy() / 100, P, atol=0.02)
    assert ((t.ic_inf.to_numpy() / 100 <= P + 0.01) & (P - 0.01 <= t.ic_sup.to_numpy() / 100)).all()


@pytest.mark.lento
def test_pipeline_recupera_verdade_da_amostra(projeto):
    votos = carregar_votos(2026)
    fin = r.finalistas(votos)
    menores = [70, 14, 55, 30]
    X, Y = tr.preparar(carregar_secao(2026), fin, menores)
    t = tr.estimar(X, Y, n_boot=30)
    rot = fin["rotulos"]
    linhas = [rot[22], rot[13], *[rot[n] for n in menores], tr.BRANCO_NULO]
    colunas = [rot[22], rot[13], tr.BRANCO_NULO]
    est = t.matriz.loc[linhas, colunas].to_numpy() / 100
    np.testing.assert_allclose(est, VERDADE_P, atol=0.08)
    assert t.erro_ajuste < 5
    assert set(tr.tabela(t).columns) == {"1º turno", "2º turno", "pct", "ic_inf", "ic_sup", "votos"}
