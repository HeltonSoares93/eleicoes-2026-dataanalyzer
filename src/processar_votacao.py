"""
Processa o arquivo do TSE "Presidente - Votação por seção eleitoral - 2026"
(votacao_secao_2026_BR.zip) e gera bases agregadas em parquet.

Uso:
    python src/processar_votacao.py data/raw/votacao_secao_2026_BR.zip

Saídas (em data/processed/):
    votos_secao.parquet      -> base limpa no nível de seção (só colunas úteis)
    votos_municipio.parquet  -> votos por turno x município x votável
    votos_uf.parquet         -> votos por turno x UF x votável
    resumo_brasil.csv        -> total nacional por turno e votável (conferência)

Regras do LEIAME do TSE aplicadas:
    - encoding Latin 1, separador ';', campos entre aspas
    - '#NULO' / -1 = em branco; '#NE' / -3 = não registrado -> viram NA
    - SG_UF pode ser 'ZZ' (exterior) ou 'VT' (voto em trânsito)
    - NR_VOTAVEL 95 = branco, 96 = nulo, 97 = anulado e apurado em separado
"""

import sys
import zipfile
from pathlib import Path

import pandas as pd

COLUNAS = [
    "ANO_ELEICAO", "NR_TURNO", "SG_UF", "CD_MUNICIPIO", "NM_MUNICIPIO",
    "NR_ZONA", "NR_SECAO", "CD_CARGO", "NR_VOTAVEL", "NM_VOTAVEL", "QT_VOTOS",
]

TIPOS = {
    "ANO_ELEICAO": "Int16", "NR_TURNO": "Int8", "SG_UF": "category",
    "CD_MUNICIPIO": "Int32", "NM_MUNICIPIO": "category",
    "NR_ZONA": "Int16", "NR_SECAO": "Int16", "CD_CARGO": "Int8",
    "NR_VOTAVEL": "Int32", "NM_VOTAVEL": "category", "QT_VOTOS": "Int32",
}

VALORES_NULOS = ["#NULO", "#NULO#", "#NE", "#NE#", "-1", "-3"]

TIPO_VOTO = {95: "Branco", 96: "Nulo", 97: "Anulado"}

CHUNK = 1_000_000  # linhas por bloco; reduza se faltar memória


def converter_numeros(df: pd.DataFrame) -> pd.DataFrame:
    """Converte colunas numéricas já no bloco, para economizar memória."""
    for col, tipo in TIPOS.items():
        if col in df.columns and tipo.startswith("Int"):
            df[col] = pd.to_numeric(df[col], errors="coerce").astype(tipo)
    return df


def ler_csv_do_zip(caminho_zip: Path) -> pd.DataFrame:
    """Lê os CSVs de dentro do zip em blocos, mantendo só as colunas úteis."""
    partes = []
    with zipfile.ZipFile(caminho_zip) as z:
        csvs = [n for n in z.namelist() if n.lower().endswith(".csv")]
        if not csvs:
            sys.exit(f"Nenhum CSV encontrado dentro de {caminho_zip}")
        for nome in csvs:
            print(f"Lendo {nome} ...")
            with z.open(nome) as f:
                leitor = pd.read_csv(
                    f, sep=";", encoding="latin-1", quotechar='"',
                    usecols=lambda c: c in COLUNAS,
                    dtype=str, na_values=VALORES_NULOS, keep_default_na=False,
                    chunksize=CHUNK,
                )
                for i, bloco in enumerate(leitor, 1):
                    partes.append(converter_numeros(bloco))
                    print(f"  bloco {i}: {len(bloco):,} linhas")
    df = pd.concat(partes, ignore_index=True)
    faltando = set(COLUNAS) - set(df.columns)
    if faltando:
        sys.exit(f"Colunas esperadas ausentes no arquivo: {faltando}")
    return df


def limpar(df: pd.DataFrame) -> pd.DataFrame:
    for col, tipo in TIPOS.items():
        if not tipo.startswith("Int"):
            df[col] = df[col].astype(tipo)

    # Classifica cada linha: voto nominal, branco, nulo ou anulado
    df["TP_VOTO"] = (
        df["NR_VOTAVEL"].map(TIPO_VOTO).fillna("Nominal").astype("category")
    )
    # Marca exterior e voto em trânsito para poder filtrar depois
    df["FL_EXTERIOR"] = df["SG_UF"].astype(str).eq("ZZ")
    df["FL_TRANSITO"] = df["SG_UF"].astype(str).eq("VT")
    return df


def agregar(df: pd.DataFrame, chaves: list[str]) -> pd.DataFrame:
    return (
        df.groupby(chaves, observed=True, dropna=False)["QT_VOTOS"]
        .sum()
        .reset_index()
    )


def main():
    if len(sys.argv) < 2:
        sys.exit("Informe o caminho do zip. Ex.: python src/processar_votacao.py data/raw/votacao_secao_2026_BR.zip")

    caminho_zip = Path(sys.argv[1])
    saida = Path(__file__).resolve().parents[1] / "data" / "processed"
    saida.mkdir(parents=True, exist_ok=True)

    df = limpar(ler_csv_do_zip(caminho_zip))
    print(f"\nTotal de linhas: {len(df):,}")
    print(f"Turnos no arquivo: {sorted(df['NR_TURNO'].dropna().unique().tolist())}")

    df.to_parquet(saida / "votos_secao.parquet", index=False)

    votavel = ["NR_VOTAVEL", "NM_VOTAVEL", "TP_VOTO"]
    mun = agregar(df, ["NR_TURNO", "SG_UF", "CD_MUNICIPIO", "NM_MUNICIPIO"] + votavel)
    mun.to_parquet(saida / "votos_municipio.parquet", index=False)

    uf = agregar(df, ["NR_TURNO", "SG_UF"] + votavel)
    uf.to_parquet(saida / "votos_uf.parquet", index=False)

    br = agregar(df, ["NR_TURNO"] + votavel).sort_values(
        ["NR_TURNO", "QT_VOTOS"], ascending=[True, False]
    )
    validos = br[br["TP_VOTO"] == "Nominal"].groupby("NR_TURNO")["QT_VOTOS"].transform("sum")
    br["PCT_VALIDOS"] = (br["QT_VOTOS"] / validos * 100).round(2)
    br.to_csv(saida / "resumo_brasil.csv", index=False, encoding="utf-8-sig")

    print("\nResumo nacional (confira com o resultado oficial do TSE):")
    print(br.to_string(index=False))
    print(f"\nArquivos salvos em {saida}")


if __name__ == "__main__":
    main()
