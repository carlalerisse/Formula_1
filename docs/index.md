# Fórmula 1 ETL

Pipeline ETL que extrai os **dados históricos da Fórmula 1** (temporada 2023 em
diante) da [API OpenF1](openf1.md), normaliza os registros e os grava localmente
em **JSON bruto** e em **Parquet particionado**, prontos para análise com pandas,
DuckDB ou Spark.

## Problema que resolve

A OpenF1 oferece dados ricos (voltas, stints, pit stops, posições, gaps, clima,
direção de prova, resultados), mas:

- cada consulta devolve um único endpoint de uma única sessão, em JSON;
- os tipos variam entre sessões: gaps chegam como número ou como `"+1 LAP"`, e a
  classificação traz arrays Q1/Q2/Q3;
- a API não publica limites de requisição e responde `429` quando é sobrecarregada.

Este projeto percorre uma temporada inteira, respeita a API com pausas e
retries, normaliza os tipos e entrega um dataset local consistente e idempotente.

## Funcionalidades

- Extração de uma temporada: `meetings → sessions → endpoints por sessão`.
- 18 endpoints históricos suportados, sendo 12 extraídos por padrão.
- Filtros por tipo ou nome de sessão (`Race`, `Qualifying`, `Sprint`...).
- Normalização: datas em UTC, tipos anuláveis, gaps convertidos em segundos e
  em voltas, Q1/Q2/Q3 explodidos e campos depreciados removidos.
- Armazenamento em JSON bruto e em Parquet particionado por
  `year/meeting_key/session_key`.
- Execuções idempotentes: as sessões já baixadas são puladas, a menos que se use `--force`.
- Falhas isoladas: um erro numa sessão é registrado e não interrompe o lote.
- [Dashboard](dashboard.md) em Streamlit que abre no **top 5 voltas mais
  rápidas de cada circuito** e traz a análise por sessão: ritmo por volta,
  estratégia de pneus, evolução de posições, resultado e pit stops.

## Por onde começar

| Página | Conteúdo |
|---|---|
| [Instalação](instalacao.md) | pyenv, Poetry e dependências |
| [Uso](uso.md) | CLI, variáveis de ambiente e leitura dos dados |
| [Dashboard](dashboard.md) | Como abrir e usar o dashboard Streamlit |
| [Testes](testes.md) | Como rodar os testes e interpretar a cobertura |
| [Arquitetura](arquitetura.md) | Camadas, fluxo de dados e decisões técnicas |
| [API OpenF1](openf1.md) | Resumo dos endpoints, filtros e limitações |
| [Referência da API](referencia/api.md) | Classes e funções do pacote `formula1` |

!!! note "Fonte dos dados"
    A OpenF1 é um projeto **não oficial**, sem vínculo com as empresas da Fórmula 1.
    Este pipeline usa apenas os dados históricos, que são gratuitos e não exigem
    autenticação.
