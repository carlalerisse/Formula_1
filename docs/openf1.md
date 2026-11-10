# OpenF1 API: resumo

> Fonte: <https://openf1.org/docs/#api-endpoints> e <https://openf1.org/auth.html>.
> A OpenF1 é um projeto **não oficial**, sem vínculo com as empresas da Fórmula 1.

---

## 1. Visão geral

| Item | Valor |
|---|---|
| URL base | `https://api.openf1.org/v1/<endpoint>` |
| Dados históricos | De **2023 em diante**, **gratuitos** e **sem autenticação** |
| Dados em tempo real | Exigem **assinatura paga** e autenticação (ver seção 6) |
| Formato padrão | JSON |
| Formato alternativo | CSV, adicionando `csv=true` à query |
| Limites de taxa | A página não dá números. Com autenticação, o limite é maior. |
| Preços | Não informados na documentação |

---

## 2. Formatos e filtros

- **CSV:** `https://api.openf1.org/v1/sessions?year=2023&csv=true`
- **Filtro por atributo:** coloque o atributo na query string. Qualquer atributo pode ser filtrado, **menos arrays**.
- **Operadores:** `=`, `>`, `>=`, `<`, `<=`
  - Exemplos: `lap_duration>=120`, `position<=3`, `interval>0`
  - Também podem ir codificados na URL, por exemplo `%3E%3D` para `>=`.
- **Vários valores:** repita a chave, como em `driver_number=4&driver_number=81`.
- **Datas:**
  - Intervalo: `date>=2023-09-01&date<2023-09-30`.
  - A API aceita formatos que o `dateutil.parser.parse` do Python entende, como `2021-09-10T14:30:20+00:00` ou `10 September 2021`.
  - Todas as datas estão em **UTC**.
- **`latest`:** use `session_key=latest` ou `meeting_key=latest` para pegar a sessão ou o evento mais recente.
- **Espaços:** codifique como `%20`, por exemplo `session_name=Sprint%20Qualifying`.

---

## 3. Chaves e hierarquia dos dados

```
meeting (fim de semana de GP ou testes)   -> meeting_key
  └── session (TL1, Quali, Sprint, Corrida...)   -> session_key
        └── dados por piloto   -> driver_number
              (car_data, laps, pit, stints, position, location...)
```

- **`meeting_key`** identifica o fim de semana.
- **`session_key`** identifica cada sessão.
- **`driver_number`** é o número do carro.
- Quase todos os endpoints trazem `meeting_key` e `session_key`, o que permite cruzar os dados (joins).

---

## 4. Tabela-resumo dos endpoints

| Endpoint | Descrição | Frequência / observação |
|---|---|---|
| `meetings` | Fins de semana de GP ou testes | Atualizado diariamente à 00:00 UTC |
| `sessions` | Sessões de um fim de semana | Atualizado diariamente à 00:00 UTC |
| `drivers` | Pilotos de uma sessão | — |
| `car_data` | Telemetria do carro | ~3,7 Hz |
| `location` | Posição aproximada (x, y, z) na pista | ~3,7 Hz |
| `laps` | Dados de cada volta | — |
| `intervals` | Gap para o líder e para o carro da frente | ~4 s, só em corridas |
| `position` | Posição do piloto ao longo da sessão | — |
| `pit` | Passagens pelo pit lane | — |
| `stints` | Stints e pneus | — |
| `race_control` | Bandeiras, safety car, incidentes | — |
| `weather` | Clima na pista | A cada minuto |
| `team_radio` | Rádio entre piloto e equipe | Cobertura limitada (muito reduzida em 2026) |
| `overtakes` | Ultrapassagens / trocas de posição | Só em corridas; pode estar incompleto |
| `session_result` | Resultado final da sessão | Minutos após o resultado oficial |
| `starting_grid` | Grid de largada | Minutos após o resultado oficial |
| `championship_drivers` | Campeonato de pilotos (**beta**) | Só sessões de corrida |
| `championship_teams` | Campeonato de construtores (**beta**) | Só sessões de corrida |

---

## 5. Detalhe por endpoint

### `meetings`

Um fim de semana de GP ou de testes.

- **Campos:**
  - Identificação: `meeting_key`, `meeting_name`, `meeting_official_name`, `year`
  - Datas: `date_start`, `date_end`, `gmt_offset`
  - Local: `location`, `country_name`, `country_code`, `country_key`, `country_flag`
  - Circuito: `circuit_key`, `circuit_short_name`, `circuit_type` (Permanent / Temporary - Street / Temporary - Road), `circuit_image`, `circuit_info_url`
  - Outros: `is_cancelled`
- **Exemplo:** `https://api.openf1.org/v1/meetings?year=2026&country_name=Singapore`

### `sessions`

Cada sessão do fim de semana.

- **Campos:**
  - Identificação: `session_key`, `meeting_key`, `year`
  - Tipo: `session_name` (Practice 1, Qualifying, Race...), `session_type` (Practice, Qualifying, Race...)
  - Datas: `date_start`, `date_end`, `gmt_offset`
  - Local: `location`, `country_*`, `circuit_key`, `circuit_short_name`
  - Outros: `is_cancelled`
- **Exemplo:** `https://api.openf1.org/v1/sessions?country_name=Belgium&session_name=Sprint%20Qualifying&year=2023`

### `drivers`

Pilotos de uma sessão.

- **Campos:**
  - Número: `driver_number`
  - Nome: `first_name`, `last_name`, `full_name`, `broadcast_name`, `name_acronym` (3 letras)
  - Equipe: `team_name`, `team_colour` (hex), `headshot_url`
  - Depreciado: `country_code`
- **Exemplo:** `https://api.openf1.org/v1/drivers?driver_number=1&session_key=9158`

### `car_data`

Telemetria a cerca de 3,7 Hz.

- **Campos:**
  - `date`, `driver_number`
  - `speed` (km/h), `rpm`, `n_gear` (1–8; 0 = neutro)
  - `throttle` (%)
  - `brake` (0 ou 100)
  - `drs`
- **Exemplo:** `https://api.openf1.org/v1/car_data?driver_number=55&session_key=9159&speed>=315`

| Valor de `drs` | Significado |
|---|---|
| 0, 1 | DRS desligado |
| 8 | Detectado, elegível ao entrar na zona |
| 10, 12, 14 | DRS ligado |
| 2, 3, 9 | Desconhecido |

### `location`

Posição aproximada do carro (x, y, z) a cerca de 3,7 Hz.

- Mostra o progresso ao longo da pista, mas não a posição lateral.
- A origem (0, 0, 0) é arbitrária.
- **Exemplo:** `https://api.openf1.org/v1/location?session_key=9161&driver_number=81&date>2023-09-16T13:03:35.200&date<2023-09-16T13:03:35.800`

### `laps`

Dados de cada volta.

- **Campos:**
  - Volta: `lap_number` (começa em 1), `date_start` (aproximado), `lap_duration`
  - Setores: `duration_sector_1`, `duration_sector_2`, `duration_sector_3`
  - Velocidades: `i1_speed`, `i2_speed` (pontos intermediários), `st_speed` (speed trap)
  - `is_pit_out_lap`
  - Mini-setores: `segments_sector_1`, `segments_sector_2`, `segments_sector_3`
- **Exemplo:** `https://api.openf1.org/v1/laps?session_key=9161&driver_number=63&lap_number=8`

| Valor de segmento | Significado |
|---|---|
| 0 | Indisponível |
| 2048 | Amarelo |
| 2049 | Verde |
| 2051 | Roxo |
| 2064 | Pit lane |
| 2050, 2052, 2068 | Desconhecido |

> Os segmentos não estão disponíveis em corridas, e as cores podem não bater com as da TV.

### `intervals`

Gaps durante a corrida, atualizados a cada ~4 s. Só existe para sessões de corrida.

- **Campos:**
  - `gap_to_leader`
  - `interval` (até o carro da frente)
- Os dois campos vêm em segundos, ou `+1 LAP` se o piloto estiver uma volta atrás. Para o líder, vêm como `null`.
- **Exemplo:** `https://api.openf1.org/v1/intervals?session_key=9165&interval<0.005`

### `position`

Posição do piloto ao longo da sessão, incluindo a posição inicial e cada mudança.

- **Campos:** `date`, `driver_number`, `position`
- **Exemplo:** `https://api.openf1.org/v1/position?meeting_key=1217&driver_number=40&position<=3`

### `pit`

Passagens pelo pit lane.

- **Campos:**
  - `date`, `lap_number`
  - `lane_duration` (tempo no pit lane)
  - `stop_duration` (tempo parado)
  - `pit_duration` (depreciado, igual a `lane_duration`)
- **Exemplo:** `https://api.openf1.org/v1/pit?session_key=9877&stop_duration<2.3`

### `stints`

Períodos de pilotagem contínua.

- **Campos:**
  - `stint_number`, `lap_start`, `lap_end`
  - `compound` (SOFT, MEDIUM, HARD...)
  - `tyre_age_at_start` (voltas que o pneu já tinha no início do stint)
- **Exemplo:** `https://api.openf1.org/v1/stints?session_key=9165&tyre_age_at_start>=3`

### `race_control`

Mensagens da direção de prova.

- **Campos:**
  - `category` (SessionStatus, CarEvent, Drs, Flag, SafetyCar...)
  - `flag` (GREEN, YELLOW, DOUBLE YELLOW, CHEQUERED...)
  - `scope` (Track, Driver, Sector...)
  - `sector`, `lap_number`, `qualifying_phase`
  - `message`, `driver_number`
- **Exemplo:** `https://api.openf1.org/v1/race_control?flag=BLACK%20AND%20WHITE&driver_number=1&date>=2023-01-01&date<2023-09-01`

### `weather`

Clima na pista, atualizado a cada minuto.

- **Campos:**
  - `air_temperature`, `track_temperature` (°C)
  - `humidity` (%)
  - `pressure` (mbar)
  - `rainfall`
  - `wind_direction` (0–359°), `wind_speed` (m/s)
- **Exemplo:** `https://api.openf1.org/v1/weather?meeting_key=1208&wind_direction>=130&track_temperature>=52`

### `team_radio`

Rádio entre piloto e equipe, com apenas uma seleção das mensagens.

- **Campos:** `date`, `driver_number`, `recording_url` (link do áudio)
- **Exemplo:** `https://api.openf1.org/v1/team_radio?session_key=9158&driver_number=11`

### `overtakes`

Trocas de posição em corrida. Inclui as causadas por pit stops e por punições.

- **Campos:**
  - `overtaking_driver_number`, `overtaken_driver_number`
  - `position` (posição de quem ultrapassou, depois da manobra)
  - `date`
- **Exemplo:** `https://api.openf1.org/v1/overtakes?session_key=9636&overtaking_driver_number=63&overtaken_driver_number=4&position=1`

### `session_result`

Classificação final da sessão.

- **Campos:**
  - `position`, `number_of_laps`
  - `duration`: melhor volta em treinos, tempo total em corridas, ou array Q1/Q2/Q3 na classificação
  - `gap_to_leader`: em segundos ou `+N LAP(S)`; array na classificação
  - `dnf`, `dns`, `dsq`
- **Exemplo:** `https://api.openf1.org/v1/session_result?session_key=7782&position<=3`

### `starting_grid`

Grid de largada.

- **Campos:**
  - `position` (posição no grid)
  - `lap_duration` (volta de classificação)
  - `driver_number`
- **Exemplo:** `https://api.openf1.org/v1/starting_grid?session_key=7783&position<=3`

### `championship_drivers` (beta)

Campeonato de pilotos. Só existe para sessões de corrida.

- **Campos:**
  - `points_start`, `points_current` (pontos antes e durante/depois da corrida)
  - `position_start`, `position_current`
- **Exemplo:** `https://api.openf1.org/v1/championship_drivers?session_key=9839&driver_number=4&driver_number=81`

### `championship_teams` (beta)

Campeonato de construtores. Tem os mesmos campos de `championship_drivers`, mas com `team_name` no lugar de `driver_number`.

- **Exemplo:** `https://api.openf1.org/v1/championship_teams?session_key=9839&team_name=McLaren`

---

## 6. Tempo real (autenticado, pago)

1. **Obter o token:** faça um `POST https://api.openf1.org/token` com `username` e `password` em form-encoded.
   - A resposta traz `access_token`, `token_type: bearer` e `expires_in: 3600`, ou seja, o token **expira em 1 h**.
2. **Chamadas REST:** envie o header `Authorization: Bearer <token>`.
3. **Streaming (recomendado para dados ao vivo):**
   - **MQTT:** `mqtt.openf1.org`, porta TLS `8883`, para backends.
   - **WebSocket:** `wss://mqtt.openf1.org:8084/mqtt`, para browsers.
   - **Usuário:** qualquer string não vazia, ou o seu e-mail.
   - **Senha:** o token.
   - **Tópicos:** `v1/<endpoint>`, por exemplo `v1/laps` ou `v1/location`. Use `#` para receber todos.
   - **Mensagens:** o mesmo JSON do REST, mais dois campos:
     - `_id`: inteiro crescente, serve para ordenar.
     - `_key`: o mesmo valor indica uma versão mais nova do mesmo objeto.
4. **Segurança:** faça a troca de credenciais **no backend**. Nunca exponha usuário, senha ou token no front-end.

---

## 7. Limitações e depreciações

- Campos depreciados, que serão **removidos no fim de 2026**:
  - `drivers.country_code`
  - `pit.pit_duration` (use `lane_duration`)
- `pit.stop_duration`:
  - Só existe a partir do **GP dos EUA de 2024**.
  - Em 2026, pode faltar ao vivo e ser preenchido horas depois.
- `team_radio` tem cobertura muito reduzida desde 2026, por limitação da própria F1.
- `overtakes` pode estar incompleto.
- Os segmentos de `laps` não estão disponíveis em corridas.
- `championship_*` está em **beta**.
- A documentação não informa números de rate limit, preços nem termos de uso.

---

## 8. Exemplo rápido em Python

```python
import requests
import pandas as pd

BASE = "https://api.openf1.org/v1"


def get(endpoint: str, **params) -> pd.DataFrame:
    resp = requests.get(f"{BASE}/{endpoint}", params=params, timeout=30)
    resp.raise_for_status()
    return pd.DataFrame(resp.json())


# Corridas de 2024
sessions = get("sessions", year=2024, session_name="Race")

# Voltas do Verstappen (#1) na primeira corrida da lista
session_key = sessions.iloc[0]["session_key"]
laps = get("laps", session_key=session_key, driver_number=1)
print(laps[["lap_number", "lap_duration"]].head())
```

> **Atenção:** operadores como `>=` não cabem num dicionário de `params`. Nesses casos, monte a query manualmente, por exemplo `f"{BASE}/laps?session_key={sk}&lap_duration>=90"`.

---

## 9. Links úteis

- Documentação: <https://openf1.org/docs/>
- Autenticação e streaming: <https://openf1.org/auth.html>
- GitHub: <https://github.com/br-g/openf1>
  - Issues: <https://github.com/br-g/openf1/issues>
  - Discussions: <https://github.com/br-g/openf1/discussions>
