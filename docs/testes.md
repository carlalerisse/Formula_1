# Testes

Os testes usam **Pytest** e ficam em `tests/`, espelhando a estrutura de `src/formula1/`.

```text
tests/
├── conftest.py                       # payloads de exemplo e cliente HTTP falso
├── unit/
│   ├── conftest.py                   # dados de uma sessão e diretório de dados de exemplo
│   ├── adapters/test_openf1_client.py
│   ├── adapters/test_storage.py
│   ├── dashboard/test_app.py         # app Streamlit via AppTest (sem navegador)
│   ├── dashboard/test_charts.py
│   ├── dashboard/test_data.py
│   ├── domain/test_analytics.py
│   ├── domain/test_endpoints.py
│   ├── domain/test_transform.py
│   ├── services/test_pipeline.py
│   ├── test_config.py
│   └── test_main.py
└── integration/
    └── test_openf1_live.py           # @pytest.mark.integration (API real)
```

## Executando

| Objetivo | Comando |
|---|---|
| Testes unitários (sem rede), com cobertura | `poetry run task test` (atalho de `poetry run pytest -m "not integration"`) |
| Teste de integração (chamada real e pequena) | `poetry run pytest -m integration --no-cov` |
| Todos os testes | `poetry run pytest` |
| Um arquivo ou teste específico | `poetry run pytest tests/unit/domain/test_transform.py::test_parse_gap_valores_validos -v` |

Os testes unitários são determinísticos e não acessam a rede:

- o cliente HTTP roda sobre `httpx.MockTransport`, e a função `sleep` é
  substituída por uma lista que registra as esperas (retry e backoff testados
  sem esperar de verdade);
- o pipeline usa um `FakeClient` com payloads fixos;
- o armazenamento grava em `tmp_path`.

O teste de integração faz uma única consulta real
(`sessions?year=2023&session_name=Race`) e falha se a API estiver fora do ar.
Por isso ele fica fora do pipeline padrão de validação. Rode-o com `--no-cov`:
sozinho, ele não atinge o mínimo de 50% de cobertura, que vale apenas para a
suíte unitária.

## Cobertura

A cobertura é medida pelo `pytest-cov` sobre `src/formula1/`, com cobertura de
ramos (`branch = true`). O mínimo obrigatório é **50%**: abaixo disso, o
`pytest` termina com erro (`--cov-fail-under=50` e `fail_under = 50`). Reduzir
esse limite exige autorização do responsável pelo projeto.

| Relatório | Comando |
|---|---|
| Terminal, com linhas não cobertas | `poetry run pytest --cov-report=term-missing` |
| HTML em `htmlcov/` | `poetry run pytest --cov-report=html` |
| XML (CI) | `poetry run pytest --cov-report=xml` |

Como ler o relatório do terminal:

- `Stmts` / `Miss`: comandos totais e não executados;
- `Branch` / `BrPart`: ramos (`if`/`else`) e ramos parcialmente cobertos;
- `Missing`: linhas, ou transições `origem->destino`, sem cobertura.

## Tarefas (taskipy)

As tarefas mais usadas têm atalhos no `pyproject.toml` (`[tool.taskipy.tasks]`):

| Comando | Equivale a |
|---|---|
| `poetry run task test` | `pytest -m "not integration"` |
| `poetry run task lint` | `ruff check . && ruff format --check .` |
| `poetry run task format` | `ruff check . --fix && ruff format .` |
| `poetry run task docs` | `mkdocs serve` (http://127.0.0.1:8000) |
| `poetry run task dashboard` | `streamlit run src/formula1/dashboard/app.py` (http://localhost:8501) |

`poetry run task --list` mostra todas as tarefas com a descrição. Use `task lint`
para **verificar** sem alterar nada (como no pipeline abaixo) e `task format`
para **corrigir** e formatar o código.

## Pipeline de validação local

Antes de concluir qualquer mudança, rode:

=== "Bash"

    ```bash
    poetry check --lock \
      && poetry run task lint \
      && poetry run task test \
      && poetry run mkdocs build --strict
    ```

=== "PowerShell 5.1"

    ```powershell
    poetry check --lock; if ($?) { poetry run task lint }; if ($?) { poetry run task test }; if ($?) { poetry run mkdocs build --strict }
    ```

A tarefa só está concluída se todos os comandos terminarem com sucesso.

## Integração contínua (CI)

O workflow [`.github/workflows/ci.yml`](https://github.com/carlalerisse/F-rmula_1/blob/main/.github/workflows/ci.yml)
roda o mesmo pipeline no GitHub Actions (Ubuntu, Python do `.python-version`,
Poetry 2.5.1 com cache das dependências).

| Job | O que faz | Quando roda |
|---|---|---|
| **Lock e lint (Ruff)** | `poetry check --lock` e `poetry run task lint` | push e PR em `main`/`dev`, manual |
| **Testes unitários e cobertura** | `poetry run task test` (falha abaixo de 50%) e publica o `coverage.xml` como artefato | push e PR em `main`/`dev`, manual |
| **Build da documentação** | `poetry run mkdocs build --strict` | push e PR em `main`/`dev`, manual |
| **Integração (API OpenF1 real)** | `poetry run pytest -m integration --no-cov` | manual (*Run workflow*) e toda segunda às 06:00 UTC |

Os três primeiros jobs rodam em paralelo e bloqueiam o merge quando falham
(com a proteção de branch configurada). O de integração não roda em push nem
em PR, para que instabilidades da API externa não travem o desenvolvimento.
Execuções antigas do mesmo branch são canceladas quando chega um push novo.
