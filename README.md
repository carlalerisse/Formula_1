# Formula_1

[![CI](https://github.com/carlalerisse/F-rmula_1/actions/workflows/ci.yml/badge.svg)](https://github.com/carlalerisse/F-rmula_1/actions/workflows/ci.yml)

Pipeline ETL que extrai os dados históricos da Fórmula 1 (2023 em diante) da
[API OpenF1](https://openf1.org/docs/), normaliza os registros e grava tudo
localmente em JSON bruto e em Parquet particionado, pronto para análise com pandas.

> A OpenF1 é um projeto não oficial, sem vínculo com as empresas da Fórmula 1.
> Os dados históricos são gratuitos e não exigem autenticação.

## Pré-requisitos

- [pyenv](https://github.com/pyenv/pyenv) (ou [pyenv-win](https://github.com/pyenv-win/pyenv-win)) com Python **3.12.10**
- [Poetry](https://python-poetry.org/) **2.0 ou superior**

## Instalação rápida

```bash
pyenv install 3.12.10              # se ainda não estiver instalado
poetry config virtualenvs.in-project true --local
poetry env use "$(pyenv which python)"   # PowerShell: poetry env use (pyenv which python)
poetry install --with dev,docs
```

## Como executar

```bash
# Corridas de 2023, apenas voltas e stints
poetry run formula1 extract --year 2023 --session-type Race --endpoints laps,stints

# Temporada 2024 completa com os endpoints padrão
poetry run formula1 extract --year 2024
```

Os arquivos vão para `./data` (ou para o diretório da variável `F1_DATA_DIR`):

```python
import pandas as pd

laps = pd.read_parquet("data/processed/laps")
```

Execuções repetidas pulam as sessões já baixadas. Use `--force` para reextrair.

## Dashboard

```bash
poetry run task dashboard    # http://localhost:8501
```

A visão inicial mostra as **5 voltas mais rápidas de cada circuito**, com todas
as sessões extraídas da OpenF1, filtros por temporada e por sessão (Race, Sprint,
Qualifying...) e a opção de contar só a melhor volta de cada piloto. Para ela,
basta extrair `meetings`, `sessions`, `drivers` e `laps`:

```bash
poetry run formula1 extract --year 2024 --endpoints meetings,sessions,drivers,laps
poetry run task dashboard
```

Para abrir **só** o painel das 5 voltas mais rápidas, use o script
[`dashboard.py`](dashboard.py) da raiz:

```bash
poetry run task top5         # equivale a: poetry run streamlit run dashboard.py
```

A visão **Análise por sessão** traz ritmo por volta, estratégia de pneus, evolução
das posições, resultado e pit stops. Veja [docs/dashboard.md](docs/dashboard.md).

## Tarefas de desenvolvimento

Atalhos definidos com [taskipy](https://github.com/taskipy/taskipy) no `pyproject.toml`:

| Comando | O que faz |
|---|---|
| `poetry run task test` | Testes unitários com cobertura (mínimo de 50%) |
| `poetry run task lint` | `ruff check` + `ruff format --check` (não altera arquivos) |
| `poetry run task format` | `ruff check --fix` + `ruff format` (corrige e formata) |
| `poetry run task docs` | Serve a documentação em http://127.0.0.1:8000 |
| `poetry run task dashboard` | Abre o dashboard em http://localhost:8501 |

`poetry run task --list` lista todas as tarefas.

## Como testar

```bash
poetry run task test                     # testes unitários, com cobertura mínima de 50%
poetry run pytest -m integration --no-cov  # chamada real e pequena à API
```

Validação completa (lint, formatação, testes e documentação):

```bash
poetry check --lock && poetry run ruff check . && poetry run ruff format --check . \
  && poetry run pytest -m "not integration" && poetry run mkdocs build --strict
```

O mesmo pipeline roda no GitHub Actions ([`.github/workflows/ci.yml`](.github/workflows/ci.yml))
a cada push e pull request em `main` e `dev`. Detalhes dos jobs em [docs/testes.md](docs/testes.md).

## Documentação

```bash
poetry run task docs    # http://127.0.0.1:8000
```

A documentação completa fica em [`docs/`](docs/index.md): instalação, uso,
testes, arquitetura, referência da API Python e resumo da API OpenF1.
