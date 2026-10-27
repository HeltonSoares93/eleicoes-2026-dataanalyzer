"""
Gera arquivos sintéticos NO FORMATO EXATO do TSE (Latin 1, ';', aspas, #NULO...)
para os municípios reais dos recortes em tests/fixtures/external.

Os votos são simulados com estrutura conhecida, para que os testes possam
verificar se as análises recuperam o que foi plantado:
- % do candidato A cresce com o IDHM (relação socioeconômica);
- a transferência do 1º para o 2º turno segue a matriz VERDADE_P.
"""

import io
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

FIXTURES = Path(__file__).parent / "fixtures" / "external"

CANDIDATOS_T1 = [  # (número, nome) — nomes fictícios
    (22, "CANDIDATO ALFA DE SOUZA"),
    (13, "CANDIDATA BETA DA SILVA"),
    (70, "CANDIDATO GAMA FERREIRA"),
    (14, "CANDIDATA DELTA COSTA"),
    (55, "CANDIDATO ÉPSILON ARAÚJO"),
    (30, "CANDIDATO ZETA REIS"),
]
NOMES = dict(CANDIDATOS_T1) | {95: "VOTO BRANCO", 96: "VOTO NULO", 97: "VOTO ANULADO E APURADO EM SEPARADO"}

# Linhas: 22, 13, 70, 14, 55, 30, branco/nulo.  Colunas: 22, 13, branco/nulo.
VERDADE_P = np.array(
    [
        [0.96, 0.02, 0.02],
        [0.03, 0.95, 0.02],
        [0.55, 0.25, 0.20],
        [0.70, 0.15, 0.15],
        [0.60, 0.20, 0.20],
        [0.50, 0.30, 0.20],
        [0.30, 0.25, 0.45],
    ]
)

COLUNAS_SECAO = [
    "DT_GERACAO",
    "HH_GERACAO",
    "ANO_ELEICAO",
    "CD_TIPO_ELEICAO",
    "NM_TIPO_ELEICAO",
    "NR_TURNO",
    "CD_ELEICAO",
    "DS_ELEICAO",
    "DT_ELEICAO",
    "TP_ABRANGENCIA",
    "SG_UF",
    "SG_UE",
    "NM_UE",
    "CD_MUNICIPIO",
    "NM_MUNICIPIO",
    "NR_ZONA",
    "NR_SECAO",
    "CD_CARGO",
    "DS_CARGO",
    "NR_VOTAVEL",
    "NM_VOTAVEL",
    "QT_VOTOS",
    "NR_LOCAL_VOTACAO",
    "SQ_CANDIDATO",
    "NM_LOCAL_VOTACAO",
    "DS_LOCAL_VOTACAO_ENDERECO",
]
COLUNAS_DETALHE = [
    "DT_GERACAO",
    "HH_GERACAO",
    "ANO_ELEICAO",
    "CD_TIPO_ELEICAO",
    "NM_TIPO_ELEICAO",
    "NR_TURNO",
    "CD_ELEICAO",
    "DS_ELEICAO",
    "DT_ELEICAO",
    "TP_ABRANGENCIA",
    "SG_UF",
    "SG_UE",
    "NM_UE",
    "CD_MUNICIPIO",
    "NM_MUNICIPIO",
    "NR_ZONA",
    "CD_CARGO",
    "DS_CARGO",
    "QT_APTOS",
    "QT_SECOES_PRINCIPAIS",
    "QT_SECOES_AGREGADAS",
    "QT_SECOES_NAO_INSTALADAS",
    "QT_TOTAL_SECOES",
    "QT_COMPARECIMENTO",
    "QT_ELEITORES_SECAO_NAO_INSTALADA",
    "QT_ABSTENCOES",
    "ST_VOTO_EM_TRANSITO",
    "QT_VOTOS",
    "QT_VOTOS_CONCORRENTES",
    "QT_TOTAL_VOTOS_VALIDOS",
    "QT_VOTOS_BRANCOS",
    "QT_TOTAL_VOTOS_NULOS",
    "QT_VOTOS_NULOS",
    "QT_VOTOS_ANULADOS_APU_SEP",
]


def municipios() -> pd.DataFrame:
    dep = pd.read_csv(FIXTURES / "municipios_tse_ibge.csv")
    cen = pd.read_csv(FIXTURES / "municipios_censo2022.csv", usecols=["ibge_code", "population_2022"])
    atl = pd.read_csv(
        FIXTURES / "atlas_idhm_municipal.csv", sep=";", decimal=",", usecols=["Codmun7", "IDHM"]
    )
    m = dep.merge(cen, left_on="codigo_ibge", right_on="ibge_code").merge(
        atl, left_on="codigo_ibge", right_on="Codmun7"
    )
    return m.rename(columns={"codigo_tse": "CD_MUNICIPIO", "uf": "SG_UF", "nome_municipio": "NM_MUNICIPIO"})


def _csv_tse(linhas: list[list], colunas: list[str]) -> bytes:
    txt = "\n".join(";".join(f'"{v}"' for v in linha) for linha in [colunas, *linhas])
    return txt.encode("latin-1")


def simular_secoes(ano: int, turnos=(1, 2), semente: int = 0, efeito_uf: dict | None = None) -> pd.DataFrame:
    """Contagens por seção (formato longo) para os turnos pedidos."""
    rng = np.random.default_rng(semente)
    efeito_uf = efeito_uf or {"AC": 0.8, "RR": 1.0, "AP": -0.2, "SE": -0.6, "AL": -0.4, "DF": 0.3}
    linhas = []
    for _, m in municipios().iterrows():
        n_secoes = int(np.clip(m["population_2022"] / 4000, 3, 40))
        idh = (m["IDHM"] - 0.65) / 0.06
        logit_a = 0.9 * idh + efeito_uf[m["SG_UF"]] + rng.normal(0, 0.25)
        pa = 1 / (1 + np.exp(-logit_a))
        menores = rng.dirichlet([3, 2, 2, 0.5]) * rng.uniform(0.05, 0.16)
        bn = rng.uniform(0.03, 0.07)
        base = np.array([pa, 1 - pa]) * (1 - menores.sum() - bn)
        shares = np.concatenate([base, menores, [bn]])
        for s in range(1, n_secoes + 1):
            zona = 1 + (s % 2)
            x = rng.dirichlet(shares * 150)
            n = int(rng.integers(180, 420))
            c1 = rng.multinomial(n, x)
            c2 = np.zeros(3, dtype=int)
            for k in range(7):
                c2 += rng.multinomial(c1[k], VERDADE_P[k])
            chave = (m["SG_UF"], m["CD_MUNICIPIO"], m["NM_MUNICIPIO"], zona, s)
            if 1 in turnos:
                bn1 = rng.multinomial(c1[6], [0.4, 0.55, 0.05])
                for (nr, _), v in zip(CANDIDATOS_T1, c1[:6], strict=True):
                    linhas.append((1, *chave, nr, int(v)))
                for nr, v in zip((95, 96, 97), bn1, strict=True):
                    linhas.append((1, *chave, nr, int(v)))
            if 2 in turnos:
                bn2 = rng.multinomial(c2[2], [0.45, 0.55])
                linhas.append((2, *chave, 22, int(c2[0])))
                linhas.append((2, *chave, 13, int(c2[1])))
                linhas.append((2, *chave, 95, int(bn2[0])))
                linhas.append((2, *chave, 96, int(bn2[1])))
    df = pd.DataFrame(
        linhas,
        columns=[
            "NR_TURNO",
            "SG_UF",
            "CD_MUNICIPIO",
            "NM_MUNICIPIO",
            "NR_ZONA",
            "NR_SECAO",
            "NR_VOTAVEL",
            "QT_VOTOS",
        ],
    )
    df["ANO_ELEICAO"] = ano
    # exterior e voto em trânsito
    extra = []
    for t in turnos:
        cands = [22, 13] if t == 2 else [22, 13, 70]
        for nr in cands:
            extra.append((t, "ZZ", 29297, "LISBOA", 1, 1, nr, int(rng.integers(50, 200)), ano))
            extra.append((t, "VT", 27855, "MACEIÓ", 1, 900, nr, int(rng.integers(5, 30)), ano))
    return pd.concat([df, pd.DataFrame(extra, columns=df.columns)], ignore_index=True)


def escrever_votacao_secao(secoes: pd.DataFrame, destino: Path, linha_nula: bool = True) -> Path:
    ano = int(secoes["ANO_ELEICAO"].iloc[0])
    linhas = []
    for r in secoes.itertuples(index=False):
        sq = "#NULO" if r.NR_VOTAVEL >= 95 else f"28000{r.NR_VOTAVEL}"
        linhas.append(
            [
                "26/10/2026",
                "10:00:00",
                ano,
                2,
                "ELEIÇÃO ORDINÁRIA",
                r.NR_TURNO,
                619 + r.NR_TURNO,
                f"Eleição Geral Federal {ano}",
                "04/10/2026",
                "F",
                r.SG_UF,
                "BR",
                "BRASIL",
                r.CD_MUNICIPIO,
                r.NM_MUNICIPIO,
                r.NR_ZONA,
                r.NR_SECAO,
                1,
                "PRESIDENTE",
                r.NR_VOTAVEL,
                NOMES[r.NR_VOTAVEL],
                r.QT_VOTOS,
                1015,
                sq,
                "ESCOLA MUNICIPAL JOÃO",
                "RUA DA AÇUCENA, 10",
            ]
        )
    if linha_nula:  # registro com quantidade ausente: deve ser descartado com aviso
        linhas.append(linhas[0][:21] + ["#NULO"] + linhas[0][22:])
    destino.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(f"votacao_secao_{ano}_BR.csv", _csv_tse(linhas, COLUNAS_SECAO))
        z.writestr("leiame.pdf", b"%PDF-1.4 leiame")
    return destino


def escrever_detalhe(secoes: pd.DataFrame, destino: Path, semente: int = 0) -> Path:
    """Detalhe da apuração por município e zona, coerente com os votos (comparecimento = votos)."""
    rng = np.random.default_rng(semente)
    ano = int(secoes["ANO_ELEICAO"].iloc[0])
    g = secoes.groupby(["NR_TURNO", "SG_UF", "CD_MUNICIPIO", "NM_MUNICIPIO", "NR_ZONA"])["QT_VOTOS"].sum()
    linhas = []
    for (t, uf, cd, nm, zona), comp in g.items():
        aptos = int(comp / rng.uniform(0.75, 0.85))
        for cargo, ds in [(1, "PRESIDENTE"), (3, "GOVERNADOR")]:
            linhas.append(
                [
                    "26/10/2026",
                    "10:00:00",
                    ano,
                    2,
                    "ELEIÇÃO ORDINÁRIA",
                    t,
                    619 + t,
                    f"Eleição {ano}",
                    "04/10/2026",
                    "F",
                    uf,
                    "BR",
                    "BRASIL",
                    cd,
                    nm,
                    zona,
                    cargo,
                    ds,
                    aptos,
                    10,
                    0,
                    0,
                    10,
                    comp,
                    0,
                    aptos - comp,
                    "N",
                    comp,
                    comp,
                    comp,
                    0,
                    0,
                    0,
                    0,
                ]
            )
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(f"detalhe_votacao_munzona_{ano}_BR.csv", _csv_tse(linhas, COLUNAS_DETALHE))
    return destino


def csv_de_zip(caminho: Path) -> pd.DataFrame:
    with zipfile.ZipFile(caminho) as z:
        nome = next(n for n in z.namelist() if n.endswith(".csv"))
        return pd.read_csv(io.BytesIO(z.read(nome)), sep=";", encoding="latin-1", dtype=str)
