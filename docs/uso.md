# Uso

## Linha de comando

```text
poetry run formula1 [--log-level {DEBUG,INFO,WARNING,ERROR}] extract
    --year ANO
    [--endpoints LISTA]
    [--session-type TIPO ...]
    [--force]
    [--data-dir DIR]
    [--request-interval SEGUNDOS]
```

O mesmo comando também roda com `poetry run python -m formula1 ...`.

| Parâmetro | Obrigatório | Descrição |
|---|---|---|
| `--year` | sim | Temporada, a partir de **2023** |
| `--endpoints` | não | Lista separada por vírgulas. Se omitido, usa os endpoints padrão (tabela abaixo) |
| `--session-type` | não | Filtra por `session_type` **ou** `session_name`, sem diferenciar maiúsculas. Pode ser repetido ou separado por vírgulas: `--session-type Race,Qualifying` |
| `--force` | não | Reextrai as partições que já existem |
| `--data-dir` | não | Diretório de saída. Tem prioridade sobre `F1_DATA_DIR` |
| `--request-interval` | não | Pausa mínima entre requisições, em segundos (padrão `0.5`) |
| `--log-level` | não | Nível de log (padrão `INFO`), informado **antes** de `extract` |

O código de saída é `0` quando não há falhas e `1` quando pelo menos uma
partição falhou. As falhas aparecem no resumo final do log.

### Exemplos

```bash
# Corridas (GP e Sprint) de 2023, só voltas e stints
poetry run formula1 extract --year 2023 --session-type Race --endpoints laps,stints

# Temporada 2024 completa, com os endpoints padrão
poetry run formula1 extract --year 2024

# Classificações de 2024, regravando o que já existe
poetry run formula1 extract --year 2024 --session-type Qualifying --force

# Telemetria (alto volume) das corridas de 2024, em outro diretório
poetry run formula1 extract --year 2024 --session-type Race --endpoints car_data --data-dir D:/f1
```

!!! tip "Sprint é `Race`"
    Na OpenF1, a Sprint tem `session_type = "Race"` e `session_name = "Sprint"`.
    Use `--session-type Race` para GP e Sprint, ou `--session-type "Sprint"` só
    para as Sprints.

## Endpoints

| Endpoint | Padrão | Observação |
|---|:---:|---|
| `meetings` | ✅ | Catálogo da temporada, regravado a cada execução |
| `sessions` | ✅ | Catálogo de cada fim de semana, regravado a cada execução |
| `drivers` | ✅ | Remove o campo depreciado `country_code` |
| `laps` | ✅ | Mini-setores como `list<int64>` |
| `stints` | ✅ | |
| `pit` | ✅ | Remove o campo depreciado `pit_duration` (use `lane_duration`) |
| `position` | ✅ | |
| `intervals` | ✅ | Só em corridas. Gera colunas `*_seconds` e `*_laps_behind` |
| `race_control` | ✅ | |
| `weather` | ✅ | |
| `session_result` | ✅ | Explode Q1/Q2/Q3 e gera colunas de gap |
| `starting_grid` | ✅ | |
| `car_data` | — | ~3,7 Hz, alto volume. Extraído piloto a piloto |
| `location` | — | ~3,7 Hz, alto volume. Extraído piloto a piloto |
| `team_radio` | — | Cobertura limitada |
| `overtakes` | — | Só em corridas. Pode estar incompleto |
| `championship_drivers` | — | Beta. Só em corridas |
| `championship_teams` | — | Beta. Só em corridas |

Os endpoints marcados como "só em corridas" são pulados nas sessões que não
são `Race`, e esses pulos aparecem no resumo.

## Variáveis de ambiente

| Variável | Padrão | Descrição |
|---|---|---|
| `F1_DATA_DIR` | `./data` | Diretório raiz dos dados. O padrão `data/` está no `.gitignore` |

## Onde ficam os dados

```text
$F1_DATA_DIR/
├── raw/                                   # JSON exatamente como veio da API
│   ├── meetings/year=2023.json
│   ├── sessions/year=2023/meeting_key=1141.json
│   └── laps/year=2023/meeting_key=1141/session_key=7953.json
└── processed/                             # Parquet normalizado (particionamento Hive)
    ├── meetings/year=2023/part.parquet
    ├── sessions/year=2023/meeting_key=1141/part.parquet
    └── laps/year=2023/meeting_key=1141/session_key=7953/part.parquet
```

- O **JSON bruto** é gravado sempre, mesmo quando a API não devolve registros.
  É ele que marca a partição como concluída (idempotência).
- O **Parquet** só é gravado quando há registros.
- As colunas de partição (`year`, `meeting_key`, `session_key`) **não ficam
  dentro** do Parquet: o leitor as reconstrói a partir do caminho.

## Lendo os dados com pandas

```python
import pandas as pd

# Todas as voltas extraídas (todas as temporadas e sessões)
laps = pd.read_parquet("data/processed/laps")

# Só uma temporada ou sessão, lendo apenas as partições necessárias
laps_2023 = pd.read_parquet("data/processed/laps", filters=[("year", "=", 2023)])
race = pd.read_parquet(
    "data/processed/laps", filters=[("session_key", "=", 7953)]
)

# Juntar com pilotos e sessões
drivers = pd.read_parquet("data/processed/drivers")
sessions = pd.read_parquet("data/processed/sessions")

laps = laps.astype({"session_key": "int64"})
drivers = drivers.astype({"session_key": "int64"})
sessions = sessions.astype({"meeting_key": "int64"})

best = (
    laps.dropna(subset=["lap_duration"])
    .merge(drivers[["session_key", "driver_number", "name_acronym"]],
           on=["session_key", "driver_number"])
    .groupby(["session_key", "name_acronym"])["lap_duration"].min()
)
```

!!! note "Colunas de partição como `category`"
    Ao ler um diretório particionado, `year`, `meeting_key` e `session_key`
    chegam como `category`. Converta com `.astype("int64")` antes de fazer joins.

### Tipos das colunas

| Tipo pandas | Colunas |
|---|---|
| `datetime64[..., UTC]` | `date`, `date_start`, `date_end` |
| `Int64` (anulável) | chaves, `driver_number`, `lap_number`, `position`, velocidades, `n_gear`, `drs`... |
| `float64` | durações, temperaturas, pontos, gaps convertidos |
| `boolean` (anulável) | `is_pit_out_lap`, `is_cancelled`, `dnf`, `dns`, `dsq` |
| `string` | textos e o valor original dos gaps |
| `object` (lista) | `segments_sector_1..3` |

### Gaps (`intervals` e `session_result`)

A API envia os gaps como segundos, `"+N LAP(S)"` ou `null` (líder). O pipeline
mantém o valor original como texto e cria duas colunas:

| Valor original | `<campo>_seconds` | `<campo>_laps_behind` |
|---|---|---|
| `null` (líder) | `NaN` | `<NA>` |
| `11.987` ou `"+11.987"` | `11.987` | `0` |
| `"+1 LAP"` | `NaN` | `1` |
| `"+3 LAPS"` | `NaN` | `3` |

Em `intervals`, isso vale para `gap_to_leader` e `interval`. Em
`session_result`, vale para `gap_to_leader`. Na classificação, `duration` e
`gap_to_leader` são arrays e viram `duration_q1..q3` e `gap_to_leader_q1..q3`.
Nesse caso, `duration` fica `NaN`.
