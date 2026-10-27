"""
Processa os arquivos brutos do TSE de um ano e grava bases limpas e validadas.

Uso:
    python -m eleicoes.processar                  # ano principal do config.yaml
    python -m eleicoes.processar --ano 2022
    python -m eleicoes.processar --ano 2026 --zip caminho/para/votacao_secao_2026_BR.zip

Entradas (data/raw/):
    votacao_secao_<ano>_BR.zip        votos por seção (obrigatório)
    detalhe_votacao_munzona_<ano>.zip aptos, comparecimento e abstenção (opcional)

Saídas (data/processed/<ano>/):
    votos_secao.parquet              votos por seção (base para inferência ecológica)
    votos_municipio.parquet          votos por turno x município x votável
    votos_uf.parquet                 votos por turno x UF x votável
    comparecimento_municipio.parquet aptos, comparecimento e abstenção (se houver o arquivo)
    resumo_brasil.csv                total nacional por turno (conferência)

Regras do LEIAME do TSE: Latin 1, separador ';', aspas; '#NULO'/-1 e '#NE'/-3 = ausente;
SG_UF 'ZZ' = exterior, 'VT' = voto em trânsito; NR_VOTAVEL 95/96/97 = branco/nulo/anulado.
"""

import argparse
import zipfile
from pathlib import Path

import pandas as pd

from eleicoes.config import arquivo_tse, config, pasta_processada
from eleicoes.esquema import (
    COMPARECIMENTO_MUNICIPIO,
    VOTOS_MUNICIPIO,
    VOTOS_SECAO,
    validar,
)

CD_CARGO_PRESIDENTE = 1
VALORES_NULOS = ["#NULO", "#NULO#", "#NE", "#NE#", "-1", "-3"]
TIPO_VOTO = {95: "Branco", 96: "Nulo", 97: "Anulado"}
CHUNK = 1_000_000  # linhas por bloco; reduza se faltar memória

COLS_SECAO_NUM = [
    "ANO_ELEICAO",
    "NR_TURNO",
    "CD_MUNICIPIO",
    "NR_ZONA",
    "NR_SECAO",
    "CD_CARGO",
    "NR_VOTAVEL",
    "QT_VOTOS",
]
COLS_SECAO_TXT = ["SG_UF", "NM_MUNICIPIO", "NM_VOTAVEL"]

COLS_DETALHE_NUM = ["NR_TURNO", "CD_MUNICIPIO", "CD_CARGO", "QT_APTOS", "QT_COMPARECIMENTO", "QT_ABSTENCOES"]
COLS_DETALHE_TXT = ["SG_UF"]


# ------------------------------------------------------------------ leitura


def _csvs_no_zip(caminho: Path) -> list[str]:
    with zipfile.ZipFile(caminho) as z:
        nomes = [n for n in z.namelist() if n.lower().endswith(".csv")]
    if not nomes:
        raise ValueError(f"Nenhum CSV dentro de {caminho}. Confira se é o arquivo do TSE.")
    # Alguns zips do TSE trazem um CSV por UF E um CSV do Brasil inteiro (_BR.csv).
    # Ler todos contaria tudo em dobro: se houver o do Brasil, usa só ele.
    brasil = [n for n in nomes if n.upper().endswith("_BR.CSV")]
    return brasil or nomes


def ler_zip_tse(
    caminho: Path, numericas: list[str], textos: list[str], filtro_cargo: int | None = CD_CARGO_PRESIDENTE
) -> pd.DataFrame:
    """Lê todos os CSVs do zip em blocos, só com as colunas pedidas.

    Numéricas saem como int64 (sem nulos). Linhas com valor ausente em
    coluna numérica são descartadas e contabilizadas na tela.
    """
    usar = set(numericas) | set(textos)
    partes, descartadas = [], 0
    with zipfile.ZipFile(caminho) as z:
        for nome in _csvs_no_zip(caminho):
            print(f"Lendo {nome} ...")
            with z.open(nome) as f:
                cabecalho = pd.read_csv(f, sep=";", encoding="latin-1", nrows=0).columns
            faltando = usar - set(cabecalho)
            if faltando:
                raise ValueError(
                    f"{nome}: colunas ausentes {sorted(faltando)}.\nColunas do arquivo: {list(cabecalho)}"
                )
            with z.open(nome) as f:
                leitor = pd.read_csv(
                    f,
                    sep=";",
                    encoding="latin-1",
                    quotechar='"',
                    usecols=lambda c: c in usar,
                    dtype={c: "float64" for c in numericas} | {c: "str" for c in textos},
                    na_values=VALORES_NULOS,
                    keep_default_na=False,
                    chunksize=CHUNK,
                )
                for i, bloco in enumerate(leitor, 1):
                    if filtro_cargo is not None and "CD_CARGO" in bloco:
                        bloco = bloco[bloco["CD_CARGO"] == filtro_cargo]
                    nulos = bloco[numericas].isna().any(axis=1)
                    descartadas += int(nulos.sum())
                    bloco = bloco[~nulos].astype({c: "int64" for c in numericas})
                    partes.append(bloco)
                    print(f"  bloco {i}: {len(bloco):,} linhas")
    if descartadas:
        print(f"Aviso: {descartadas:,} linhas descartadas por valor ausente em coluna numérica.")
    if not partes:
        raise ValueError(f"Nenhuma linha de Presidente (CD_CARGO={filtro_cargo}) em {caminho}.")
    return pd.concat(partes, ignore_index=True)


# ------------------------------------------------------------------ transformação


def limpar_secao(df: pd.DataFrame) -> pd.DataFrame:
    df = df.drop(columns="CD_CARGO")
    df["TP_VOTO"] = pd.Categorical(
        df["NR_VOTAVEL"].map(TIPO_VOTO).fillna("Nominal"),
        categories=["Nominal", "Branco", "Nulo", "Anulado"],
    )
    for c in COLS_SECAO_TXT:
        df[c] = df[c].astype("category")
    ordem = [
        "ANO_ELEICAO",
        "NR_TURNO",
        "SG_UF",
        "CD_MUNICIPIO",
        "NM_MUNICIPIO",
        "NR_ZONA",
        "NR_SECAO",
        "NR_VOTAVEL",
        "NM_VOTAVEL",
        "TP_VOTO",
        "QT_VOTOS",
    ]
    return df[ordem]


def agregar(df: pd.DataFrame, chaves: list[str]) -> pd.DataFrame:
    out = df.groupby(chaves, observed=True)["QT_VOTOS"].sum().reset_index()
    out["QT_VOTOS"] = out["QT_VOTOS"].astype("int64")
    return out


def votos_municipio(secao: pd.DataFrame) -> pd.DataFrame:
    chaves = ["NR_TURNO", "SG_UF", "CD_MUNICIPIO", "NR_VOTAVEL"]
    out = agregar(secao, chaves)
    # nomes: um por código (o TSE repete o mesmo nome em todas as linhas)
    nm_mun = secao.drop_duplicates(["SG_UF", "CD_MUNICIPIO"])[["SG_UF", "CD_MUNICIPIO", "NM_MUNICIPIO"]]
    nm_vot = secao.drop_duplicates("NR_VOTAVEL")[["NR_VOTAVEL", "NM_VOTAVEL", "TP_VOTO"]]
    out = out.merge(nm_mun, on=["SG_UF", "CD_MUNICIPIO"]).merge(nm_vot, on="NR_VOTAVEL")
    for c in ["SG_UF", "NM_MUNICIPIO", "NM_VOTAVEL"]:
        out[c] = out[c].astype(str).astype("category")
    out["TP_VOTO"] = out["TP_VOTO"].astype(secao["TP_VOTO"].dtype)
    return out[
        [
            "NR_TURNO",
            "SG_UF",
            "CD_MUNICIPIO",
            "NM_MUNICIPIO",
            "NR_VOTAVEL",
            "NM_VOTAVEL",
            "TP_VOTO",
            "QT_VOTOS",
        ]
    ]


def resumo_brasil(mun: pd.DataFrame) -> pd.DataFrame:
    br = (
        mun.groupby(["NR_TURNO", "NR_VOTAVEL", "NM_VOTAVEL", "TP_VOTO"], observed=True)["QT_VOTOS"]
        .sum()
        .reset_index()
        .sort_values(["NR_TURNO", "QT_VOTOS"], ascending=[True, False])
    )
    nominal = br["TP_VOTO"] == "Nominal"
    validos = br[nominal].groupby("NR_TURNO")["QT_VOTOS"].sum()
    br["PCT_VALIDOS"] = (br["QT_VOTOS"] / br["NR_TURNO"].map(validos) * 100).where(nominal).round(2)
    return br.reset_index(drop=True)


def processar_detalhe(caminho: Path) -> pd.DataFrame:
    det = ler_zip_tse(caminho, COLS_DETALHE_NUM, COLS_DETALHE_TXT)
    out = (
        det.groupby(["NR_TURNO", "SG_UF", "CD_MUNICIPIO"])[["QT_APTOS", "QT_COMPARECIMENTO", "QT_ABSTENCOES"]]
        .sum()
        .reset_index()
    )
    out["SG_UF"] = out["SG_UF"].astype("category")
    return out.astype(
        {c: "int64" for c in ["NR_TURNO", "CD_MUNICIPIO", "QT_APTOS", "QT_COMPARECIMENTO", "QT_ABSTENCOES"]}
    )


# ------------------------------------------------------------------ orquestração


def processar_ano(ano: int, zip_secao: Path | None = None, zip_detalhe: Path | None = None) -> dict:
    zip_secao = Path(zip_secao or arquivo_tse("votacao_secao", ano))
    zip_detalhe = Path(zip_detalhe or arquivo_tse("detalhe_munzona", ano))
    if not zip_secao.exists():
        raise FileNotFoundError(
            f"Não encontrei {zip_secao}.\nRode `python -m eleicoes.baixar --ano {ano}` "
            "ou informe o caminho com --zip."
        )
    saida = pasta_processada(ano)

    secao = validar(limpar_secao(ler_zip_tse(zip_secao, COLS_SECAO_NUM, COLS_SECAO_TXT)), VOTOS_SECAO)
    anos = secao["ANO_ELEICAO"].unique().tolist()
    if anos != [ano]:
        raise ValueError(f"O arquivo {zip_secao.name} contém ANO_ELEICAO={anos}, esperado {ano}.")
    secao.to_parquet(saida / "votos_secao.parquet", index=False)

    mun = validar(votos_municipio(secao), VOTOS_MUNICIPIO)
    mun.to_parquet(saida / "votos_municipio.parquet", index=False)
    agregar(mun, ["NR_TURNO", "SG_UF", "NR_VOTAVEL", "NM_VOTAVEL", "TP_VOTO"]).to_parquet(
        saida / "votos_uf.parquet", index=False
    )
    br = resumo_brasil(mun)
    br.to_csv(saida / "resumo_brasil.csv", index=False, encoding="utf-8-sig")

    resultado = {
        "turnos": sorted(secao["NR_TURNO"].unique().tolist()),
        "linhas_secao": len(secao),
        "resumo": br,
        "comparecimento": None,
    }

    if zip_detalhe.exists():
        comp = validar(processar_detalhe(zip_detalhe), COMPARECIMENTO_MUNICIPIO)
        comp.to_parquet(saida / "comparecimento_municipio.parquet", index=False)
        resultado["comparecimento"] = comp
        conferir_comparecimento(mun, comp)
    else:
        print(f"\nAviso: {zip_detalhe.name} não encontrado; abstenção não será calculada.")
    return resultado


def conferir_comparecimento(mun: pd.DataFrame, comp: pd.DataFrame, tolerancia: float = 0.001) -> pd.DataFrame:
    """Validação cruzada entre dois arquivos independentes do TSE:
    votos totais por município (votação por seção) x comparecimento (detalhe da apuração)."""
    votos = mun.groupby(["NR_TURNO", "CD_MUNICIPIO"])["QT_VOTOS"].sum()
    compar = comp.groupby(["NR_TURNO", "CD_MUNICIPIO"])["QT_COMPARECIMENTO"].sum()
    t = pd.concat([votos, compar], axis=1).dropna()
    t["dif_rel"] = (t["QT_VOTOS"] - t["QT_COMPARECIMENTO"]).abs() / t["QT_COMPARECIMENTO"].clip(lower=1)
    ruins = t[t["dif_rel"] > tolerancia]
    total = t[["QT_VOTOS", "QT_COMPARECIMENTO"]].sum()
    print(
        f"\nConferência votos x comparecimento: {len(t):,} municípios-turno; "
        f"diferença nacional {abs(total.iloc[0] - total.iloc[1]):,} votos; "
        f"{len(ruins)} acima de {tolerancia:.1%}."
    )
    return ruins


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--ano", type=int, default=None)
    p.add_argument("--zip", type=Path, default=None, help="caminho do votacao_secao_<ano>_BR.zip")
    p.add_argument("--detalhe", type=Path, default=None, help="caminho do detalhe_votacao_munzona_<ano>.zip")
    a = p.parse_args(argv)
    ano = a.ano or int(config()["ano_principal"])

    r = processar_ano(ano, a.zip, a.detalhe)
    pd.set_option("display.width", 160)
    print(f"\nLinhas (seção): {r['linhas_secao']:,}   Turnos: {r['turnos']}")
    print("\nResumo nacional (confira com o resultado oficial do TSE):")
    print(r["resumo"].to_string(index=False))
    print(f"\nArquivos salvos em {pasta_processada(ano)}")


if __name__ == "__main__":
    main()
