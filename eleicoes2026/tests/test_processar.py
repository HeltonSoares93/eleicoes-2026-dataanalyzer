import zipfile

import pandas as pd
import pytest
from amostra import csv_de_zip, escrever_votacao_secao, simular_secoes

from eleicoes.config import pasta_processada
from eleicoes.processar import (
    COLS_SECAO_NUM,
    COLS_SECAO_TXT,
    conferir_comparecimento,
    ler_zip_tse,
    processar_ano,
)


def test_saidas_criadas(projeto):
    pasta = pasta_processada(2026, criar=False)
    for nome in [
        "votos_secao.parquet",
        "votos_municipio.parquet",
        "votos_uf.parquet",
        "comparecimento_municipio.parquet",
        "resumo_brasil.csv",
    ]:
        assert (pasta / nome).exists(), nome


def test_tipos_definitivos_sem_inteiros_anulaveis(projeto):
    """Regressão do erro 'margem_pp has dtype object': nada de Int32/Int8 anulável."""
    for nome in ["votos_secao", "votos_municipio", "comparecimento_municipio"]:
        df = pd.read_parquet(pasta_processada(2026, criar=False) / f"{nome}.parquet")
        for col, tipo in df.dtypes.items():
            assert not isinstance(tipo, pd.api.extensions.ExtensionDtype) or isinstance(
                tipo, pd.CategoricalDtype
            ), f"{nome}.{col} tem tipo anulável {tipo}"
        assert df["QT_VOTOS" if "QT_VOTOS" in df else "QT_APTOS"].dtype == "int64"


def test_totais_preservados(projeto):
    """Soma por município == soma por seção == soma do CSV original (menos a linha #NULO)."""
    bruto = csv_de_zip(projeto / "data/raw/votacao_secao_2026_BR.zip")
    bruto = bruto[bruto["QT_VOTOS"] != "#NULO"]
    total_bruto = bruto["QT_VOTOS"].astype(int).sum()
    pasta = pasta_processada(2026, criar=False)
    assert pd.read_parquet(pasta / "votos_secao.parquet")["QT_VOTOS"].sum() == total_bruto
    assert pd.read_parquet(pasta / "votos_municipio.parquet")["QT_VOTOS"].sum() == total_bruto
    assert pd.read_parquet(pasta / "votos_uf.parquet")["QT_VOTOS"].sum() == total_bruto


def test_linha_nula_descartada_com_aviso(projeto, capsys):
    df = ler_zip_tse(projeto / "data/raw/votacao_secao_2026_BR.zip", COLS_SECAO_NUM, COLS_SECAO_TXT)
    assert "1 linhas descartadas" in capsys.readouterr().out
    assert df["QT_VOTOS"].notna().all()


def test_acentos_latin1_preservados(projeto):
    mun = pd.read_parquet(pasta_processada(2026, criar=False) / "votos_municipio.parquet")
    assert "MACEIÓ" in set(mun["NM_MUNICIPIO"].astype(str))
    assert any("ÉPSILON" in n for n in mun["NM_VOTAVEL"].astype(str))


def test_exterior_e_transito_mantidos(projeto):
    mun = pd.read_parquet(pasta_processada(2026, criar=False) / "votos_municipio.parquet")
    assert {"ZZ", "VT"} <= set(mun["SG_UF"].astype(str))


def test_tipo_de_voto(projeto):
    mun = pd.read_parquet(pasta_processada(2026, criar=False) / "votos_municipio.parquet")
    tipos = mun.drop_duplicates("NR_VOTAVEL").set_index("NR_VOTAVEL")["TP_VOTO"].astype(str)
    assert tipos[95] == "Branco" and tipos[96] == "Nulo" and tipos[97] == "Anulado"
    assert tipos[22] == "Nominal"


def test_resumo_percentuais_somam_100(projeto):
    br = pd.read_csv(pasta_processada(2026, criar=False) / "resumo_brasil.csv")
    for _, g in br.groupby("NR_TURNO"):
        assert g["PCT_VALIDOS"].sum() == pytest.approx(100, abs=0.05)
        assert g.loc[g["TP_VOTO"] != "Nominal", "PCT_VALIDOS"].isna().all()


def test_detalhe_filtra_presidente_e_soma_zonas(projeto):
    comp = pd.read_parquet(pasta_processada(2026, criar=False) / "comparecimento_municipio.parquet")
    bruto = csv_de_zip(projeto / "data/raw/detalhe_votacao_munzona_2026.zip")
    pres = bruto[bruto["CD_CARGO"] == "1"]
    assert comp["QT_APTOS"].sum() == pres["QT_APTOS"].astype(int).sum()
    assert (comp["QT_COMPARECIMENTO"] + comp["QT_ABSTENCOES"] == comp["QT_APTOS"]).all()


def test_conferencia_cruzada_votos_x_comparecimento(projeto):
    pasta = pasta_processada(2026, criar=False)
    mun = pd.read_parquet(pasta / "votos_municipio.parquet")
    comp = pd.read_parquet(pasta / "comparecimento_municipio.parquet")
    assert conferir_comparecimento(mun, comp).empty


def test_sem_detalhe_segue_sem_abstencao(raiz_vazia, capsys):
    sec = simular_secoes(2026, turnos=(1,), semente=5)
    escrever_votacao_secao(sec, raiz_vazia / "data/raw/votacao_secao_2026_BR.zip")
    r = processar_ano(2026)
    assert r["turnos"] == [1] and r["comparecimento"] is None
    assert "abstenção não será calculada" in capsys.readouterr().out


def test_erro_claro_se_zip_nao_existe(raiz_vazia):
    with pytest.raises(FileNotFoundError, match="eleicoes.baixar"):
        processar_ano(2026)


def test_erro_claro_se_zip_sem_csv(raiz_vazia):
    caminho = raiz_vazia / "data/raw/votacao_secao_2026_BR.zip"
    caminho.parent.mkdir(parents=True)
    with zipfile.ZipFile(caminho, "w") as z:
        z.writestr("README.md", "não é o arquivo do TSE")
    with pytest.raises(ValueError, match="Nenhum CSV"):
        processar_ano(2026)


def test_erro_claro_se_coluna_ausente(raiz_vazia):
    caminho = raiz_vazia / "data/raw/votacao_secao_2026_BR.zip"
    caminho.parent.mkdir(parents=True)
    with zipfile.ZipFile(caminho, "w") as z:
        z.writestr("x.csv", '"NR_TURNO";"SG_UF"\n"1";"PE"\n'.encode("latin-1"))
    with pytest.raises(ValueError, match="colunas ausentes"):
        processar_ano(2026)


def test_erro_se_ano_do_arquivo_diferente(raiz_vazia):
    sec = simular_secoes(2022, turnos=(1,), semente=3)
    escrever_votacao_secao(sec, raiz_vazia / "data/raw/votacao_secao_2026_BR.zip")
    with pytest.raises(ValueError, match="ANO_ELEICAO"):
        processar_ano(2026)
