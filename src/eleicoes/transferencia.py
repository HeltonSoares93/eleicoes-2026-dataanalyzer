"""
Inferência ecológica: para onde foram os votos do 1º para o 2º turno?

Unidade: seção eleitoral (~470 mil), muito mais homogênea que o município.

Modelo (regressão ecológica restrita, na linha de Goodman):
    para cada seção i,  y_i ≈ x_i · P
    x_i = proporções do 1º turno (A, B, demais candidatos, branco/nulo)
    y_i = proporções do 2º turno (A, B, branco/nulo)
    P   = matriz de transferência; P[k, j] = fração de quem votou em k no 1º turno
          que foi para j no 2º. Restrições: P ≥ 0 e cada linha soma 1.

P é estimada separadamente em cada UF (o comportamento pode variar entre estados)
e depois combinada em uma matriz nacional ponderada pelos votos. A incerteza vem de
um bootstrap por município (reamostra municípios inteiros dentro de cada UF).

LIMITAÇÕES (importante ao comunicar resultados):
- É inferência sobre agregados: estima padrões médios, não o voto de cada pessoa.
- Supõe P parecida entre seções de uma mesma UF.
- O arquivo de votação por seção não tem eleitores aptos, então quem deixou de votar
  (ou passou a votar) entre os turnos não é modelado explicitamente; as proporções
  são calculadas sobre quem votou em cada turno.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from eleicoes.dados import FORA_DO_MAPA

BRANCO_NULO = "Branco/Nulo"
OUTROS = "Outros"
CHAVE_SECAO = ["SG_UF", "CD_MUNICIPIO", "NR_ZONA", "NR_SECAO"]


@dataclass
class Transferencia:
    matriz: pd.DataFrame  # % (linhas: 1º turno, colunas: 2º turno), nacional
    ic_inf: pd.DataFrame  # limite inferior do IC 95% (bootstrap)
    ic_sup: pd.DataFrame  # limite superior
    fluxos: pd.DataFrame  # votos estimados (linhas x colunas), nacional
    por_uf: dict  # UF -> matriz P (fração) daquela UF
    n_secoes: int
    erro_ajuste: float  # erro médio absoluto (p.p.) da previsão do 2º turno por seção


# ------------------------------------------------------------------ preparação


def _categoria(nr: pd.Series, tp: pd.Series, mapa: dict) -> pd.Series:
    cat = nr.map(mapa).astype(object)
    cat[tp != "Nominal"] = BRANCO_NULO
    return cat.fillna(OUTROS)


def preparar(secao: pd.DataFrame, fin: dict, menores: list[int]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Matrizes por seção: contagens do 1º turno (X) e do 2º (Y), mesmas seções nas duas."""
    s = secao[~secao["SG_UF"].astype(str).isin(FORA_DO_MAPA)]
    rot = {nr: fin["rotulos"][nr] for nr in [fin["A"], fin["B"], *menores]}

    def largo(turno, colunas):
        d = s[s["NR_TURNO"] == turno]
        cat = _categoria(d["NR_VOTAVEL"], d["TP_VOTO"].astype(str), rot)
        w = (
            d.assign(cat=cat.to_numpy(), SG_UF=d["SG_UF"].astype(str))
            .groupby(CHAVE_SECAO + ["cat"])["QT_VOTOS"]
            .sum()
            .unstack("cat", fill_value=0)
        )
        return w.reindex(columns=colunas, fill_value=0)

    cols_x = list(rot.values()) + [OUTROS, BRANCO_NULO]
    cols_y = [rot[fin["A"]], rot[fin["B"]], BRANCO_NULO]
    X, Y = largo(1, cols_x), largo(2, cols_y)
    comum = X.index.intersection(Y.index)
    X, Y = X.loc[comum], Y.loc[comum]
    if X[OUTROS].sum() == 0:
        X = X.drop(columns=OUTROS)
    vivos = (X.sum(axis=1) > 0) & (Y.sum(axis=1) > 0)
    return X[vivos].astype("float64"), Y[vivos].astype("float64")


# ------------------------------------------------------------------ estimação


def _momentos(Xc: np.ndarray, Yc: np.ndarray):
    """G = Xᵀ W X e H = Xᵀ W Y com x, y em proporções e peso = votos do 1º turno."""
    n1 = Xc.sum(axis=1, keepdims=True)
    x, y = Xc / n1, Yc / Yc.sum(axis=1, keepdims=True)
    w = n1
    return (x * w).T @ x, (x * w).T @ y


def resolver(G: np.ndarray, H: np.ndarray) -> np.ndarray:
    """min tr(PᵀGP) − 2tr(PᵀH)  s.a. P ≥ 0, linhas somam 1."""
    K, J = H.shape
    escala = np.trace(G) / K or 1.0
    Gs, Hs = G / escala, H / escala

    def f(p):
        P = p.reshape(K, J)
        GP = Gs @ P
        return float(np.sum(P * GP) - 2 * np.sum(P * Hs)), (2 * (GP - Hs)).ravel()

    cons = [
        {
            "type": "eq",
            "fun": lambda p, k=k: p.reshape(K, J)[k].sum() - 1,
            "jac": lambda p, k=k: np.eye(K)[k].repeat(J) * 1.0,
        }
        for k in range(K)
    ]
    p0 = np.full(K * J, 1.0 / J)
    r = minimize(
        f,
        p0,
        jac=True,
        method="SLSQP",
        bounds=[(0, 1)] * (K * J),
        constraints=cons,
        options={"maxiter": 500, "ftol": 1e-12},
    )
    P = np.clip(r.x.reshape(K, J), 0, 1)
    return P / P.sum(axis=1, keepdims=True)


def estimar(X: pd.DataFrame, Y: pd.DataFrame, n_boot: int = 200, semente: int = 0) -> Transferencia:
    ufs = X.index.get_level_values("SG_UF")
    mun = X.index.get_level_values("CD_MUNICIPIO")
    rng = np.random.default_rng(semente)
    cols_x, cols_y = list(X.columns), list(Y.columns)

    por_uf, fluxo_total = {}, np.zeros((len(cols_x), len(cols_y)))
    boot_fluxos = np.zeros((n_boot, len(cols_x), len(cols_y)))
    for uf in sorted(set(ufs)):
        sel = ufs == uf
        Xu, Yu, mu = X.to_numpy()[sel], Y.to_numpy()[sel], mun[sel]
        # momentos por município: o bootstrap só soma, sem refazer contas por seção
        codigos, inv = np.unique(mu, return_inverse=True)
        n1 = Xu.sum(axis=1, keepdims=True)
        x, y = Xu / n1, Yu / Yu.sum(axis=1, keepdims=True)
        xw = x * n1
        Gm = np.zeros((len(codigos), x.shape[1], x.shape[1]))
        Hm = np.zeros((len(codigos), x.shape[1], y.shape[1]))
        np.add.at(Gm, inv, xw[:, :, None] * x[:, None, :])
        np.add.at(Hm, inv, xw[:, :, None] * y[:, None, :])

        P = resolver(Gm.sum(0), Hm.sum(0))
        por_uf[uf] = pd.DataFrame(P, index=cols_x, columns=cols_y)
        votos_x = Xu.sum(axis=0)
        fluxo_total += votos_x[:, None] * P

        for b in range(n_boot):
            amostra = rng.integers(0, len(codigos), len(codigos))
            Pb = resolver(Gm[amostra].sum(0), Hm[amostra].sum(0))
            boot_fluxos[b] += votos_x[:, None] * Pb

    def pct(fl):
        return fl / fl.sum(axis=-1, keepdims=True) * 100

    matriz = pd.DataFrame(pct(fluxo_total), index=cols_x, columns=cols_y)
    bp = pct(boot_fluxos)
    ic_inf = pd.DataFrame(np.percentile(bp, 2.5, axis=0), index=cols_x, columns=cols_y)
    ic_sup = pd.DataFrame(np.percentile(bp, 97.5, axis=0), index=cols_x, columns=cols_y)

    # qualidade do ajuste: previsão do 2º turno por seção com a P da UF
    prev = np.vstack(
        [
            X.to_numpy()[ufs == uf] / X.to_numpy()[ufs == uf].sum(1, keepdims=True) @ por_uf[uf].to_numpy()
            for uf in sorted(set(ufs))
        ]
    )
    obs = np.vstack(
        [Y.to_numpy()[ufs == uf] / Y.to_numpy()[ufs == uf].sum(1, keepdims=True) for uf in sorted(set(ufs))]
    )
    erro = float(np.abs(prev - obs).mean() * 100)

    return Transferencia(
        matriz=matriz,
        ic_inf=ic_inf,
        ic_sup=ic_sup,
        fluxos=pd.DataFrame(fluxo_total, index=cols_x, columns=cols_y).round(),
        por_uf=por_uf,
        n_secoes=len(X),
        erro_ajuste=erro,
    )


def tabela(t: Transferencia) -> pd.DataFrame:
    """Matriz em formato longo, com IC 95%, pronta para exibir."""
    m = t.matriz.stack().rename("pct")
    out = pd.concat(
        [
            m,
            t.ic_inf.stack().rename("ic_inf"),
            t.ic_sup.stack().rename("ic_sup"),
            t.fluxos.stack().rename("votos"),
        ],
        axis=1,
    )
    out.index.names = ["1º turno", "2º turno"]
    return out.reset_index()
