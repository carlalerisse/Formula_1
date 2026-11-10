# Arquitetura

## Estrutura de módulos

```text
src/formula1/
├── __main__.py              # CLI (argparse): formula1 extract ...
├── config.py                # URL base, timeouts, retries, pausa, F1_DATA_DIR
├── domain/                  # Regras puras, sem I/O
│   ├── endpoints.py         # Registro dos endpoints e tabelas de tipos das colunas
│   ├── transform.py         # Normalização: registros JSON → DataFrame tipado
│   └── analytics.py         # Análises (sessão e ranking de voltas por circuito)
├── adapters/                # I/O
│   ├── openf1_client.py     # Cliente HTTP: filtros com operadores, retry e pausa
│   └── storage.py           # JSON bruto e Parquet particionado
├── services/
│   └── pipeline.py          # Orquestração: ano → meetings → sessions → endpoints
└── dashboard/               # Interface Streamlit (somente leitura do Parquet)
    ├── data.py              # Descoberta de temporadas/sessões e leitura das partições
    ├── charts.py            # Gráficos Altair
    ├── fastest_laps.py      # Visão inicial: top 5 voltas por circuito
    └── app.py               # App: streamlit run src/formula1/dashboard/app.py
```

| Camada | Responsabilidade | Depende de |
|---|---|---|
| `domain` | Saber **o que** cada endpoint contém, **como** normalizá-lo e analisá-lo | pandas |
| `adapters` | Falar com o mundo externo (HTTP e disco) | httpx, pyarrow, `domain` |
| `services` | Orquestrar o fluxo e isolar falhas | `adapters`, `domain` |
| `__main__` | Traduzir argumentos da CLI em uma execução | todas |
| `dashboard` | Apresentar os dados extraídos (ver [Dashboard](dashboard.md)) | streamlit, altair, `adapters`, `domain` |

O `domain` não faz I/O, por isso a transformação é testada só com listas de
dicionários. O pipeline depende de um `Protocol` (`OpenF1Source`), e não da
classe concreta do cliente. Assim, os testes injetam um cliente falso.

## Fluxo de dados

```text
                 ┌──────────────── OpenF1Client ────────────────┐
formula1 extract │ GET meetings?year=Y                           │
   --year Y ───► │ GET sessions?meeting_key=M   (por meeting)    │
                 │ GET <endpoint>?session_key=S (por sessão)     │
                 └──────────────────────┬────────────────────────┘
                                        │ list[dict]
                     Storage.save_raw ◄─┤
                                        ▼
                         transform.to_dataframe (domain)
                                        │ DataFrame tipado
                                        ▼
                             Storage.save_parquet
```

Para cada sessão e endpoint, o pipeline faz:

1. **pula** a partição se o endpoint for só de corrida e a sessão não for `Race`;
2. **pula** a partição se o JSON bruto já existir (a menos que se use `--force`);
3. **extrai** os registros (os endpoints de alto volume são buscados piloto a piloto);
4. **transforma** e grava o Parquet (só quando há registros);
5. grava o **JSON bruto** por último, marcando a partição como concluída.

Se os passos 3 ou 4 falharem, a falha entra no `PipelineReport` e no log, e o
lote continua. Como o JSON bruto não foi gravado, a próxima execução tenta de novo.

## Decisões técnicas

| Tema | Decisão | Motivo |
|---|---|---|
| Nome do pacote | `formula1` | O `poetry new` gerou `f_rmula_1` ao remover o acento do nome do diretório |
| Python | 3.12.10, `requires-python = ">=3.12,<3.13"` | Alinhado ao `.python-version`. O valor gerado (`>=3.14`) conflitava com ele |
| HTTP | `httpx` | Traz `MockTransport` para testar sem rede e sem dependências extras |
| Query string | Montada manualmente | Dicionários de `params` não aceitam operadores como `>=` |
| Retry | Backoff exponencial (1, 2, 4, 8, 16 s) em 429, 5xx e falhas de rede, respeitando `Retry-After` (teto de 60 s) | A API não publica rate limit. Na prática, devolve 429 com `Retry-After: 60` |
| Pausa entre chamadas | 0,5 s (configurável) | Reduz os 429 sem deixar a extração lenta demais |
| 404 "No results found" | Vira lista vazia | É como a API responde a um filtro sem resultados. Os demais 404 continuam virando `OpenF1Error` |
| Alto volume | `car_data` e `location` piloto a piloto e fora do padrão | Uma sessão inteira a ~3,7 Hz é grande demais para uma única resposta |
| Idempotência | Baseada na existência do JSON bruto | Funciona inclusive para sessões sem dados, que não geram Parquet |
| Catálogos | `meetings` e `sessions` são sempre consultados e regravados | Guiam a iteração e mudam ao longo da temporada |
| Particionamento | Hive (`year=/meeting_key=/session_key=`), sem as colunas de partição dentro do arquivo | Evita conflito de tipos (`int32` inferido do caminho × `int64` do arquivo) na leitura do dataset |
| Schema estável | Todas as colunas documentadas sempre presentes, com tipos fixos (`Int64`, `float64`, `boolean`, `string`, `list<int64>`) | Partições com colunas inteiramente nulas não podem gerar tipos diferentes no Parquet |
| Gaps | `<campo>_seconds` + `<campo>_laps_behind`, e o original como texto | `intervals` tem dois campos de gap. Uma coluna não pode misturar número e `"+1 LAP"` |
| Gravação | Atômica (arquivo temporário + `replace`) | Uma interrupção não deixa arquivos corrompidos nem marca partições como concluídas |
| Dashboard | Streamlit + Altair (Altair declarado explicitamente, pois é importado direto) | App Python local, sem front-end separado. Testável com `streamlit.testing.AppTest` |
| Leitura no dashboard | Partição a partição, por caminho direto | Mais rápido que varrer o dataset e evita conflitos de schema entre temporadas |
| Dependency groups | `[dependency-groups]` (PEP 735) no `pyproject.toml` | É o formato que o Poetry 2.x grava com `poetry add --group`. Equivale ao `[tool.poetry.group.*]` do modelo da skill |

### Desvios do plano original

- **Nomes das colunas de gap:** o plano previa `gap_seconds` e `laps_behind`.
  Como `intervals` tem dois campos de gap (`gap_to_leader` e `interval`), as
  colunas recebem o prefixo do campo (`gap_to_leader_seconds`,
  `interval_laps_behind`...).
- **404:** o plano previa que todo 404 fosse erro. A exceção "No results found"
  foi adicionada depois de confirmar que é assim que a API sinaliza um
  resultado vazio.

## Limitações conhecidas

- A cobertura da OpenF1 começa em 2023. Anos anteriores são rejeitados pela CLI.
- `pit.stop_duration` só existe a partir do GP dos EUA de 2024. Antes disso, a
  coluna fica nula.
- `overtakes` pode estar incompleto, e `championship_*` está em beta.
- Os mini-setores de `laps` não são publicados em corridas (listas nulas).
- Os campos depreciados `drivers.country_code` e `pit.pit_duration` são
  descartados, porque serão removidos pela API no fim de 2026.
- Dados em tempo real (pagos, MQTT/WebSocket) estão fora do escopo.
