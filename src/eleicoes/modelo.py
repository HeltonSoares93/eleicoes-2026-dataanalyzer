"""
Voto x perfil socioeconômico dos municípios (pergunta 2).

Dois modelos complementares, com o mesmo alvo (% dos válidos de um candidato):
1. Regressão linear ponderada (WLS): coeficientes interpretáveis, com erro-padrão
   robusto (HC3) e efeito fixo de região. Responde "mantendo o resto constante,
   quanto o voto muda quando a renda sobe 1 desvio-padrão?".
2. Gradient boosting + SHAP: captura relações não lineares e interações. A validação
   cruzada é por UF (GroupKFold): o modelo é sempre avaliado em estados que não viu no
   treino, o que evita superestimar o desempenho por vizinhança geográfica.

Lembrete: associação entre municípios não é causalidade nem descreve eleitores
individuais (falácia ecológica). Indicadores do Atlas são do Censo 2010.
"""

import numpy as np
import pandas as pd

from eleicoes.dados import ATLAS_COLUNAS

VARIAVEIS_LINEAR = {
    "LOG_RDPC": "Renda per capita (log)",
    "GINI": "Índice de Gini",
    "T_ANALF15M": "Analfabetismo 15+ (%)",
    "T_SUPER25M": "Superior completo 25+ (%)",
    "URBANIZACAO": "Urbanização (%)",
    "LOG_DENSIDADE": "Densidade 2022 (log)",
}
VARIAVEIS_GBM = {
    **{k: v for k, v in ATLAS_COLUNAS.items() if k != "RDPC"},
    "LOG_RDPC": "Renda per capita (log)",
    "URBANIZACAO": "Urbanização (%)",
    "LOG_POP_2022": "População 2022 (log)",
    "LOG_DENSIDADE": "Densidade 2022 (log)",
    "REGIAO": "Região",
}


def montar_base(mun: pd.DataFrame, socio: pd.DataFrame, alvo: str = "pct_A") -> pd.DataFrame:
    """Junta resultado municipal (saída de resultados.municipios) e indicadores."""
    b = mun[["CD_MUNICIPIO", "SG_UF", "NM_MUNICIPIO", "validos", alvo]].merge(
        socio, on="CD_MUNICIPIO", how="inner"
    )
    b["LOG_RDPC"] = np.log(b["RDPC"])
    b = b.rename(columns={alvo: "alvo"})
    faltando = b[list(VARIAVEIS_GBM)].isna().any(axis=1)
    if faltando.any():
        print(f"Aviso: {faltando.sum()} municípios sem indicadores (criados após 2010) foram excluídos.")
    return b[~faltando].reset_index(drop=True)


# ------------------------------------------------------------------ linear


def regressao_linear(base: pd.DataFrame, efeito_regiao: bool = True):
    """WLS com variáveis padronizadas: coeficiente = variação em p.p. do alvo
    para +1 desvio-padrão da variável."""
    import statsmodels.api as sm

    X = base[list(VARIAVEIS_LINEAR)]
    X = (X - X.mean()) / X.std()
    if efeito_regiao:
        X = X.join(pd.get_dummies(base["REGIAO"], prefix="reg", drop_first=True, dtype=float))
    X = sm.add_constant(X)
    res = sm.WLS(base["alvo"], X, weights=base["validos"]).fit(cov_type="HC3")
    ic = res.conf_int()
    tab = pd.DataFrame({"coef_pp": res.params, "ic_inf": ic[0], "ic_sup": ic[1], "p_valor": res.pvalues})
    tab = tab.drop(index="const")
    tab.index = [VARIAVEIS_LINEAR.get(i, i.replace("reg_", "Região: ")) for i in tab.index]
    return res, tab


def vif(base: pd.DataFrame) -> pd.Series:
    """Fator de inflação da variância (> 5 indica colinearidade forte)."""
    from statsmodels.stats.outliers_influence import variance_inflation_factor

    X = base[list(VARIAVEIS_LINEAR)]
    X = (X - X.mean()) / X.std()
    return pd.Series(
        [variance_inflation_factor(X.values, i) for i in range(X.shape[1])],
        index=[VARIAVEIS_LINEAR[c] for c in X.columns],
        name="VIF",
    )


# ------------------------------------------------------------------ gradient boosting


def _matriz(base: pd.DataFrame) -> pd.DataFrame:
    X = base[[c for c in VARIAVEIS_GBM if c != "REGIAO"]].copy()
    # região como colunas 0/1 (compatível com SHAP)
    return X.join(pd.get_dummies(base["REGIAO"], prefix="Região", prefix_sep=": ", dtype=float))


def modelo_gbm(base: pd.DataFrame, semente: int = 0, n_shap: int = 2000) -> dict:
    from sklearn.ensemble import HistGradientBoostingRegressor
    from sklearn.metrics import mean_absolute_error, r2_score
    from sklearn.model_selection import GroupKFold

    X, y, w, grupos = _matriz(base), base["alvo"].to_numpy(), base["validos"].to_numpy(), base["SG_UF"]

    def novo():
        return HistGradientBoostingRegressor(
            max_iter=400,
            learning_rate=0.05,
            max_leaf_nodes=31,
            min_samples_leaf=30,
            l2_regularization=1.0,
            random_state=semente,
        )

    oof = np.zeros(len(y))
    for tr, te in GroupKFold(n_splits=5).split(X, y, grupos):
        m = novo().fit(X.iloc[tr], y[tr])
        oof[te] = m.predict(X.iloc[te])
    metricas = {
        "r2_validacao_por_uf": r2_score(y, oof),
        "mae_pp": mean_absolute_error(y, oof),
        "mae_baseline_pp": mean_absolute_error(y, np.full_like(y, np.average(y, weights=w))),
    }
    final = novo().fit(X, y)

    import shap

    amostra = X.sample(min(n_shap, len(X)), random_state=semente)
    explicador = shap.TreeExplainer(final)
    valores = explicador(amostra)
    valores.feature_names = [VARIAVEIS_GBM.get(c, c) for c in amostra.columns]
    importancia = (
        pd.Series(np.abs(valores.values).mean(axis=0), index=amostra.columns)
        .rename(index=VARIAVEIS_GBM)
        .sort_values(ascending=False)
    )
    return {
        "modelo": final,
        "metricas": metricas,
        "oof": oof,
        "shap": valores,
        "amostra": amostra,
        "importancia_pp": importancia,
    }
