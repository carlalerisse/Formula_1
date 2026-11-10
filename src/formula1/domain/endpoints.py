"""Registro dos endpoints da OpenF1 e das regras de tipagem das colunas."""

from dataclasses import dataclass

_KEYS: tuple[str, ...] = ("meeting_key", "session_key")


@dataclass(frozen=True)
class EndpointSpec:
    """Descrição de um endpoint da OpenF1.

    Attributes:
        name: Nome do endpoint na URL (ex.: ``laps``).
        columns: Colunas documentadas, sempre presentes no DataFrame final.
        race_only: Se ``True``, o endpoint só tem dados em sessões de corrida.
        per_driver: Se ``True``, a extração é feita piloto a piloto, porque o
            volume de uma sessão inteira é alto demais para uma requisição.
        deprecated: Campos depreciados pela API, removidos na transformação.
    """

    name: str
    columns: tuple[str, ...]
    race_only: bool = False
    per_driver: bool = False
    deprecated: tuple[str, ...] = ()


_SPECS: tuple[EndpointSpec, ...] = (
    EndpointSpec(
        "meetings",
        (
            "meeting_key",
            "meeting_name",
            "meeting_official_name",
            "year",
            "date_start",
            "date_end",
            "gmt_offset",
            "location",
            "country_name",
            "country_code",
            "country_key",
            "country_flag",
            "circuit_key",
            "circuit_short_name",
            "circuit_type",
            "circuit_image",
            "circuit_info_url",
            "is_cancelled",
        ),
    ),
    EndpointSpec(
        "sessions",
        (
            *_KEYS,
            "year",
            "session_name",
            "session_type",
            "date_start",
            "date_end",
            "gmt_offset",
            "location",
            "country_name",
            "country_code",
            "country_key",
            "circuit_key",
            "circuit_short_name",
            "is_cancelled",
        ),
    ),
    EndpointSpec(
        "drivers",
        (
            *_KEYS,
            "driver_number",
            "first_name",
            "last_name",
            "full_name",
            "broadcast_name",
            "name_acronym",
            "team_name",
            "team_colour",
            "headshot_url",
        ),
        deprecated=("country_code",),
    ),
    EndpointSpec(
        "car_data",
        (
            *_KEYS,
            "date",
            "driver_number",
            "speed",
            "rpm",
            "n_gear",
            "throttle",
            "brake",
            "drs",
        ),
        per_driver=True,
    ),
    EndpointSpec(
        "location",
        (*_KEYS, "date", "driver_number", "x", "y", "z"),
        per_driver=True,
    ),
    EndpointSpec(
        "laps",
        (
            *_KEYS,
            "driver_number",
            "lap_number",
            "date_start",
            "lap_duration",
            "duration_sector_1",
            "duration_sector_2",
            "duration_sector_3",
            "i1_speed",
            "i2_speed",
            "st_speed",
            "is_pit_out_lap",
            "segments_sector_1",
            "segments_sector_2",
            "segments_sector_3",
        ),
    ),
    EndpointSpec(
        "intervals",
        (*_KEYS, "date", "driver_number", "gap_to_leader", "interval"),
        race_only=True,
    ),
    EndpointSpec("position", (*_KEYS, "date", "driver_number", "position")),
    EndpointSpec(
        "pit",
        (
            *_KEYS,
            "date",
            "driver_number",
            "lap_number",
            "lane_duration",
            "stop_duration",
        ),
        deprecated=("pit_duration",),
    ),
    EndpointSpec(
        "stints",
        (
            *_KEYS,
            "driver_number",
            "stint_number",
            "lap_start",
            "lap_end",
            "compound",
            "tyre_age_at_start",
        ),
    ),
    EndpointSpec(
        "race_control",
        (
            *_KEYS,
            "date",
            "driver_number",
            "lap_number",
            "category",
            "flag",
            "scope",
            "sector",
            "qualifying_phase",
            "message",
        ),
    ),
    EndpointSpec(
        "weather",
        (
            *_KEYS,
            "date",
            "air_temperature",
            "track_temperature",
            "humidity",
            "pressure",
            "rainfall",
            "wind_direction",
            "wind_speed",
        ),
    ),
    EndpointSpec(
        "team_radio",
        (*_KEYS, "date", "driver_number", "recording_url"),
    ),
    EndpointSpec(
        "overtakes",
        (
            *_KEYS,
            "date",
            "overtaking_driver_number",
            "overtaken_driver_number",
            "position",
        ),
        race_only=True,
    ),
    EndpointSpec(
        "session_result",
        (
            *_KEYS,
            "driver_number",
            "position",
            "number_of_laps",
            "duration",
            "gap_to_leader",
            "dnf",
            "dns",
            "dsq",
        ),
    ),
    EndpointSpec(
        "starting_grid",
        (*_KEYS, "driver_number", "position", "lap_duration"),
    ),
    EndpointSpec(
        "championship_drivers",
        (
            *_KEYS,
            "driver_number",
            "points_start",
            "points_current",
            "position_start",
            "position_current",
        ),
        race_only=True,
    ),
    EndpointSpec(
        "championship_teams",
        (
            *_KEYS,
            "team_name",
            "points_start",
            "points_current",
            "position_start",
            "position_current",
        ),
        race_only=True,
    ),
)

ENDPOINTS: dict[str, EndpointSpec] = {spec.name: spec for spec in _SPECS}
"""Todos os endpoints históricos suportados, indexados pelo nome."""

CATALOG_ENDPOINTS: tuple[str, ...] = ("meetings", "sessions")
"""Endpoints de catálogo, consultados por ano/evento e não por sessão."""

DEFAULT_ENDPOINTS: tuple[str, ...] = (
    "meetings",
    "sessions",
    "drivers",
    "laps",
    "stints",
    "pit",
    "position",
    "intervals",
    "race_control",
    "weather",
    "session_result",
    "starting_grid",
)
"""Endpoints extraídos quando ``--endpoints`` não é informado."""

RACE_SESSION_TYPE: str = "Race"
"""Valor de ``session_type`` das corridas (inclui a Sprint)."""

DATE_COLUMNS: frozenset[str] = frozenset({"date", "date_start", "date_end"})
"""Colunas convertidas para ``datetime`` em UTC."""

INT_COLUMNS: frozenset[str] = frozenset(
    {
        "meeting_key",
        "session_key",
        "driver_number",
        "year",
        "circuit_key",
        "country_key",
        "lap_number",
        "position",
        "stint_number",
        "lap_start",
        "lap_end",
        "tyre_age_at_start",
        "speed",
        "rpm",
        "n_gear",
        "throttle",
        "brake",
        "drs",
        "x",
        "y",
        "z",
        "i1_speed",
        "i2_speed",
        "st_speed",
        "number_of_laps",
        "sector",
        "qualifying_phase",
        "overtaking_driver_number",
        "overtaken_driver_number",
        "position_start",
        "position_current",
        "rainfall",
        "wind_direction",
    }
)
"""Colunas inteiras (``Int64`` anulável; viram ``float64`` se houver frações)."""

FLOAT_COLUMNS: frozenset[str] = frozenset(
    {
        "lap_duration",
        "duration_sector_1",
        "duration_sector_2",
        "duration_sector_3",
        "lane_duration",
        "stop_duration",
        "duration",
        "air_temperature",
        "track_temperature",
        "humidity",
        "pressure",
        "wind_speed",
        "points_start",
        "points_current",
    }
)
"""Colunas numéricas de ponto flutuante."""

BOOL_COLUMNS: frozenset[str] = frozenset(
    {"is_cancelled", "is_pit_out_lap", "dnf", "dns", "dsq"}
)
"""Colunas booleanas (``boolean`` anulável)."""

INT_LIST_COLUMNS: frozenset[str] = frozenset(
    {"segments_sector_1", "segments_sector_2", "segments_sector_3"}
)
"""Colunas com listas de inteiros (mini-setores de ``laps``)."""


def get_endpoint(name: str) -> EndpointSpec:
    """Retorna a especificação de um endpoint.

    Args:
        name: Nome do endpoint (ex.: ``laps``).

    Returns:
        A especificação registrada.

    Raises:
        ValueError: Se o endpoint não for suportado.
    """
    try:
        return ENDPOINTS[name]
    except KeyError:
        valid = ", ".join(sorted(ENDPOINTS))
        msg = f"Endpoint desconhecido: {name!r}. Válidos: {valid}"
        raise ValueError(msg) from None


def parse_endpoints(value: str | None) -> tuple[str, ...]:
    """Converte uma lista separada por vírgulas em nomes de endpoints válidos.

    Args:
        value: Texto como ``"laps,stints"``. Vazio ou ``None`` usa o padrão.

    Returns:
        Os endpoints na ordem informada, sem repetições.

    Raises:
        ValueError: Se algum endpoint não for suportado.
    """
    if value is None or not value.strip():
        return DEFAULT_ENDPOINTS
    names = [item.strip() for item in value.split(",") if item.strip()]
    for name in names:
        get_endpoint(name)
    return tuple(dict.fromkeys(names))


def is_race(session_type: str | None) -> bool:
    """Indica se uma sessão é de corrida (Grande Prêmio ou Sprint).

    Args:
        session_type: Valor do campo ``session_type`` da sessão.

    Returns:
        ``True`` para sessões do tipo ``Race``.
    """
    return session_type == RACE_SESSION_TYPE
