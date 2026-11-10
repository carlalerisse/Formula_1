"""Regras puras de normalização dos registros da OpenF1 (sem I/O).

A API devolve listas de objetos JSON. Este módulo converte essas listas em
DataFrames com tipos estáveis, para que partições diferentes do mesmo endpoint
tenham o mesmo schema no Parquet.
"""

import json
import logging
import math
import re
from collections.abc import Callable, Mapping, Sequence
from typing import Any

import pandas as pd

from formula1.domain.endpoints import (
    BOOL_COLUMNS,
    DATE_COLUMNS,
    FLOAT_COLUMNS,
    INT_COLUMNS,
    INT_LIST_COLUMNS,
    get_endpoint,
)

logger = logging.getLogger(__name__)

QUALIFYING_PHASES: tuple[str, ...] = ("q1", "q2", "q3")
"""Fases da classificação, usadas para explodir os arrays de ``session_result``."""

GAP_FIELDS: dict[str, tuple[str, ...]] = {
    "intervals": ("gap_to_leader", "interval"),
    "session_result": ("gap_to_leader",),
}
"""Campos de gap (segundos ou ``+N LAP(S)``) de cada endpoint."""

_LAPS_PATTERN = re.compile(r"^\+?\s*(\d+)\s+LAPS?$", re.IGNORECASE)


def parse_gap(value: Any) -> float | None:
    """Converte um gap da OpenF1 em segundos.

    Args:
        value: Número, texto numérico (``"+1.234"``), ``"+N LAP(S)"`` ou ``None``.

    Returns:
        O gap em segundos; ``None`` para o líder (``null``) ou quando o piloto
        está voltas atrás (``"+1 LAP"``), caso em que o gap não é temporal.

    Raises:
        ValueError: Se o valor não for um gap reconhecível.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        msg = f"Gap inválido: {value!r}"
        raise ValueError(msg)
    if isinstance(value, int | float):
        return None if math.isnan(value) else _finite(float(value), value)
    if isinstance(value, str):
        text = value.strip()
        if _LAPS_PATTERN.match(text):
            return None
        try:
            number = float(text)
        except ValueError:
            msg = f"Gap inválido: {value!r}"
            raise ValueError(msg) from None
        return _finite(number, value)
    msg = f"Gap inválido: {value!r}"
    raise ValueError(msg)


def parse_laps_behind(value: Any) -> int | None:
    """Converte um gap da OpenF1 em quantidade de voltas de atraso.

    Args:
        value: Número, texto numérico, ``"+N LAP(S)"`` ou ``None``.

    Returns:
        ``N`` para ``"+N LAP(S)"``, ``0`` para gaps em segundos e ``None`` para
        o líder (``null``).

    Raises:
        ValueError: Se o valor não for um gap reconhecível.
    """
    if isinstance(value, str):
        match = _LAPS_PATTERN.match(value.strip())
        if match:
            return int(match.group(1))
    seconds = parse_gap(value)
    return None if seconds is None else 0


def to_dataframe(records: Sequence[Mapping[str, Any]], endpoint: str) -> pd.DataFrame:
    """Normaliza os registros de um endpoint em um DataFrame tipado.

    Regras aplicadas:

    - remove os campos depreciados (``drivers.country_code``, ``pit.pit_duration``);
    - garante todas as colunas documentadas, mesmo ausentes na resposta;
    - em ``intervals`` e ``session_result``, cria ``<campo>_seconds`` e
      ``<campo>_laps_behind`` a partir dos gaps e guarda o valor original como texto;
    - em ``session_result``, explode os arrays Q1/Q2/Q3 em ``duration_q1..q3`` e
      ``gap_to_leader_q1..q3``;
    - converte datas para ``datetime`` UTC e aplica tipos anuláveis.

    Args:
        records: Lista de objetos devolvida pela API.
        endpoint: Nome do endpoint de origem.

    Returns:
        O DataFrame normalizado. Uma lista vazia gera um DataFrame vazio com as
        colunas esperadas.

    Raises:
        ValueError: Se o endpoint não for suportado ou uma data for inválida.
    """
    spec = get_endpoint(endpoint)
    frame = pd.DataFrame.from_records(list(records))
    frame = frame.drop(columns=[c for c in spec.deprecated if c in frame.columns])
    for column in spec.columns:
        if column not in frame.columns:
            frame[column] = pd.Series(
                [None] * len(frame), index=frame.index, dtype=object
            )
    if endpoint == "session_result":
        frame = _expand_qualifying(frame)
    for field in GAP_FIELDS.get(endpoint, ()):
        frame = _add_gap_columns(frame, field)
    return _coerce_types(frame)


def _finite(number: float, original: Any) -> float:
    if not math.isfinite(number):
        msg = f"Gap inválido: {original!r}"
        raise ValueError(msg)
    return number


def _safe(parser: Callable[[Any], Any], value: Any) -> Any:
    try:
        return parser(value)
    except ValueError:
        logger.warning("Valor descartado por ser inválido: %r", value)
        return None


def _as_text(value: Any) -> str | None:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    if isinstance(value, list | tuple):
        return json.dumps(list(value))
    return str(value)


def _split_phases(value: Any) -> tuple[Any, list[Any]]:
    """Separa um valor escalar dos arrays Q1/Q2/Q3 da classificação."""
    if isinstance(value, list | tuple):
        phases = [*value, *([None] * len(QUALIFYING_PHASES))]
        return None, phases[: len(QUALIFYING_PHASES)]
    return value, [None] * len(QUALIFYING_PHASES)


def _float_series(values: list[Any], index: pd.Index) -> pd.Series:
    return pd.Series(values, index=index, dtype="float64")


def _expand_qualifying(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy()
    for field in ("duration", "gap_to_leader"):
        split = [_split_phases(value) for value in frame[field]]
        for position, phase in enumerate(QUALIFYING_PHASES):
            values = [_safe(parse_gap, phases[position]) for _, phases in split]
            frame[f"{field}_{phase}"] = _float_series(values, frame.index)
        if field == "duration":
            scalars = [_safe(parse_gap, scalar) for scalar, _ in split]
            frame[field] = _float_series(scalars, frame.index)
    return frame


def _add_gap_columns(frame: pd.DataFrame, field: str) -> pd.DataFrame:
    frame = frame.copy()
    scalars = [_split_phases(value)[0] for value in frame[field]]
    frame[f"{field}_seconds"] = _float_series(
        [_safe(parse_gap, value) for value in scalars], frame.index
    )
    frame[f"{field}_laps_behind"] = pd.Series(
        [_safe(parse_laps_behind, value) for value in scalars],
        index=frame.index,
        dtype="Int64",
    )
    frame[field] = pd.Series(
        [_as_text(value) for value in frame[field]], index=frame.index, dtype="string"
    )
    return frame


def _to_int(series: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(series)
    try:
        return numeric.astype("Int64")
    except (TypeError, ValueError):
        return numeric.astype("float64")


def _to_int_list(value: Any) -> list[int | None] | None:
    if not isinstance(value, list | tuple):
        return None
    return [None if item is None else int(item) for item in value]


def _is_text(series: pd.Series) -> bool:
    if series.dtype != object and not pd.api.types.is_string_dtype(series.dtype):
        return False
    return all(isinstance(value, str) for value in series.dropna())


def _coerce_types(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy()
    for column in frame.columns:
        series = frame[column]
        if column in DATE_COLUMNS:
            frame[column] = pd.to_datetime(series, utc=True, format="ISO8601")
        elif column in INT_COLUMNS:
            frame[column] = _to_int(series)
        elif column in FLOAT_COLUMNS:
            frame[column] = pd.to_numeric(series).astype("float64")
        elif column in BOOL_COLUMNS:
            frame[column] = series.astype("boolean")
        elif column in INT_LIST_COLUMNS:
            frame[column] = series.map(_to_int_list).astype(object)
        elif _is_text(series):
            frame[column] = series.astype("string")
    return frame
