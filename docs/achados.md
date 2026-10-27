# Achados — eleição presidencial 2026

Gerado por `python -m eleicoes.figuras_readme` a partir dos dados do TSE.

## Resultado nacional

| Turno | Candidato | Votos | % válidos |
|---|---|---:|---:|
| 1º | Flávio Bolsonaro | 56.104.503 | 47,03% |
| 1º | Lula | 53.879.538 | 45,16% |
| 1º | Augusto Cury | 3.448.569 | 2,89% |
| 1º | Renan Santos | 2.675.887 | 2,24% |
| 1º | Ronaldo Caiado | 2.605.148 | 2,18% |
| 2º | Lula | 64.256.232 | 51,79% |
| 2º | Flávio Bolsonaro | 59.826.041 | 48,21% |

| Turno | Abstenção | Brancos | Nulos |
|---|---:|---:|---:|
| 1º | 21,1% | 1,8% | 2,9% |
| 2º | – | 1,1% | 2,1% |

## Por região (2º turno)

| Região | Flávio Bolsonaro | Lula |
|---|---:|---:|
| Norte | 50,0% | 50,0% |
| Nordeste | 30,6% | 69,4% |
| Centro-Oeste | 60,0% | 40,0% |
| Sudeste | 52,8% | 47,2% |
| Sul | 62,6% | 37,4% |
| Exterior | 46,1% | 53,9% |

## Municípios (2º turno)

- Lula: venceu em 2.876 municípios
- Flávio Bolsonaro: venceu em 2.695 municípios
- 213 municípios mudaram de vencedor entre os turnos

## Transferência de votos (estimativa, IC 95%)

| 1º turno | Flávio Bolsonaro | Lula | Branco/Nulo |
|---|---:|---:|---:|
| Flávio Bolsonaro | 98% (98–99) | 1% (1–1) | 1% (1–1) |
| Lula | 0% (0–0) | 100% (100–100) | 0% (0–0) |
| Augusto Cury | 25% (24–27) | 61% (59–62) | 14% (13–15) |
| Renan Santos | 34% (33–35) | 50% (49–51) | 16% (16–17) |
| Ronaldo Caiado | 46% (45–47) | 41% (40–44) | 12% (11–13) |
| Outros | 51% (46–53) | 35% (33–40) | 14% (13–15) |
| Branco/Nulo | 0% (0–1) | 64% (62–64) | 36% (35–37) |

## Análises avançadas

- Moran's I = 0,897 (p = 0,001)
- Regressão ponderada: R² = 0,746 (5.565 municípios)
- Gradient boosting (validação por UF): R² = 0,730, erro médio 7,6 p.p. (palpite pela média: 16,1 p.p.)
- Indicadores mais importantes: Renda per capita (log), Região: Nordeste, Pobres (%)
