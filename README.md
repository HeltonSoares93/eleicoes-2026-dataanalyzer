# Eleições presidenciais 2026 — análise do 1º e 2º turnos

Análise da eleição presidencial brasileira com dados abertos do TSE: resultados por região, UF
e município, abstenção, transferência de votos entre turnos, padrões geográficos, relação com
indicadores socioeconômicos e comparação com 2022.

> **Principais achados:** *(preencher depois de rodar os notebooks com os dados oficiais
> completos dos dois turnos; ver `figuras/`)*

## Perguntas

1. Como o voto e a abstenção mudaram do 1º para o 2º turno, e onde?
2. Qual a relação entre o resultado nos municípios e o perfil socioeconômico?
3. Para onde foram os votos dos candidatos eliminados no 1º turno?
4. O voto forma blocos geográficos? O que mudou em relação a 2022?

## Como rodar

Requer Python 3.11 ou mais recente.

```bash
python -m venv .venv
.venv\Scripts\activate             # Windows  (Linux/Mac: source .venv/bin/activate)
pip install -e ".[app,notebook,dev]"

python -m eleicoes.baixar          # dados do TSE (2026 e 2022) + fontes externas, com manifesto SHA-256
python -m eleicoes.processar                # processa o ano principal (config.yaml)
python -m eleicoes.processar --ano 2022     # processa a eleição de comparação

pytest                             # 60 testes (inclui conferências nos seus dados reais)
```

Depois, abra os notebooks em `notebooks/` e rode "Run All":

| Notebook | Conteúdo |
|---|---|
| `01_resultados.ipynb` | resultado nacional, participação, região, UF, abstenção, mapas por área e proporcional, demais candidatos, 1º → 2º turno |
| `02_ciencia_de_dados.ipynb` | inferência ecológica por seção, Moran's I e LISA, regressão ponderada, gradient boosting + SHAP, swing 2022 → 2026 |

App interativo: `streamlit run app/streamlit_app.py`

**Vindo da versão anterior (scripts soltos em `src/`):** apague `src/processar_votacao.py`,
`src/analise.py`, `requirements.txt`, `notebooks/01_analise_turnos.ipynb` e o conteúdo de
`data/processed/`. O zip do TSE que já está em `data/raw/` é reaproveitado (não baixa de novo).

**Quando o TSE atualizar um arquivo** (por exemplo, publicar o 2º turno):
`python -m eleicoes.baixar --forcar` e `python -m eleicoes.processar`.

## Dados

| Fonte | Uso | Onde fica |
|---|---|---|
| TSE — Votação por seção eleitoral (Presidente) | votos por candidato, branco e nulo | `data/raw/` |
| TSE — Detalhe da apuração por município e zona | eleitores aptos, comparecimento, abstenção | `data/raw/` |
| Malha municipal IBGE (`tbrugz/geodata-br`) | mapas | `data/external/` |
| Correspondência TSE ↔ IBGE (`betafcc/Municipios-Brasileiros-TSE`) | cruzar códigos de município | `data/external/` |
| Atlas do Desenvolvimento Humano (PNUD/IPEA/FJP, Censo 2010) | IDHM, renda, escolaridade, desigualdade | `data/external/` |
| Censo 2022 (`CaiqueDourado/municipios-e-estados-do-brasil`) | população, densidade, coordenadas | `data/external/` |

As fontes externas estão fixadas em um commit específico e conferidas por SHA-256 no
`config.yaml`. Cada download fica registrado em `data/manifesto.json` (URL, data, tamanho, hash).

## Estrutura

```
config.yaml            ano analisado, ano de comparação, URLs e hashes das fontes
src/eleicoes/
  baixar.py            download com manifesto e verificação de hash
  processar.py         leitura dos zips do TSE (pandas, em blocos) e bases limpas em parquet
  esquema.py           contrato de dados (pandera): tipos, faixas e unicidade
  dados.py             leitura das bases processadas e das fontes externas
  resultados.py        cálculos: finalistas, percentuais, margens, abstenção, swing
  transferencia.py     inferência ecológica por seção (com bootstrap)
  espacial.py          Moran's I e LISA
  modelo.py            regressão ponderada (WLS) e gradient boosting + SHAP
  graficos.py          gráficos e mapas (paleta acessível a daltônicos)
notebooks/             análises
app/                   app Streamlit
tests/                 testes (pytest) com amostra sintética no formato exato do TSE
```

## Qualidade

- **Contrato de dados:** o processamento valida cada base antes de salvar (tipos inteiros
  comuns, votos ≥ 0, turno ∈ {1, 2}, sem duplicatas). Problemas aparecem no processamento,
  com a coluna e o motivo, e não depois, no notebook.
- **Validação cruzada:** votos totais (votação por seção) x comparecimento (detalhe da
  apuração), dois arquivos independentes do TSE, conferidos município a município.
- **Conferência com o resultado oficial:** preencha `oficial:` no `config.yaml` e
  `pytest -m dados_reais` compara os totais.
- **Testes:** amostra sintética no formato exato do TSE (Latin 1, `;`, `#NULO`, exterior e
  trânsito) com estrutura conhecida; os testes verificam se a inferência ecológica e a
  análise espacial recuperam o padrão plantado. Os notebooks e o app são executados nos testes.
- **CI:** GitHub Actions roda lint (ruff) e testes em Linux e Windows a cada push.
- **Pre-commit:** `pre-commit install` ativa ruff e `nbstripout`, que limpa as saídas dos notebooks antes do commit.

## Notas metodológicas

- Percentuais sobre votos válidos, como no resultado oficial.
- Exterior (`ZZ`) e voto em trânsito (`VT`) entram nos totais, mas não nos mapas.
- **Inferência ecológica:** estima padrões médios a partir de agregados, não o voto de cada
  pessoa. Supõe comportamento semelhante entre seções da mesma UF. Quem deixou de votar entre
  os turnos não é modelado explicitamente (o arquivo por seção não traz eleitores aptos).
- **Socioeconômico:** indicadores do Atlas são do Censo 2010. Associação entre municípios não
  é causalidade. A validação do gradient boosting é por UF, para não superestimar o desempenho
  por vizinhança geográfica.
- Malha municipal de 2010: os 6 municípios criados depois aparecem em cinza nos mapas.
