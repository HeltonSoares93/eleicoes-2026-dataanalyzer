import pandas as pd
import pandera.errors
import pytest

from eleicoes.esquema import VOTOS_MUNICIPIO, validar


def _base():
    df = pd.DataFrame(
        {
            "NR_TURNO": [1, 1],
            "SG_UF": ["PE", "SP"],
            "CD_MUNICIPIO": [25313, 71072],
            "NM_MUNICIPIO": ["RECIFE", "SÃO PAULO"],
            "NR_VOTAVEL": [13, 13],
            "NM_VOTAVEL": ["X", "X"],
            "TP_VOTO": ["Nominal", "Nominal"],
            "QT_VOTOS": [10, 20],
        }
    )
    for c in ["SG_UF", "NM_MUNICIPIO", "NM_VOTAVEL", "TP_VOTO"]:
        df[c] = df[c].astype("category")
    return df.astype(
        {"NR_TURNO": "int64", "CD_MUNICIPIO": "int64", "NR_VOTAVEL": "int64", "QT_VOTOS": "int64"}
    )


def test_base_valida_passa():
    validar(_base(), VOTOS_MUNICIPIO)


def test_rejeita_inteiro_anulavel():
    df = _base().astype({"QT_VOTOS": "Int32"})
    with pytest.raises(pandera.errors.SchemaErrors):
        validar(df, VOTOS_MUNICIPIO)


def test_rejeita_voto_negativo():
    df = _base()
    df.loc[0, "QT_VOTOS"] = -1
    with pytest.raises(pandera.errors.SchemaErrors):
        validar(df, VOTOS_MUNICIPIO)


def test_rejeita_turno_invalido():
    df = _base()
    df.loc[0, "NR_TURNO"] = 3
    with pytest.raises(pandera.errors.SchemaErrors):
        validar(df, VOTOS_MUNICIPIO)


def test_rejeita_duplicata():
    df = pd.concat([_base(), _base()], ignore_index=True)
    with pytest.raises(pandera.errors.SchemaErrors):
        validar(df, VOTOS_MUNICIPIO)


def test_rejeita_coluna_extra():
    df = _base().assign(EXTRA=1)
    with pytest.raises(pandera.errors.SchemaErrors):
        validar(df, VOTOS_MUNICIPIO)
