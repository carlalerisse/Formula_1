# Dashboard

Dashboard interativo em [Streamlit](https://streamlit.io/) para explorar os
dados da API OpenF1 que o pipeline gravou em `data/processed/`. Ele só lê
arquivos locais e não faz chamadas à API.

O seletor **Visão**, na barra lateral, alterna entre:

- **Top 5 voltas por circuito** (abre por padrão): as 5 voltas mais rápidas já
  registradas em cada pista, juntando todas as temporadas e sessões extraídas;
- **Análise por sessão**: ritmo, pneus, posições e resultado de uma sessão.

## Como abrir

```bash
poetry run task dashboard
```

Acesse **http://localhost:8501**. O endereço também aparece no terminal. Para
encerrar, use `Ctrl+C`.

O comando equivale a `poetry run streamlit run src/formula1/dashboard/app.py`.
O arquivo `.streamlit/config.toml` deixa o servidor em modo *headless*: ele
não pede e-mail na primeira execução, não abre o navegador sozinho e não envia
estatísticas de uso.

## Dados necessários

O dashboard mostra o que já foi extraído. Para o **top 5 por circuito**, bastam
quatro endpoints. Extraia mais temporadas para ampliar o ranking:

```bash
poetry run formula1 extract --year 2023 --endpoints meetings,sessions,drivers,laps
poetry run formula1 extract --year 2024 --endpoints meetings,sessions,drivers,laps
```

!!! tip "Classificação e treinos"
    Com `--session-type Race`, o ranking só tem voltas de corrida e de sprint.
    As voltas mais rápidas de cada pista costumam sair da classificação: rode a
    extração sem `--session-type` (ou com `--session-type Qualifying`) para
    incluí-las.

Para aproveitar todas as abas da análise por sessão, rode:

```bash
poetry run formula1 extract --year 2023 --session-type Race \
  --endpoints meetings,sessions,drivers,laps,stints,position,pit,session_result
```

| Endpoint | Usado em |
|---|---|
| `meetings`, `sessions` | Nomes legíveis das sessões no seletor. Sem eles, aparecem as chaves numéricas |
| `drivers` | Siglas (VER, HAM...) e cores das equipes. Sem eles, aparece `#número` |
| `laps` | Aba **Ritmo** e os indicadores de volta mais rápida e de número de voltas |
| `stints` | Aba **Pneus** |
| `position` | Aba **Posições** |
| `session_result` | Indicador de vencedor, tabela de resultado e ordem dos pilotos |
| `pit` | Indicador e tabela de pit stops |

Quando falta um endpoint, a aba correspondente diferencia dois casos:

- **não extraído:** mostra o comando exato para extraí-lo;
- **extraído, mas sem registros:** avisa que a própria OpenF1 não tem esse dado
  para a sessão. Por exemplo, `pit` não existe nas corridas de 2023 até Mônaco,
  e `starting_grid` não existe em 2023. Nesses casos, o indicador mostra "—".

## Top 5 voltas por circuito

**Barra lateral:** temporadas, sessões (Race, Sprint, Qualifying, Practice 1...)
e a opção **Só a melhor volta de cada piloto**, que impede um mesmo piloto de
ocupar várias posições do ranking.

**Indicadores:** número de circuitos, voltas extraídas e o piloto com mais
voltas recorde (1º lugar) entre os circuitos.

| Aba | Conteúdo |
|---|---|
| **Por circuito** | Escolha a pista e veja as 5 voltas em ordem, com o tempo, a diferença para a 1ª, o piloto, a equipe, a temporada, o GP, a sessão e o número da volta |
| **Todos os circuitos** | Tabela com uma linha por pista e as colunas 1º a 5º (`VER · 1:29.708 (2023)`) |
| **Pilotos** | Quantas voltas de cada piloto entram no top 5 dos circuitos |

Regras do ranking (`analytics.fastest_laps_by_circuit`):

- só entram voltas com `lap_duration` válido; as voltas de saída do pit ficam de fora;
- o circuito vem de `circuit_short_name` do catálogo `sessions` (com o mesmo
  traçado agrupado ao longo das temporadas). Sem o catálogo, usa o nome do evento;
- siglas e cores vêm do `drivers` de cada sessão. Se faltar o cadastro de uma
  sessão, vale o da sessão mais recente com o mesmo número.

## Análise por sessão

**Barra lateral:** o diretório de dados (padrão `F1_DATA_DIR` ou `./data`), a
temporada, a sessão e os pilotos. Os pilotos vêm na ordem do resultado final.

**Indicadores:** vencedor, volta mais rápida e seu autor, número de voltas e
passagens pelo pit lane.

| Aba | Conteúdo |
|---|---|
| **Ritmo** | Tempo de cada volta por piloto, com zoom e tooltip, e boxplot da distribuição dos tempos, do mais rápido ao mais lento. Por padrão, oculta voltas acima de 107% da mais rápida (safety car, entrada no pit, tráfego) e voltas de saída do pit |
| **Pneus** | Estratégia: um bloco por stint, com as cores convencionais dos compostos (macio vermelho, médio amarelo, duro branco, intermediário verde, chuva azul) |
| **Posições** | Evolução das posições ao longo da sessão, com o 1º lugar no topo |
| **Resultado e pit stops** | Classificação final (com Q1/Q2/Q3 na classificação e DNF/DNS/DSQ) e tabela de pit stops |

## Como funciona

```text
data/processed/*.parquet
        │  dashboard/data.py       descobre temporadas e sessões e lê partições
        ▼
domain/analytics.py                (puro) rótulos, filtros de voltas, stints, resumo,
        │                          ranking das voltas mais rápidas por circuito
        │
        ▼
dashboard/charts.py                gráficos Altair
        │
        ▼
dashboard/app.py                   interface Streamlit (com cache das leituras)
dashboard/fastest_laps.py          visão "Top 5 voltas por circuito"
```

- As sessões disponíveis são descobertas pelas pastas
  `year=/meeting_key=/session_key=`, e cada partição é lida diretamente, sem
  varrer o dataset inteiro.
- As leituras ficam em cache (`st.cache_data`). Depois de extrair dados novos,
  use **Clear cache** no menu do Streamlit (☰), ou tecle `C`, e recarregue a página.
