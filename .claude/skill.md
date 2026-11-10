# Skill: Padrão de Engenharia de Software Python

> **Status:** obrigatório · **Escopo:** todo projeto Python desenvolvido por humanos ou agentes de IA
> **Pilares:** reprodutibilidade · qualidade · testes · documentação · manutenibilidade

---

## 1. Objetivo da Skill

Esta Skill define o padrão técnico **obrigatório** para desenvolver projetos Python. Ela diz:

- **quais ferramentas** usar (pyenv, Poetry, Ruff, Pytest, pytest-cov, MkDocs Material);
- **como configurá-las** (configuração centralizada no `pyproject.toml` e no `mkdocs.yml`);
- **como organizar** o código, os testes e a documentação;
- **quais comandos** executar em cada etapa do ciclo de desenvolvimento;
- **quais critérios** um projeto precisa atender para ser considerado concluído.

Um agente de IA que use esta Skill deve tratá-la como **contrato**: as regras se aplicam antes, durante e depois de cada implementação.

> **Convenção:** neste documento, `projeto` é o nome do pacote principal. Substitua-o pelo nome real do pacote (ex.: `src/formula1/`) em todos os comandos e configurações.

---

## 2. Comportamento obrigatório do agente de IA

### 2.1 Antes de implementar

1. **Ler esta Skill por completo** antes de escrever qualquer código.
2. **Verificar o ambiente** (seção 8.1): versão do Python via pyenv, Poetry instalado, ambiente virtual ativo e dependências sincronizadas com o `poetry.lock`.
3. **Inspecionar o projeto existente**: estrutura de diretórios, `pyproject.toml`, `mkdocs.yml`, testes e documentação já presentes. Seguir os padrões do projeto em vez de criar padrões paralelos.
4. Se algo obrigatório estiver ausente (ex.: sem `.python-version` ou sem configuração do Ruff), **criar ou corrigir primeiro** e só depois desenvolver a funcionalidade.

### 2.2 Durante a implementação

5. **Nunca instalar** bibliotecas ou ferramentas globalmente (`pip install` fora do ambiente, `sudo pip`, `pip install --user`). Toda dependência entra via `poetry add`.
6. **Criar ou atualizar testes** sempre que uma funcionalidade for criada ou alterada, na mesma entrega.
7. **Usar type hints** em todas as assinaturas públicas (parâmetros e retorno).
8. **Não ignorar erros do Ruff.** Corrigir a causa. Usar `# noqa: <REGRA>` só com justificativa técnica no comentário e apenas quando a correção não for viável.
9. **Não desativar regras, baixar o limite de cobertura nem alterar configurações obrigatórias** sem justificativa técnica **e** autorização explícita do responsável pelo projeto.

### 2.3 Depois de implementar

10. Executar o **pipeline de validação local** (seção 8.4): lint, formatação, testes com cobertura e build estrito da documentação.
11. **Atualizar a documentação** (`docs/` e `README.md`) sempre que houver mudança de comportamento, API pública, comandos, dependências ou arquitetura.
12. **Relatar com transparência**: informar o que foi feito, o resultado real dos comandos de validação (incluindo falhas) e qualquer requisito que **não pôde ser atendido**, com o motivo e a alternativa proposta. Nunca declarar sucesso sem ter executado as verificações.

---

## 3. Regras obrigatórias (resumo)

| # | Regra | Ferramenta |
|---|-------|-----------|
| R1 | A versão local do Python é definida pelo `.python-version` | pyenv |
| R2 | Dependências, pacotes e ambiente virtual são gerenciados exclusivamente pelo Poetry | Poetry |
| R3 | O `pyproject.toml` é o arquivo central de configuração | — |
| R4 | O `poetry.lock` é versionado no Git e garante a reprodutibilidade | Poetry |
| R5 | Nenhuma dependência do projeto é instalada globalmente | Poetry |
| R6 | Lint e formatação são feitos com Ruff, configurado no `pyproject.toml` | Ruff |
| R7 | O código segue a PEP 8 e usa type hints sempre que aplicável | Ruff |
| R8 | Os testes automatizados usam Pytest e ficam em `tests/` | Pytest |
| R9 | A cobertura mínima de `src/projeto/` é **50%**; abaixo disso a execução **falha** | pytest-cov |
| R10 | A documentação usa MkDocs Material, com `docs/index.md` e `mkdocs.yml` | MkDocs Material |

---

## 4. Ferramentas e tecnologias

| Ferramenta | Finalidade | Onde é instalada |
|-----------|-----------|------------------|
| **pyenv** (ou **pyenv-win** no Windows) | Instalar e fixar a versão do Python por projeto | Sistema (ferramenta de infraestrutura) |
| **Poetry** (≥ 2.0) | Dependências, ambiente virtual, build e lockfile | Sistema, via `pipx` ou instalador oficial |
| **Ruff** | Lint, formatação, ordenação de imports, detecção de erros | Grupo `dev` do Poetry |
| **Pytest** | Testes automatizados | Grupo `dev` do Poetry |
| **pytest-cov** | Medição de cobertura e relatórios | Grupo `dev` do Poetry |
| **MkDocs Material** | Site de documentação | Grupo `docs` do Poetry |
| **mkdocstrings[python]** | Referência de API gerada a partir das docstrings | Grupo `docs` do Poetry |

> **Exceção controlada:** apenas o **pyenv** e o **Poetry** ficam fora do ambiente virtual, por serem eles que criam e gerenciam esse ambiente. Todas as outras ferramentas (Ruff, Pytest, MkDocs etc.) ficam **dentro** do ambiente do Poetry.

---

## 5. Estrutura de diretórios

```text
projeto-raiz/
├── .python-version          # Versão do Python (gerada pelo pyenv)
├── .gitignore               # Arquivos ignorados pelo Git
├── README.md                # Apresentação e instruções rápidas
├── pyproject.toml           # Metadados, dependências e configuração das ferramentas
├── poetry.lock              # Versões bloqueadas (VERSIONAR)
├── poetry.toml              # Configuração local do Poetry (venv no projeto)
├── mkdocs.yml               # Configuração da documentação
├── src/
│   └── projeto/             # Código-fonte principal (pacote importável)
│       ├── __init__.py
│       ├── __main__.py      # Ponto de entrada opcional: python -m projeto
│       ├── config.py        # Configurações e constantes
│       ├── domain/          # Entidades e regras de negócio (sem I/O)
│       ├── services/        # Casos de uso / orquestração
│       ├── adapters/        # I/O: APIs, banco, arquivos, CLI
│       └── utils/           # Funções auxiliares genéricas
├── tests/
│   ├── __init__.py
│   ├── conftest.py          # Fixtures compartilhadas
│   ├── unit/                # Testes unitários (espelham src/projeto/)
│   └── integration/         # Testes de integração (opcional)
└── docs/
    ├── index.md             # Página inicial
    ├── instalacao.md        # Instalação e configuração do ambiente
    ├── uso.md               # Como executar o projeto
    ├── testes.md            # Como executar os testes e ver a cobertura
    ├── arquitetura.md       # Visão arquitetural e decisões
    └── referencia/
        └── api.md           # Referência de classes, funções e módulos
```

### 5.1 Princípios de organização

- **Layout `src/`**: impede imports acidentais do diretório de trabalho e garante que os testes rodem contra o pacote instalado.
- **Separação de responsabilidades**: regras de negócio (`domain/`) não dependem de I/O (`adapters/`). Isso facilita os testes unitários.
- **Testes espelham o código**: `src/projeto/services/pedido.py` → `tests/unit/services/test_pedido.py`.
- **Módulos pequenos e coesos**: cada módulo tem uma responsabilidade clara.
- **Adaptação permitida**: a estrutura pode ser simplificada em projetos pequenos (ex.: sem `domain/`/`adapters/`) ou expandida em projetos complexos, mantendo sempre `src/projeto/`, `tests/` e `docs/`.

---

## 6. Padrões de configuração

### 6.1 `.python-version`

Gerado pelo comando `pyenv local`. Contém apenas a versão:

```text
3.12.7
```

### 6.2 `poetry.toml` (ambiente virtual dentro do projeto)

Gerado por `poetry config virtualenvs.in-project true --local`:

```toml
[virtualenvs]
in-project = true
```

O ambiente fica em `.venv/` na raiz, o que facilita a integração com IDEs e a inspeção.

### 6.3 `pyproject.toml` (modelo de referência)

```toml
[project]
name = "projeto"
version = "0.1.0"
description = "Descrição curta e objetiva do projeto."
authors = [{ name = "Nome do Autor", email = "autor@exemplo.com" }]
readme = "README.md"
requires-python = ">=3.12,<3.13"
dependencies = [
    # Dependências de produção são adicionadas via: poetry add <pacote>
]

[project.scripts]
# Ponto de entrada opcional da CLI
projeto = "projeto.__main__:main"

[tool.poetry]
packages = [{ include = "projeto", from = "src" }]

[tool.poetry.group.dev.dependencies]
ruff = "^0.8"
pytest = "^8.3"
pytest-cov = "^6.0"

[tool.poetry.group.docs.dependencies]
mkdocs-material = "^9.5"
mkdocstrings = { extras = ["python"], version = "^0.27" }

[build-system]
requires = ["poetry-core>=2.0.0,<3.0.0"]
build-backend = "poetry.core.masonry.api"

# ---------------------------------------------------------------------------
# Ruff — lint e formatação
# ---------------------------------------------------------------------------
[tool.ruff]
target-version = "py312"
line-length = 88
src = ["src", "tests"]
extend-exclude = ["docs", ".venv"]

[tool.ruff.lint]
select = [
    "E",    # pycodestyle (erros) — PEP 8
    "W",    # pycodestyle (avisos) — PEP 8
    "F",    # Pyflakes — imports/variáveis não usados, nomes indefinidos
    "I",    # isort — ordenação de imports
    "N",    # pep8-naming — convenções de nomes
    "UP",   # pyupgrade — sintaxe moderna do Python
    "B",    # flake8-bugbear — bugs prováveis
    "SIM",  # flake8-simplify — simplificações
    "C4",   # flake8-comprehensions
    "ANN",  # flake8-annotations — exige type hints
    "S",    # flake8-bandit — problemas de segurança
    "PT",   # flake8-pytest-style — boas práticas no Pytest
    "RET",  # flake8-return
    "ERA",  # código comentado esquecido
    "PL",   # Pylint
    "RUF",  # regras específicas do Ruff
]
ignore = [
    "ANN401",  # permite typing.Any quando realmente necessário
]

[tool.ruff.lint.per-file-ignores]
"tests/**/*.py" = [
    "S101",     # assert é o padrão nos testes
    "ANN",      # anotações não são exigidas nos testes
    "PLR2004",  # valores literais ("magic numbers") são aceitáveis nos testes
]

[tool.ruff.lint.pydocstyle]
convention = "google"

[tool.ruff.format]
quote-style = "double"
indent-style = "space"
docstring-code-format = true

# ---------------------------------------------------------------------------
# Pytest + cobertura
# ---------------------------------------------------------------------------
[tool.pytest.ini_options]
minversion = "8.0"
testpaths = ["tests"]
addopts = [
    "-ra",
    "--strict-markers",
    "--strict-config",
    "--cov=projeto",
    "--cov-report=term-missing",
    "--cov-fail-under=50",
]
markers = [
    "integration: testes que dependem de recursos externos",
]

[tool.coverage.run]
source = ["src/projeto"]
branch = true

[tool.coverage.report]
fail_under = 50
show_missing = true
skip_covered = false
exclude_also = [
    "if TYPE_CHECKING:",
    "if __name__ == .__main__.:",
    "raise NotImplementedError",
]

[tool.coverage.html]
directory = "htmlcov"
```

> **Notas:**
> - As versões (`^0.8`, `^8.3` etc.) são referências. Use `poetry add` para obter as versões estáveis mais recentes, e o `poetry.lock` registrará as versões exatas.
> - `--cov-fail-under=50` e `fail_under = 50` fazem o Pytest **retornar erro** quando a cobertura de `src/projeto/` fica abaixo de 50%. Esse limite é o **mínimo**: subir o valor é incentivado; reduzi-lo é proibido sem autorização.
> - O grupo `ANN` exige type hints no código de produção, atendendo ao requisito de tipagem.

### 6.4 `mkdocs.yml` (modelo de referência)

```yaml
site_name: Projeto
site_description: Documentação técnica do Projeto
repo_url: https://github.com/organizacao/projeto  # ajustar ou remover

theme:
  name: material
  language: pt-BR
  features:
    - navigation.tabs
    - navigation.sections
    - navigation.top
    - search.suggest
    - search.highlight
    - content.code.copy
  palette:
    - scheme: default
      toggle:
        icon: material/brightness-7
        name: Modo escuro
    - scheme: slate
      toggle:
        icon: material/brightness-4
        name: Modo claro

plugins:
  - search
  - mkdocstrings:
      handlers:
        python:
          paths: [src]
          options:
            docstring_style: google
            show_source: true
            show_signature_annotations: true

markdown_extensions:
  - admonition
  - pymdownx.details
  - pymdownx.superfences
  - pymdownx.highlight:
      anchor_linenums: true
  - pymdownx.inlinehilite
  - pymdownx.tabbed:
      alternate_style: true
  - toc:
      permalink: true

nav:
  - Início: index.md
  - Instalação: instalacao.md
  - Uso: uso.md
  - Testes: testes.md
  - Arquitetura: arquitetura.md
  - Referência da API: referencia/api.md
```

Exemplo de `docs/referencia/api.md` (gerado a partir das docstrings):

```markdown
# Referência da API

::: projeto.services
::: projeto.domain
```

### 6.5 `.gitignore` (mínimo obrigatório)

```gitignore
# Ambiente virtual
.venv/

# Bytecode e caches
__pycache__/
*.py[cod]
.pytest_cache/
.ruff_cache/

# Cobertura
.coverage
.coverage.*
htmlcov/
coverage.xml

# Build e distribuição
build/
dist/
*.egg-info/

# Documentação gerada
site/

# Variáveis de ambiente e segredos
.env
.env.*

# IDEs e sistema operacional
.vscode/
.idea/
.DS_Store
Thumbs.db
```

> **Importante:** `poetry.lock` e `.python-version` **devem** ser versionados e **nunca** entram no `.gitignore`.

---

## 7. Padrões de código e de testes

### 7.1 Código

- Seguir a **PEP 8** (garantida pelo Ruff).
- **Type hints** em todas as funções e métodos públicos, incluindo o retorno. Usar a sintaxe moderna: `list[str]`, `dict[str, int]`, `X | None`.
- **Docstrings no estilo Google** em módulos, classes e funções públicas. Elas alimentam a referência da API no MkDocs.
- Nomes: `snake_case` para funções e variáveis, `PascalCase` para classes, `UPPER_SNAKE_CASE` para constantes.
- Funções curtas, com uma única responsabilidade e sem efeitos colaterais ocultos.
- Exceções específicas e significativas. Nunca usar `except:` genérico nem silenciar erros.
- Sem segredos no código: usar variáveis de ambiente.
- Usar `logging` em vez de `print` no código de produção.

Exemplo de referência:

```python
"""Cálculos relacionados à pontuação de pilotos."""

PONTOS_POR_POSICAO: dict[int, int] = {1: 25, 2: 18, 3: 15}


def calcular_pontos(posicao: int) -> int:
    """Retorna os pontos obtidos por um piloto em uma corrida.

    Args:
        posicao: Posição final do piloto (1 = vencedor).

    Returns:
        Quantidade de pontos conquistados; 0 se fora da zona de pontuação.

    Raises:
        ValueError: Se a posição for menor que 1.
    """
    if posicao < 1:
        msg = f"Posição inválida: {posicao}"
        raise ValueError(msg)
    return PONTOS_POR_POSICAO.get(posicao, 0)
```

### 7.2 Testes

- Arquivos `test_*.py`; funções `test_<comportamento>_<cenário>`.
- Estrutura **Arrange → Act → Assert** em cada teste.
- **Todo teste deve validar um resultado** (`assert`, `pytest.raises`, verificação de estado ou de chamadas). Testes que só executam código sem verificar nada **não são aceitos**.
- Cobrir obrigatoriamente:
  - **cenários positivos** (fluxo esperado);
  - **cenários negativos** (entradas inválidas);
  - **exceções** (`pytest.raises` com verificação da mensagem quando relevante);
  - **casos extremos** (limites, coleções vazias, `None`, zero, valores muito grandes).
- Usar `@pytest.mark.parametrize` para variações de entrada.
- Usar **fixtures** (`conftest.py`) para preparar dados reutilizáveis.
- Isolar dependências externas (rede, banco, disco, relógio) com `monkeypatch`, `tmp_path` ou mocks. Testes unitários devem ser **determinísticos e rápidos**.

Exemplo de referência:

```python
import pytest

from projeto.pontuacao import calcular_pontos


@pytest.mark.parametrize(
    ("posicao", "esperado"),
    [(1, 25), (2, 18), (3, 15)],
)
def test_calcular_pontos_posicoes_pontuaveis(posicao, esperado):
    assert calcular_pontos(posicao) == esperado


def test_calcular_pontos_fora_da_zona_retorna_zero():
    assert calcular_pontos(20) == 0


@pytest.mark.parametrize("posicao", [0, -1])
def test_calcular_pontos_posicao_invalida_lanca_erro(posicao):
    with pytest.raises(ValueError, match="Posição inválida"):
        calcular_pontos(posicao)
```

---

## 8. Comandos de execução

> Todos os comandos são executados **na raiz do projeto**. Ferramentas do projeto são sempre chamadas via `poetry run` (ou com o ambiente ativado), **nunca** por instalações globais.

### 8.1 Verificar o ambiente (antes de desenvolver)

```bash
pyenv --version              # pyenv disponível
pyenv version                # versão ativa (deve coincidir com .python-version)
poetry --version             # Poetry disponível (>= 2.0)
poetry env info              # ambiente virtual em uso
poetry check --lock          # pyproject.toml válido e poetry.lock sincronizado
```

### 8.2 Configuração inicial

| Objetivo | Comando |
|---------|---------|
| Instalar a versão do Python | `pyenv install 3.12.7` |
| Fixar a versão no projeto (cria `.python-version`) | `pyenv local 3.12.7` |
| Criar o venv dentro do projeto | `poetry config virtualenvs.in-project true --local` |
| Criar um novo projeto (layout src) | `poetry new --src projeto` |
| Inicializar o Poetry em um projeto existente | `poetry init` |
| Vincular o Poetry ao Python do pyenv (Linux/macOS) | `poetry env use "$(pyenv which python)"` |
| Vincular o Poetry ao Python do pyenv (Windows/PowerShell) | `poetry env use (pyenv which python)` |
| Instalar todas as dependências (cria o venv) | `poetry install --with dev,docs` |
| Sincronizar exatamente com o lock | `poetry sync --with dev,docs` |

### 8.3 Ambiente virtual e dependências

| Objetivo | Comando |
|---------|---------|
| Ativar o ambiente (Linux/macOS) | `eval "$(poetry env activate)"` |
| Ativar o ambiente (Windows/PowerShell) | `Invoke-Expression (poetry env activate)` |
| Executar sem ativar | `poetry run <comando>` |
| Adicionar dependência de produção | `poetry add <pacote>` |
| Adicionar dependência de desenvolvimento | `poetry add --group dev <pacote>` |
| Adicionar dependência de documentação | `poetry add --group docs <pacote>` |
| Remover dependência | `poetry remove <pacote>` |
| Atualizar o lock após editar o `pyproject.toml` | `poetry lock` |
| Listar dependências | `poetry show --tree` |

Instalação inicial das ferramentas obrigatórias:

```bash
poetry add --group dev ruff pytest pytest-cov
poetry add --group docs mkdocs-material "mkdocstrings[python]"
```

### 8.4 Qualidade, testes e documentação

| Objetivo | Comando |
|---------|---------|
| Lint (análise estática) | `poetry run ruff check .` |
| Lint com correção automática | `poetry run ruff check . --fix` |
| Formatar o código | `poetry run ruff format .` |
| Verificar a formatação sem alterar arquivos | `poetry run ruff format --check .` |
| Executar os testes (com cobertura e limite de 50%) | `poetry run pytest` |
| Executar um arquivo ou teste específico | `poetry run pytest tests/unit/test_x.py::test_y -v` |
| Relatório de cobertura no terminal | `poetry run pytest --cov-report=term-missing` |
| Relatório de cobertura em HTML (`htmlcov/`) | `poetry run pytest --cov-report=html` |
| Relatório de cobertura em XML (CI) | `poetry run pytest --cov-report=xml` |
| Iniciar a documentação localmente | `poetry run mkdocs serve` → http://127.0.0.1:8000 |
| Gerar a documentação estática (`site/`) | `poetry run mkdocs build --strict` |
| Executar o projeto | `poetry run python -m projeto` ou `poetry run projeto` |

### 8.5 Pipeline de validação local (executar antes de concluir qualquer tarefa)

```bash
poetry check --lock \
  && poetry run ruff check . \
  && poetry run ruff format --check . \
  && poetry run pytest \
  && poetry run mkdocs build --strict
```

No PowerShell 5.1 (sem `&&`):

```powershell
poetry check --lock; if ($?) { poetry run ruff check . }; if ($?) { poetry run ruff format --check . }; if ($?) { poetry run pytest }; if ($?) { poetry run mkdocs build --strict }
```

A tarefa **só está concluída** se todos os comandos terminarem com sucesso.

---

## 9. Documentação técnica

### 9.1 Conteúdo obrigatório

| Página | Conteúdo |
|--------|----------|
| `docs/index.md` | Finalidade do projeto, problema que resolve, visão geral das funcionalidades e links para as demais seções |
| `docs/instalacao.md` | Pré-requisitos (pyenv, Poetry), configuração da versão do Python e instalação das dependências |
| `docs/uso.md` | Como executar o projeto, parâmetros, variáveis de ambiente e exemplos |
| `docs/testes.md` | Como executar os testes, gerar os relatórios de cobertura e interpretar o limite mínimo |
| `docs/arquitetura.md` | Estrutura de módulos, fluxo de dados, responsabilidades das camadas e decisões técnicas |
| `docs/referencia/api.md` | Principais classes, funções e módulos (gerado com mkdocstrings a partir das docstrings) |

### 9.2 `README.md`

Deve conter, de forma resumida: descrição do projeto, pré-requisitos, instalação rápida, como executar, como testar, como abrir a documentação localmente e um link para a documentação completa.

### 9.3 Manutenção

- Atualizar a documentação **na mesma entrega** da mudança que a motivou.
- `mkdocs build --strict` deve passar sem avisos (links quebrados ou referências inválidas fazem o build falhar).

---

## 10. Critérios obrigatórios de qualidade

Um projeto só é considerado conforme quando atende **todos** os critérios:

1. ✅ Ambiente Python configurado pelo **pyenv**, com `.python-version` versionado.
2. ✅ Dependências e ferramentas gerenciadas pelo **Poetry**, com `poetry.lock` versionado e sincronizado.
3. ✅ **Ruff** configurado no `pyproject.toml`, com lint e formatação passando sem erros.
4. ✅ **Pytest** configurado, com testes em `tests/` que validam resultados.
5. ✅ Cobertura **≥ 50%** de `src/projeto/`, com falha automática abaixo desse limite.
6. ✅ Documentação em **MkDocs Material**, com `index.md`, `mkdocs.yml` e build estrito passando.
7. ✅ Código **organizado, modular, tipado** e de fácil manutenção.
8. ✅ **Nenhuma instalação global** das dependências do projeto.

---

## 11. Checklist de validação final

Antes de considerar um projeto (ou uma tarefa) concluído, confirme cada item:

### Ambiente
- [ ] `.python-version` existe, está versionado e corresponde a `pyenv version`.
- [ ] `requires-python` no `pyproject.toml` é compatível com a versão do `.python-version`.
- [ ] O ambiente virtual é o do Poetry (`poetry env info`).
- [ ] `poetry check --lock` passa.
- [ ] Nenhuma ferramenta do projeto foi instalada globalmente.

### Dependências
- [ ] Toda nova dependência foi adicionada com `poetry add` no grupo correto (principal, `dev` ou `docs`).
- [ ] `poetry.lock` foi atualizado e versionado.

### Qualidade de código
- [ ] `poetry run ruff check .` sem erros.
- [ ] `poetry run ruff format --check .` sem pendências.
- [ ] Nenhum `# noqa` sem justificativa.
- [ ] Funções e métodos públicos com type hints e docstrings.

### Testes
- [ ] Funcionalidades novas ou alteradas têm testes correspondentes.
- [ ] Os testes cobrem cenários positivos, negativos, exceções e casos extremos.
- [ ] Todos os testes têm asserções significativas.
- [ ] `poetry run pytest` passa, com cobertura ≥ 50% em `src/projeto/`.

### Documentação
- [ ] `docs/index.md` e as demais páginas obrigatórias estão atualizadas.
- [ ] A referência da API reflete as classes e funções atuais.
- [ ] `README.md` está atualizado.
- [ ] `poetry run mkdocs build --strict` passa.

### Estrutura e versionamento
- [ ] A estrutura segue a seção 5 (ou a adaptação está justificada).
- [ ] `.gitignore` cobre `.venv/`, caches, `htmlcov/`, `site/` e `.env`.
- [ ] Nenhum segredo ou credencial foi versionado.

### Comunicação (agente de IA)
- [ ] Os resultados reais do pipeline de validação foram reportados.
- [ ] Requisitos não atendidos foram informados claramente, com motivo e alternativa.
- [ ] Nenhuma configuração obrigatória foi alterada sem justificativa e autorização.

---

## 12. Exceções e desvios

Quando um requisito não puder ser cumprido (ex.: ferramenta indisponível no ambiente, conflito de versões, restrição da plataforma), o agente deve:

1. **Interromper** a etapa afetada em vez de contornar a regra silenciosamente.
2. **Informar** o requisito afetado, a causa técnica e o impacto.
3. **Propor** uma alternativa compatível com esta Skill.
4. **Aguardar autorização** antes de aplicar qualquer desvio permanente.
5. **Registrar** o desvio aprovado na documentação do projeto (ex.: `docs/arquitetura.md`, seção "Decisões técnicas").
