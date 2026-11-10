# plan.md: Pipeline ETL de Fórmula 1 (OpenF1)

> Plano de criação do projeto. A execução segue fase a fase, sob demanda.
> Referências: `doc_api.md` (API OpenF1) e `skill.md` (padrão de engenharia obrigatório).

## Contexto

O repositório tem só o esqueleto gerado pelo `poetry new`. Hoje há três problemas:
- o pacote se chama `src/f_rmula_1/`, porque o Poetry removeu o acento;
- `requires-python = ">=3.14"` conflita com o `.python-version` (`3.12.10`);
- faltam `poetry.toml`, `poetry.lock`, `.gitignore`, a configuração de Ruff/Pytest/cobertura, o `mkdocs.yml` e o `docs/`.

**Objetivo:** construir um **pipeline ETL** que extrai os dados históricos (2023 em diante, gratuitos e sem autenticação) da OpenF1, normaliza e grava localmente em Parquet para análise, seguindo à risca a `skill.md`.

**Fora de escopo (v1):** dados em tempo real (pagos, com token, MQTT e WebSocket), dashboards e análises.

## Decisões

| Tema | Decisão |
|---|---|
| Pacote | `formula1` (`src/formula1/`), com `name = "formula1"` |
| Python | 3.12.10, `requires-python = ">=3.12,<3.13"` |
| HTTP | `httpx`, que traz `MockTransport` para testar sem rede e sem dependência extra |
| Dados | `pandas` + `pyarrow` |
| Armazenamento | `data/raw/` (JSON bruto) e `data/processed/` (Parquet particionado por `year/meeting_key/session_key`) |
| Diretório de dados | Variável de ambiente `F1_DATA_DIR` (padrão `./data`, ignorado no Git) |
| CLI | `argparse` em `__main__.py`, com o script `formula1` |

## Fase 0: Corrigir a base do projeto

1. Renomear `src/f_rmula_1/` para `src/formula1/` e ajustar `[project].name` e `[tool.poetry].packages`.
2. Ajustar `requires-python` para `">=3.12,<3.13"`. Conferir com `pyenv version`.
3. Rodar `poetry config virtualenvs.in-project true --local` (cria o `poetry.toml`) e `poetry env use (pyenv which python)`.
4. Criar o `.gitignore` da skill §6.5, acrescentando `data/`.
5. Adicionar as dependências:
   - `poetry add httpx pandas pyarrow`
   - `poetry add --group dev ruff pytest pytest-cov`
   - `poetry add --group docs mkdocs-material "mkdocstrings[python]"`
6. Copiar para o `pyproject.toml` os blocos `[tool.ruff*]`, `[tool.pytest.ini_options]` e `[tool.coverage*]` da skill §6.3, com `projeto` trocado por `formula1`.
7. Rodar `poetry check --lock`.

## Fase 1: Estrutura do código

```text
src/formula1/
├── __init__.py
├── __main__.py              # CLI: formula1 extract ...
├── config.py                # BASE_URL, F1_DATA_DIR, timeouts, retries, ENDPOINTS
├── domain/
│   ├── endpoints.py         # Enum/registry dos endpoints e escopo (meeting/session)
│   └── transform.py         # Regras puras de normalização (sem I/O)
├── adapters/
│   ├── openf1_client.py     # Cliente HTTP (httpx): query string com operadores, retry
│   └── storage.py           # Escrita de JSON bruto e Parquet particionado
└── services/
    └── pipeline.py          # Orquestra: ano → meetings → sessions → endpoints
```

## Fase 2: Cliente OpenF1 (`adapters/openf1_client.py`)

- `OpenF1Client(base_url, timeout, max_retries, client: httpx.Client | None)`. O cliente pode ser injetado para os testes.
- `get(endpoint: str, filters: list[Filter]) -> list[dict]`:
  - monta a query manualmente para aceitar `>=`, `<=`, `>` e `<` (doc_api §2 e §8);
  - repete chaves para filtros com vários valores;
  - codifica espaços como `%20`.
- `Filter` é uma dataclass (`field`, `op`, `value`) e valida o operador. Um operador inválido gera `ValueError`.
- Retry com backoff exponencial em 429 e 5xx. Erros 4xx viram `OpenF1Error`. Usa `logging`, nunca `print`.
- Pausa curta configurável entre chamadas, já que a API não publica rate limit.

## Fase 3: Transformação (`domain/transform.py`, funções puras)

- `to_dataframe(records, endpoint) -> pd.DataFrame`: tipagem de colunas e datas convertidas para `datetime` UTC.
- `parse_gap(value) -> float | None`: trata `null` (líder) e `"+1 LAP"`/`"+N LAPS"`. Gera as colunas `gap_seconds` e `laps_behind` em `intervals` e `session_result`.
- Remove os campos depreciados `drivers.country_code` e `pit.pit_duration` (doc_api §7).
- Arrays (`segments_sector_*`, Q1/Q2/Q3 em `duration`) são mantidos ou explodidos em colunas `q1`, `q2` e `q3`.
- Uma lista vazia gera um DataFrame vazio com o schema esperado.

## Fase 4: Armazenamento (`adapters/storage.py`)

- `save_raw(endpoint, keys, records)` grava `data/raw/<endpoint>/year=.../meeting_key=.../session_key=....json`.
- `save_parquet(endpoint, keys, df)` grava `data/processed/<endpoint>/year=.../meeting_key=.../session_key=.../part.parquet`.
- `exists(...)` dá **idempotência**: as sessões já baixadas são puladas, a menos que se use `--force`.

## Fase 5: Pipeline e CLI

- `services/pipeline.py`, com `run(year, endpoints, session_types, force) -> PipelineReport`:
  1. `meetings?year=Y` (ignora `is_cancelled`);
  2. `sessions?meeting_key=...` (filtro opcional por `session_name` ou `session_type`);
  3. para cada sessão e endpoint, faz extract, raw, transform e grava o Parquet.
  - Endpoints só de corrida (`intervals`, `overtakes`, `championship_*`) são pulados fora de `Race`.
- Endpoints padrão: `meetings`, `sessions`, `drivers`, `laps`, `stints`, `pit`, `position`, `intervals`, `race_control`, `weather`, `session_result` e `starting_grid`.
  - `car_data` e `location` (~3,7 Hz, alto volume) só entram com `--endpoints` explícito.
- CLI: `poetry run formula1 extract --year 2024 [--endpoints laps,stints] [--session-type Race] [--force]`.
- `PipelineReport` informa as contagens por endpoint e as falhas. Falhas por sessão são registradas no log e não interrompem o lote.

## Fase 6: Testes (`tests/`, espelhando `src/`)

- `tests/conftest.py`: fixtures com payloads JSON de exemplo e `httpx.MockTransport`.
- `tests/unit/adapters/test_openf1_client.py`:
  - montagem de query com operadores e vários valores;
  - retry em 429/500;
  - erro em 404;
  - operador inválido.
- `tests/unit/domain/test_transform.py`:
  - `parse_gap` parametrizado (`null`, `"+1 LAP"`, `"+3 LAPS"`, número, string inválida);
  - datas em UTC;
  - lista vazia;
  - remoção de campos depreciados.
- `tests/unit/adapters/test_storage.py`: escrita e leitura com `tmp_path`, caminhos de partição e idempotência.
- `tests/unit/services/test_pipeline.py`: cliente falso, pulo de sessões que não são corrida, `--force` e falha isolada.
- `tests/unit/test_main.py`: parsing de argumentos da CLI.
- `tests/integration/test_openf1_live.py`, com `@pytest.mark.integration`: chamada real e pequena (`sessions?year=2023&session_name=Race`). Roda fora do pipeline padrão com `-m "not integration"`.
- Meta: cobertura ≥ 50% (obrigatória), com alvo de ~80%.

## Fase 7: Documentação

- `mkdocs.yml` conforme a skill §6.4, com `site_name: Fórmula 1 ETL`.
- Páginas em `docs/`:
  - `index.md`;
  - `instalacao.md`;
  - `uso.md`: CLI, `F1_DATA_DIR` e exemplos de leitura do Parquet com pandas;
  - `testes.md`;
  - `arquitetura.md`: camadas, fluxo de dados, decisões e limitações da API;
  - `referencia/api.md` (mkdocstrings).
- Atualizar o `README.md` conforme a skill §9.2.
- Mover o `doc_api.md` para `docs/openf1.md` e incluí-lo na navegação. O `skill.md` fica na raiz.

## Verificação

1. Pipeline local (skill §8.5, PowerShell):
   ```powershell
   poetry check --lock; if ($?) { poetry run ruff check . }; if ($?) { poetry run ruff format --check . }; if ($?) { poetry run pytest -m "not integration" }; if ($?) { poetry run mkdocs build --strict }
   ```
2. Integração: `poetry run pytest -m integration`.
3. Ponta a ponta:
   - rodar `poetry run formula1 extract --year 2023 --session-type Race --endpoints laps,stints`;
   - conferir os arquivos em `data/processed/laps/...`;
   - ler com `pd.read_parquet("data/processed/laps")`.
4. Rodar o mesmo comando de novo: as sessões devem ser puladas (idempotência).

## Arquivos críticos

- Alterar: `pyproject.toml`, `src/f_rmula_1/` (renomear), `README.md`.
- Criar: `poetry.toml`, `poetry.lock`, `.gitignore`, `mkdocs.yml`, `docs/**`, `src/formula1/**` e `tests/**`, conforme as fases acima.
