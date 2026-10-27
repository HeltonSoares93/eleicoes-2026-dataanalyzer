"""Leitura das bases processadas e das fontes externas (malha, IBGE, Atlas)."""

from functools import lru_cache

import numpy as np
import pandas as pd

from eleicoes.config import arquivo_externo, dir_external, pasta_processada
from eleicoes.esquema import COMPARECIMENTO_MUNICIPIO, VOTOS_MUNICIPIO, validar

REGIOES = {
    "AC": "Norte",
    "AP": "Norte",
    "AM": "Norte",
    "PA": "Norte",
    "RO": "Norte",
    "RR": "Norte",
    "TO": "Norte",
    "AL": "Nordeste",
    "BA": "Nordeste",
    "CE": "Nordeste",
    "MA": "Nordeste",
    "PB": "Nordeste",
    "PE": "Nordeste",
    "PI": "Nordeste",
    "RN": "Nordeste",
    "SE": "Nordeste",
    "DF": "Centro-Oeste",
    "GO": "Centro-Oeste",
    "MT": "Centro-Oeste",
    "MS": "Centro-Oeste",
    "ES": "Sudeste",
    "MG": "Sudeste",
    "RJ": "Sudeste",
    "SP": "Sudeste",
    "PR": "Sul",
    "RS": "Sul",
    "SC": "Sul",
    "ZZ": "Exterior",
    "VT": "Em trânsito",
}
ORDEM_REGIOES = ["Norte", "Nordeste", "Centro-Oeste", "Sudeste", "Sul", "Exterior", "Em trânsito"]
FORA_DO_MAPA = ["ZZ", "VT"]


class DadosAusentes(FileNotFoundError):
    """Base processada ou fonte externa ainda não disponível."""


def _exigir(caminho, dica):
    if not caminho.exists():
        raise DadosAusentes(f"Arquivo não encontrado: {caminho}\n{dica}")
    return caminho


def carregar_votos(ano: int) -> pd.DataFrame:
    """Votos por município (validados). Texto vira str e ganha a coluna REGIAO."""
    arq = _exigir(
        pasta_processada(ano, criar=False) / "votos_municipio.parquet",
        f"Rode: python -m eleicoes.processar --ano {ano}",
    )
    df = validar(pd.read_parquet(arq), VOTOS_MUNICIPIO)
    for c in ["SG_UF", "NM_MUNICIPIO", "NM_VOTAVEL", "TP_VOTO"]:
        df[c] = df[c].astype(str)
    df["REGIAO"] = df["SG_UF"].map(REGIOES).fillna("Outros")
    return df


def carregar_secao(ano: int, colunas: list[str] | None = None) -> pd.DataFrame:
    arq = _exigir(
        pasta_processada(ano, criar=False) / "votos_secao.parquet",
        f"Rode: python -m eleicoes.processar --ano {ano}",
    )
    return pd.read_parquet(arq, columns=colunas)


def carregar_comparecimento(ano: int) -> pd.DataFrame | None:
    """Aptos, comparecimento e abstenção por município; None se o arquivo não foi processado."""
    arq = pasta_processada(ano, criar=False) / "comparecimento_municipio.parquet"
    if not arq.exists():
        return None
    df = validar(pd.read_parquet(arq), COMPARECIMENTO_MUNICIPIO)
    df["SG_UF"] = df["SG_UF"].astype(str)
    df["REGIAO"] = df["SG_UF"].map(REGIOES).fillna("Outros")
    return df


def disponivel(ano: int) -> bool:
    return (pasta_processada(ano, criar=False) / "votos_municipio.parquet").exists()


# ------------------------------------------------------------------ fontes externas

_DICA_EXT = "Rode: python -m eleicoes.baixar  (baixa as fontes externas para data/external/)"


def depara_tse_ibge() -> pd.DataFrame:
    return _depara(_exigir(arquivo_externo("depara_tse_ibge"), _DICA_EXT)).copy()


@lru_cache
def _depara(arq) -> pd.DataFrame:
    d = pd.read_csv(arq, usecols=["codigo_tse", "codigo_ibge"])
    return d.rename(columns={"codigo_tse": "CD_MUNICIPIO", "codigo_ibge": "CD_IBGE"}).astype("int64")


def municipios_ibge() -> pd.DataFrame:
    """Um registro por município: códigos TSE/IBGE, região, população 2022, área, lat/lon."""
    arq = _exigir(arquivo_externo("municipios_censo2022"), _DICA_EXT)
    return _municipios(arq).merge(depara_tse_ibge(), on="CD_IBGE", how="left")


@lru_cache
def _municipios(arq) -> pd.DataFrame:
    m = pd.read_csv(
        arq,
        usecols=[
            "ibge_code",
            "name",
            "uf",
            "region",
            "latitude",
            "longitude",
            "population_2022",
            "area_km2",
            "density_2022",
            "is_capital",
        ],
    )
    m = m.rename(
        columns={
            "ibge_code": "CD_IBGE",
            "name": "NOME",
            "uf": "UF",
            "region": "REGIAO",
            "population_2022": "POP_2022",
            "area_km2": "AREA_KM2",
            "density_2022": "DENSIDADE_2022",
            "is_capital": "CAPITAL",
            "latitude": "LAT",
            "longitude": "LON",
        }
    )
    return m


ATLAS_COLUNAS = {
    "IDHM": "IDHM (2010)",
    "IDHM_E": "IDHM Educação",
    "IDHM_L": "IDHM Longevidade",
    "IDHM_R": "IDHM Renda",
    "RDPC": "Renda per capita (R$ de 2010)",
    "GINI": "Índice de Gini",
    "T_ANALF15M": "Analfabetismo 15+ (%)",
    "T_SUPER25M": "Superior completo 25+ (%)",
    "T_DES18M": "Desocupação 18+ (%)",
    "PMPOB": "Pobres (%)",
    "ESPVIDA": "Esperança de vida (anos)",
}


def atlas_idhm(ano_censo: int = 2010) -> pd.DataFrame:
    """Indicadores do Atlas do Desenvolvimento Humano por município (Censo 2010)."""
    return _atlas(_exigir(arquivo_externo("atlas_idhm"), _DICA_EXT), ano_censo).copy()


@lru_cache
def _atlas(arq, ano_censo: int) -> pd.DataFrame:
    usar = ["ANO", "Codmun7", "pesotot", "pesourb", *ATLAS_COLUNAS]
    a = pd.read_csv(arq, sep=";", decimal=",", usecols=usar)
    a = a[a["ANO"] == ano_censo].drop(columns="ANO")
    a["URBANIZACAO"] = a["pesourb"] / a["pesotot"] * 100
    return a.drop(columns=["pesotot", "pesourb"]).rename(columns={"Codmun7": "CD_IBGE"})


def base_socioeconomica() -> pd.DataFrame:
    """Atlas 2010 + Censo 2022, indexado pelo código TSE do município."""
    m = municipios_ibge()
    a = atlas_idhm()
    s = m.merge(a, on="CD_IBGE", how="left")
    s["LOG_POP_2022"] = np.log10(s["POP_2022"].clip(lower=1))
    s["LOG_DENSIDADE"] = np.log10(s["DENSIDADE_2022"].clip(lower=0.01))
    return s


def carregar_malha():
    """Malha municipal com CD_MUNICIPIO (código TSE), contornos simplificados."""
    simplificada = dir_external() / "malha_municipios_simplificada_v2.gpkg"
    return _malha(simplificada).merge(depara_tse_ibge(), on="CD_IBGE", how="left")


@lru_cache
def _malha(simplificada):
    import geopandas as gpd

    if not simplificada.exists():
        bruta = gpd.read_file(_exigir(arquivo_externo("malha_municipios"), _DICA_EXT))
        bruta = bruta[["id", "geometry"]].rename(columns={"id": "CD_IBGE"})
        bruta["CD_IBGE"] = bruta["CD_IBGE"].astype("int64")
        simples = bruta.geometry.simplify(0.01, preserve_topology=True)
        # a simplificação pode gerar polígonos inválidos (autointerseção); corrige e
        # mantém só a parte poligonal, senão a união por UF falha nos mapas
        bruta["geometry"] = simples.make_valid().buffer(0)
        bruta.to_file(simplificada, driver="GPKG")
    malha = gpd.read_file(simplificada)
    malha["CD_IBGE"] = malha["CD_IBGE"].astype("int64")
    return malha
