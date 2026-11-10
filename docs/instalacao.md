# Instalação

## Pré-requisitos

| Ferramenta | Versão | Observação |
|---|---|---|
| [pyenv](https://github.com/pyenv/pyenv) / [pyenv-win](https://github.com/pyenv-win/pyenv-win) | qualquer recente | Fixa a versão do Python do projeto |
| Python | **3.12.10** | Definido em `.python-version` |
| [Poetry](https://python-poetry.org/) | **≥ 2.0** | Instalado via `pipx` ou instalador oficial |

Só o pyenv e o Poetry ficam fora do ambiente virtual. Todas as outras
ferramentas (Ruff, Pytest, MkDocs) são instaladas **dentro** do `.venv` pelo Poetry.

## Passo a passo

1. Instale e ative a versão do Python:

    ```bash
    pyenv install 3.12.10
    pyenv version          # deve mostrar 3.12.10 (set by .../.python-version)
    ```

2. Configure o ambiente virtual dentro do projeto (`.venv/`). O `poetry.toml`
   já vem versionado, mas o comando é idempotente:

    ```bash
    poetry config virtualenvs.in-project true --local
    ```

3. Vincule o Poetry ao Python do pyenv:

    === "Linux/macOS"

        ```bash
        poetry env use "$(pyenv which python)"
        ```

    === "Windows (PowerShell)"

        ```powershell
        poetry env use (pyenv which python)
        ```

4. Instale as dependências (produção, `dev` e `docs`), exatamente como no `poetry.lock`:

    ```bash
    poetry install --with dev,docs
    ```

5. Confira o ambiente:

    ```bash
    poetry env info        # Python 3.12.10 em ./.venv
    poetry check --lock    # pyproject.toml válido e lock sincronizado
    poetry run formula1 --help
    ```

## Dependências

| Grupo | Pacotes | Uso |
|---|---|---|
| principal | `httpx`, `pandas`, `pyarrow`, `streamlit`, `altair` | Cliente HTTP, DataFrames, Parquet e dashboard |
| `dev` | `ruff`, `pytest`, `pytest-cov`, `taskipy` | Lint, formatação, testes, cobertura e atalhos `poetry run task ...` |
| `docs` | `mkdocs-material`, `mkdocstrings[python]` | Este site de documentação |

Para adicionar uma dependência, use sempre o Poetry, nunca `pip install`:

```bash
poetry add <pacote>                 # produção
poetry add --group dev <pacote>     # desenvolvimento
poetry add --group docs <pacote>    # documentação
```

## Solução de problemas

!!! warning "O Poetry usa outro Python mesmo após `poetry env use`"
    Se `poetry env info` mostrar outra versão (por exemplo 3.14) com
    `Path` apontando para a instalação global, verifique a variável
    `VIRTUAL_ENV`. Quando ela está definida no shell, o Poetry passa a usar esse
    ambiente em vez do `.venv` do projeto.

    ```powershell
    $env:VIRTUAL_ENV                 # se apontar para fora do projeto...
    Remove-Item Env:VIRTUAL_ENV      # ...remova-a na sessão atual
    poetry env use (pyenv which python)
    ```

    Para corrigir de vez, remova a definição de `VIRTUAL_ENV` do seu perfil do
    PowerShell ou das variáveis de ambiente do usuário.

!!! warning "`Failed to read README.md: stream did not contain valid UTF-8`"
    O `README.md` precisa estar em UTF-8. No PowerShell 5.1, `>` e `Out-File`
    podem gravar em UTF-16; prefira um editor ou `Set-Content -Encoding utf8`.
