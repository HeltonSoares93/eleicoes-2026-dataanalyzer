"""
Contrato de dados: o formato que cada base processada TEM de ter.

O processamento valida as bases antes de salvar. Se algo vier fora do
contrato (tipo errado, voto negativo, turno inválido...), o erro aparece
na hora do processamento, com a coluna e o problema, e não três células
depois no notebook.

Tipos são sempre numpy "comuns" (int32/int64, sem nulos), nunca os
inteiros anuláveis do pandas (Int32), que viram 'object' em contas.
"""

import pandera.pandas as pa
from pandera.pandas import Check, Column, DataFrameSchema

TIPOS_VOTO = ["Nominal", "Branco", "Nulo", "Anulado"]
UFS = (
    "AC AL AM AP BA CE DF ES GO MA MG MS MT PA PB PE PI PR RJ RN RO RR RS SC SE SP TO "
    "ZZ VT"  # exterior e voto em trânsito
).split()

_turno = Column("int64", Check.isin([1, 2]))
_uf = Column("category", Check.isin(UFS))
_votos = Column("int64", Check.ge(0))
_votavel = Column("int64", Check.gt(0))
_tp = Column("category", Check.isin(TIPOS_VOTO))

VOTOS_SECAO = DataFrameSchema(
    {
        "ANO_ELEICAO": Column("int64", Check.in_range(1994, 2100)),
        "NR_TURNO": _turno,
        "SG_UF": _uf,
        "CD_MUNICIPIO": Column("int64", Check.gt(0)),
        "NM_MUNICIPIO": Column("category"),
        "NR_ZONA": Column("int64", Check.ge(0)),
        "NR_SECAO": Column("int64", Check.ge(0)),
        "NR_VOTAVEL": _votavel,
        "NM_VOTAVEL": Column("category"),
        "TP_VOTO": _tp,
        "QT_VOTOS": _votos,
    },
    strict=True,
    coerce=False,
    name="votos_secao",
)

VOTOS_MUNICIPIO = DataFrameSchema(
    {
        "NR_TURNO": _turno,
        "SG_UF": _uf,
        "CD_MUNICIPIO": Column("int64", Check.gt(0)),
        "NM_MUNICIPIO": Column("category"),
        "NR_VOTAVEL": _votavel,
        "NM_VOTAVEL": Column("category"),
        "TP_VOTO": _tp,
        "QT_VOTOS": _votos,
    },
    strict=True,
    unique=["NR_TURNO", "SG_UF", "CD_MUNICIPIO", "NR_VOTAVEL"],
    name="votos_municipio",
)

COMPARECIMENTO_MUNICIPIO = DataFrameSchema(
    {
        "NR_TURNO": _turno,
        "SG_UF": _uf,
        "CD_MUNICIPIO": Column("int64", Check.gt(0)),
        "QT_APTOS": Column("int64", Check.ge(0)),
        "QT_COMPARECIMENTO": Column("int64", Check.ge(0)),
        "QT_ABSTENCOES": Column("int64", Check.ge(0)),
    },
    checks=[
        Check(
            # tolera diferenças de poucos eleitores (seções não instaladas, ajustes do TSE)
            lambda d: (
                (d["QT_COMPARECIMENTO"] + d["QT_ABSTENCOES"] - d["QT_APTOS"]).abs()
                <= (d["QT_APTOS"] * 0.001).clip(lower=5)
            ),
            element_wise=False,
            error="aptos = comparecimento + abstenções (tolerância de 0,1% ou 5 eleitores)",
            raise_warning=True,
        ),
    ],
    strict=True,
    unique=["NR_TURNO", "SG_UF", "CD_MUNICIPIO"],
    name="comparecimento_municipio",
)


def validar(df, esquema: pa.DataFrameSchema):
    """Valida e devolve o DataFrame; em caso de erro, lista todos os problemas."""
    return esquema.validate(df, lazy=True)
