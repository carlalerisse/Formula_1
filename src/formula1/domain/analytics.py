"""Análises puras sobre os dados normalizados de uma sessão (sem I/O).

As funções recebem DataFrames lidos do Parquet e devolvem tabelas prontas para
gráficos e indicadores. Quando a tabela de pilotos está disponível, cada linha
ganha um rótulo (sigla de três letras) e a cor da equipe.
"""

import math
from collections.abc import Collection
from dataclasses import dataclass

import pandas as pd

COMPOUND_COLORS: dict[str, str] = {
    "SOFT": "#DA291C",
    "MEDIUM": "#FFD12E",
    "HARD": "#EBEBEB",
    "INTERMEDIATE": "#43B02A",
    "WET": "#0067AD",
    "UNKNOWN": "#9E9E9E",
}
"""Cores convencionais dos compostos de pneu."""

DEFAULT_COLOR: str = "#9E9E9E"
"""Cor usada quando a equipe do piloto é desconhecida."""

SLOW_LAP_RATIO: float = 1.07
"""Voltas acima de 107% da mais rápida são tratadas como lentas (SC, pit, tráfego)."""

LABEL_COLUMNS: tuple[str, ...] = (
    "driver_number",
    "label",
    "full_name",
    "team_name",
    "color",
)
"""Colunas da tabela de rótulos de pilotos."""

TOP_LAPS: int = 5
"""Quantidade padrão de voltas no ranking por circuito."""

FASTEST_LAP_COLUMNS: tuple[str, ...] = (
    "circuit",
    "rank",
    "lap_duration",
    "gap",
    "label",
    "full_name",
    "team_name",
    "color",
    "driver_number",
    "year",
    "meeting_name",
    "session_name",
    "session_type",
    "session_key",
    "lap_number",
)
"""Colunas devolvidas por ``fastest_laps_by_circuit``."""

_SECONDS_PER_MINUTE = 60


@dataclass(frozen=True)
class SessionSummary:
    """Indicadores de uma sessão.

    Attributes:
        winner: Rótulo do vencedor (posição 1 do resultado), se houver.
        fastest_driver: Rótulo do autor da volta mais rápida.
        fastest_lap: Tempo da volta mais rápida, em segundos.
        total_laps: Maior número de volta registrado.
        pit_stops: Quantidade de passagens pelo pit lane; ``None`` sem dados de pit.
    """

    winner: str | None
    fastest_driver: str | None
    fastest_lap: float | None
    total_laps: int | None
    pit_stops: int | None


def format_lap_time(seconds: float | None) -> str:
    """Formata um tempo de volta como ``m:ss.sss``.

    Args:
        seconds: Tempo em segundos.

    Returns:
        O tempo formatado (ex.: ``1:31.447``), ou ``"—"`` se ausente ou negativo.
    """
    if seconds is None or pd.isna(seconds) or seconds < 0 or math.isinf(seconds):
        return "—"
    minutes, rest = divmod(float(seconds), _SECONDS_PER_MINUTE)
    if minutes == 0:
        return f"{rest:.3f}"
    return f"{int(minutes)}:{rest:06.3f}"


def driver_labels(drivers: pd.DataFrame) -> pd.DataFrame:
    """Monta a tabela de rótulos e cores dos pilotos.

    Args:
        drivers: Dados do endpoint ``drivers`` de uma sessão.

    Returns:
        Uma linha por ``driver_number``, com ``label`` (sigla ou ``#número``),
        ``full_name``, ``team_name`` e ``color`` (hex com ``#``).
    """
    if drivers.empty or "driver_number" not in drivers.columns:
        return pd.DataFrame(columns=list(LABEL_COLUMNS))
    frame = drivers.dropna(subset=["driver_number"]).drop_duplicates(
        "driver_number", keep="last"
    )
    numbers = frame["driver_number"].astype("int64")
    fallback = "#" + numbers.astype(str)
    result = pd.DataFrame(
        {
            "driver_number": numbers,
            "label": _column(frame, "name_acronym").fillna(fallback),
            "full_name": _column(frame, "full_name").fillna(fallback),
            "team_name": _column(frame, "team_name").fillna(""),
            "color": _column(frame, "team_colour").map(_hex_color),
        }
    )
    return result.sort_values("driver_number").reset_index(drop=True)


def attach_labels(frame: pd.DataFrame, labels: pd.DataFrame) -> pd.DataFrame:
    """Acrescenta ``label``, ``full_name``, ``team_name`` e ``color`` pelo piloto.

    Pilotos sem cadastro recebem o rótulo ``#número`` e a cor padrão.

    Args:
        frame: Tabela com a coluna ``driver_number``.
        labels: Saída de [driver_labels][formula1.domain.analytics.driver_labels].

    Returns:
        Uma cópia de ``frame`` com as colunas de rótulo.
    """
    frame = frame.drop(columns=[c for c in LABEL_COLUMNS[1:] if c in frame.columns])
    frame = frame.dropna(subset=["driver_number"]).copy()
    frame["driver_number"] = frame["driver_number"].astype("int64")
    merged = frame.merge(labels, on="driver_number", how="left")
    fallback = "#" + merged["driver_number"].astype(str)
    merged["label"] = merged["label"].fillna(fallback)
    merged["full_name"] = merged["full_name"].fillna(fallback)
    merged["team_name"] = merged["team_name"].fillna("")
    merged["color"] = merged["color"].fillna(DEFAULT_COLOR)
    return merged


def lap_times(
    laps: pd.DataFrame,
    labels: pd.DataFrame,
    *,
    include_pit_out: bool = False,
    max_ratio: float | None = SLOW_LAP_RATIO,
) -> pd.DataFrame:
    """Seleciona as voltas cronometradas de uma sessão.

    Args:
        laps: Dados do endpoint ``laps``.
        labels: Rótulos dos pilotos.
        include_pit_out: Mantém as voltas de saída do pit.
        max_ratio: Descarta voltas acima de ``max_ratio`` x a volta mais rápida.
            ``None`` mantém todas.

    Returns:
        Voltas com ``lap_duration`` válido, ordenadas por piloto e volta.

    Raises:
        ValueError: Se ``max_ratio`` for menor que 1.
    """
    if max_ratio is not None and max_ratio < 1:
        msg = f"max_ratio deve ser >= 1 (recebido {max_ratio})"
        raise ValueError(msg)
    if laps.empty:
        return attach_labels(
            laps.assign(driver_number=pd.Series(dtype="Int64")), labels
        )
    frame = laps.dropna(subset=["lap_duration", "lap_number"])
    if not include_pit_out and "is_pit_out_lap" in frame.columns:
        frame = frame[~frame["is_pit_out_lap"].fillna(False).astype(bool)]
    if max_ratio is not None and not frame.empty:
        frame = frame[frame["lap_duration"] <= frame["lap_duration"].min() * max_ratio]
    frame = attach_labels(frame, labels)
    return frame.sort_values(["driver_number", "lap_number"]).reset_index(drop=True)


def tyre_stints(stints: pd.DataFrame, labels: pd.DataFrame) -> pd.DataFrame:
    """Prepara os stints para o gráfico de estratégia de pneus.

    Args:
        stints: Dados do endpoint ``stints``.
        labels: Rótulos dos pilotos.

    Returns:
        Stints com ``lap_start``, ``lap_end`` (preenchido com ``lap_start`` quando
        ausente), ``laps`` e ``compound`` em maiúsculas (``UNKNOWN`` se ausente).
    """
    if stints.empty:
        return attach_labels(
            stints.assign(driver_number=pd.Series(dtype="Int64")), labels
        )
    frame = stints.dropna(subset=["lap_start"]).copy()
    frame["lap_start"] = frame["lap_start"].astype("int64")
    frame["lap_end"] = frame["lap_end"].fillna(frame["lap_start"]).astype("int64")
    frame["laps"] = frame["lap_end"] - frame["lap_start"] + 1
    frame["compound"] = frame["compound"].astype("string").str.upper().fillna("UNKNOWN")
    frame.loc[~frame["compound"].isin(COMPOUND_COLORS), "compound"] = "UNKNOWN"
    frame = attach_labels(frame, labels)
    return frame.sort_values(["driver_number", "lap_start"]).reset_index(drop=True)


def position_timeline(position: pd.DataFrame, labels: pd.DataFrame) -> pd.DataFrame:
    """Ordena as mudanças de posição no tempo.

    Args:
        position: Dados do endpoint ``position``.
        labels: Rótulos dos pilotos.

    Returns:
        Linhas com ``date`` e ``position`` válidos, em ordem cronológica.
    """
    if position.empty:
        return attach_labels(
            position.assign(driver_number=pd.Series(dtype="Int64")), labels
        )
    frame = position.dropna(subset=["date", "position"])
    frame = attach_labels(frame, labels)
    return frame.sort_values(["date", "position"]).reset_index(drop=True)


def result_table(result: pd.DataFrame, labels: pd.DataFrame) -> pd.DataFrame:
    """Monta a classificação final da sessão.

    Args:
        result: Dados do endpoint ``session_result``.
        labels: Rótulos dos pilotos.

    Returns:
        Uma linha por piloto, ordenada pela posição (sem posição ao final), com
        ``status`` igual a ``DNF``, ``DNS``, ``DSQ`` ou vazio.
    """
    if result.empty:
        return attach_labels(
            result.assign(driver_number=pd.Series(dtype="Int64")), labels
        )
    frame = attach_labels(result, labels)
    frame["status"] = [_status(row) for row in frame.to_dict("records")]
    return frame.sort_values("position", na_position="last").reset_index(drop=True)


def summarize(
    result: pd.DataFrame,
    laps: pd.DataFrame,
    pit: pd.DataFrame,
    labels: pd.DataFrame,
) -> SessionSummary:
    """Calcula os indicadores principais de uma sessão.

    Args:
        result: Dados do endpoint ``session_result``.
        laps: Dados do endpoint ``laps``.
        pit: Dados do endpoint ``pit``.
        labels: Rótulos dos pilotos.

    Returns:
        Os indicadores; os campos ficam ``None`` quando faltam dados.
    """
    winner = None
    if not result.empty and "position" in result.columns:
        leaders = attach_labels(result[result["position"] == 1], labels)
        if not leaders.empty:
            winner = str(leaders["label"].iloc[0])
    fastest_driver = fastest_lap = total_laps = None
    timed = lap_times(laps, labels, include_pit_out=True, max_ratio=None)
    if not timed.empty:
        best = timed.loc[timed["lap_duration"].idxmin()]
        fastest_driver = str(best["label"])
        fastest_lap = float(best["lap_duration"])
    if not laps.empty and laps["lap_number"].notna().any():
        total_laps = int(laps["lap_number"].max())
    pit_stops = None if pit.empty else len(pit)
    return SessionSummary(winner, fastest_driver, fastest_lap, total_laps, pit_stops)


def session_driver_labels(drivers: pd.DataFrame) -> pd.DataFrame:
    """Rótulos e cores dos pilotos, sessão a sessão.

    Útil quando várias sessões são analisadas juntas: o mesmo número pode
    mudar de piloto ou de equipe entre temporadas.

    Args:
        drivers: Dados do endpoint ``drivers`` de várias sessões, com
            ``session_key``.

    Returns:
        As colunas de [driver_labels][formula1.domain.analytics.driver_labels]
        mais ``session_key``.
    """
    columns = ["session_key", *LABEL_COLUMNS]
    if drivers.empty or "session_key" not in drivers.columns:
        return pd.DataFrame(columns=columns)
    frames = [
        driver_labels(group).assign(session_key=int(session_key))
        for session_key, group in drivers.dropna(subset=["session_key"]).groupby(
            "session_key", observed=True
        )
    ]
    frames = [frame for frame in frames if not frame.empty]
    if not frames:
        return pd.DataFrame(columns=columns)
    return pd.concat(frames, ignore_index=True)[columns]


def fastest_laps_by_circuit(  # noqa: PLR0913 - 4 tabelas de entrada + 3 opções nomeadas
    laps: pd.DataFrame,
    sessions: pd.DataFrame,
    meetings: pd.DataFrame,
    drivers: pd.DataFrame,
    *,
    top_n: int = TOP_LAPS,
    session_names: Collection[str] | None = None,
    one_per_driver: bool = False,
) -> pd.DataFrame:
    """Ranking das voltas mais rápidas de cada circuito.

    Considera apenas voltas cronometradas válidas: ``lap_duration`` positivo e
    que não sejam de saída do pit.

    Args:
        laps: Dados do endpoint ``laps`` de várias sessões (com ``year``,
            ``meeting_key`` e ``session_key``).
        sessions: Catálogo ``sessions`` (circuito, nome e tipo da sessão).
        meetings: Catálogo ``meetings`` (nome do Grande Prêmio).
        drivers: Dados do endpoint ``drivers`` das mesmas sessões.
        top_n: Quantidade de voltas por circuito.
        session_names: Mantém só as sessões com esses nomes (ex.: ``Race``,
            ``Sprint``, ``Qualifying``). ``None`` mantém todas.
        one_per_driver: Conta só a melhor volta de cada piloto no circuito.

    Returns:
        Até ``top_n`` linhas por circuito, com ``circuit``, ``rank`` (1 = mais
        rápida), ``lap_duration``, ``gap`` (diferença para a 1ª, em segundos),
        dados do piloto (``label``, ``full_name``, ``team_name``, ``color``) e
        da sessão (``year``, ``meeting_name``, ``session_name``,
        ``session_type``, ``lap_number``). Ordenado por circuito e ``rank``.

    Raises:
        ValueError: Se ``top_n`` for menor que 1.
    """
    if top_n < 1:
        msg = f"top_n deve ser >= 1 (recebido {top_n})"
        raise ValueError(msg)
    if laps.empty or "lap_duration" not in laps.columns:
        return pd.DataFrame(columns=list(FASTEST_LAP_COLUMNS))
    frame = laps.dropna(subset=["lap_duration", "driver_number", "session_key"])
    frame = frame[frame["lap_duration"] > 0]
    if "is_pit_out_lap" in frame.columns:
        frame = frame[~frame["is_pit_out_lap"].fillna(False).astype(bool)]
    frame = _with_circuit(frame, sessions, meetings)
    if session_names is not None:
        frame = frame[frame["session_name"].isin(list(session_names))]
    if frame.empty:
        return pd.DataFrame(columns=list(FASTEST_LAP_COLUMNS))
    frame = _with_session_labels(frame, drivers)
    frame = frame.sort_values(
        ["circuit", "lap_duration", "year", "session_key", "lap_number"],
        kind="stable",
    )
    if one_per_driver:
        frame = frame.drop_duplicates(["circuit", "label"])
    top = frame.groupby("circuit", sort=True).head(top_n).copy()
    top["rank"] = top.groupby("circuit").cumcount() + 1
    best = top.groupby("circuit")["lap_duration"].transform("min")
    top["gap"] = (top["lap_duration"] - best).round(3)
    return top[list(FASTEST_LAP_COLUMNS)].reset_index(drop=True)


def _text_column(frame: pd.DataFrame, name: str) -> pd.Series:
    if name not in frame.columns:
        return pd.Series([None] * len(frame), index=frame.index, dtype=object)
    return frame[name].astype(object).where(frame[name].notna(), None)


def _with_circuit(
    laps: pd.DataFrame, sessions: pd.DataFrame, meetings: pd.DataFrame
) -> pd.DataFrame:
    frame = laps.copy()
    for key in ("year", "meeting_key", "session_key", "lap_number"):
        if key in frame.columns:
            frame[key] = frame[key].astype("Int64")
    frame = _merge_catalog(
        frame,
        sessions,
        "session_key",
        ["circuit_short_name", "session_name", "session_type"],
    )
    frame = _merge_catalog(
        frame, meetings, "meeting_key", ["meeting_name", "circuit_short_name"]
    )
    circuit = _text_column(frame, "circuit_short_name")
    circuit = circuit.fillna(_text_column(frame, "circuit_short_name_meeting"))
    fallback = "Meeting " + frame["meeting_key"].astype(str)
    frame["circuit"] = circuit.fillna(_text_column(frame, "meeting_name")).fillna(
        fallback
    )
    return frame


def _merge_catalog(
    frame: pd.DataFrame, catalog: pd.DataFrame, key: str, columns: list[str]
) -> pd.DataFrame:
    available = [c for c in columns if c in catalog.columns]
    if catalog.empty or key not in catalog.columns or not available:
        return frame.assign(**{c: None for c in columns if c not in frame.columns})
    subset = catalog.dropna(subset=[key]).drop_duplicates(key)[[key, *available]]
    subset = subset.astype({key: "Int64"})
    merged = frame.merge(subset, on=key, how="left", suffixes=("", "_meeting"))
    missing = {c: None for c in columns if c not in merged.columns}
    return merged.assign(**missing)


def _with_session_labels(frame: pd.DataFrame, drivers: pd.DataFrame) -> pd.DataFrame:
    labels = session_driver_labels(drivers)
    frame = frame.drop(columns=[c for c in LABEL_COLUMNS[1:] if c in frame.columns])
    frame = frame.assign(
        driver_number=frame["driver_number"].astype("int64"),
        session_key=frame["session_key"].astype("int64"),
    )
    labels = labels.astype({"driver_number": "int64", "session_key": "int64"})
    merged = frame.merge(labels, on=["session_key", "driver_number"], how="left")
    # Sessões sem cadastro de pilotos herdam o rótulo mais recente do mesmo número.
    latest = (
        labels.sort_values("session_key")
        .drop_duplicates("driver_number", keep="last")
        .drop(columns="session_key")
        .set_index("driver_number")
    )
    for column in LABEL_COLUMNS[1:]:
        merged[column] = merged[column].fillna(
            merged["driver_number"].map(latest[column])
        )
    fallback = "#" + merged["driver_number"].astype(str)
    merged["label"] = merged["label"].fillna(fallback)
    merged["full_name"] = merged["full_name"].fillna(fallback)
    merged["team_name"] = merged["team_name"].fillna("")
    merged["color"] = merged["color"].fillna(DEFAULT_COLOR)
    return merged


def _column(frame: pd.DataFrame, name: str) -> pd.Series:
    if name in frame.columns:
        return frame[name].astype(object).where(frame[name].notna(), None)
    return pd.Series([None] * len(frame), index=frame.index, dtype=object)


def _hex_color(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        return DEFAULT_COLOR
    text = value.strip().lstrip("#")
    return f"#{text.upper()}"


def _status(row: dict[str, object]) -> str:
    for flag in ("dsq", "dns", "dnf"):
        value = row.get(flag)
        if value is not None and not pd.isna(value) and bool(value):
            return flag.upper()
    return ""
