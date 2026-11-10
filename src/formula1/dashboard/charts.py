"""Gráficos Altair do dashboard.

Cada função recebe a tabela já preparada por ``formula1.domain.analytics`` (com
``label`` e ``color`` dos pilotos) e devolve um gráfico Altair.
"""

from collections.abc import Sequence

import altair as alt
import pandas as pd

from formula1.domain.analytics import COMPOUND_COLORS, format_lap_time

_MIN_POSITIONS = 20


def driver_color_scale(frame: pd.DataFrame) -> alt.Scale:
    """Escala de cores que mapeia cada rótulo de piloto à cor da equipe.

    Args:
        frame: Tabela com as colunas ``label`` e ``color``.

    Returns:
        A escala ordinal ``label → color``.
    """
    pairs = frame[["label", "color"]].drop_duplicates("label").sort_values("label")
    return alt.Scale(domain=pairs["label"].tolist(), range=pairs["color"].tolist())


def _plain(frame: pd.DataFrame, columns: Sequence[str]) -> pd.DataFrame:
    """Copia só as colunas usadas, com tipos simples que o Vega-Lite entende."""
    subset = frame[list(columns)].copy()
    for column in subset.columns:
        series = subset[column]
        if isinstance(series.dtype, pd.DatetimeTZDtype):
            subset[column] = series.dt.tz_convert("UTC").dt.tz_localize(None)
        elif pd.api.types.is_bool_dtype(series.dtype) or pd.api.types.is_string_dtype(
            series.dtype
        ):
            subset[column] = series.astype(object).where(series.notna(), None)
        elif pd.api.types.is_extension_array_dtype(series.dtype):
            subset[column] = series.astype("float64")
    return subset


def lap_time_chart(laps: pd.DataFrame) -> alt.Chart:
    """Linha do tempo de volta por piloto.

    Args:
        laps: Saída de ``analytics.lap_times``.

    Returns:
        O gráfico, com zoom e tooltip.
    """
    data = _plain(laps, ["label", "color", "team_name", "lap_number", "lap_duration"])
    return (
        alt.Chart(data)
        .mark_line(point=alt.OverlayMarkDef(size=18), strokeWidth=1.5)
        .encode(
            x=alt.X("lap_number:Q", title="Volta"),
            y=alt.Y(
                "lap_duration:Q",
                title="Tempo de volta (s)",
                scale=alt.Scale(zero=False),
            ),
            color=alt.Color("label:N", title="Piloto", scale=driver_color_scale(laps)),
            tooltip=[
                alt.Tooltip("label:N", title="Piloto"),
                alt.Tooltip("team_name:N", title="Equipe"),
                alt.Tooltip("lap_number:Q", title="Volta"),
                alt.Tooltip("lap_duration:Q", title="Tempo (s)", format=".3f"),
            ],
        )
        .interactive()
    )


def lap_distribution_chart(laps: pd.DataFrame) -> alt.Chart:
    """Distribuição dos tempos de volta por piloto (boxplot), do mais rápido ao lento.

    Args:
        laps: Saída de ``analytics.lap_times``.

    Returns:
        O gráfico.
    """
    data = _plain(laps, ["label", "color", "lap_duration"])
    order = data.groupby("label")["lap_duration"].median().sort_values().index.tolist()
    return (
        alt.Chart(data)
        .mark_boxplot(extent="min-max", size=14)
        .encode(
            x=alt.X("label:N", title="Piloto", sort=order),
            y=alt.Y(
                "lap_duration:Q",
                title="Tempo de volta (s)",
                scale=alt.Scale(zero=False),
            ),
            color=alt.Color("label:N", scale=driver_color_scale(laps), legend=None),
        )
    )


def tyre_strategy_chart(
    stints: pd.DataFrame, driver_order: Sequence[str] | None = None
) -> alt.Chart:
    """Estratégia de pneus: uma barra por stint, colorida pelo composto.

    Args:
        stints: Saída de ``analytics.tyre_stints``.
        driver_order: Ordem dos pilotos no eixo vertical (ex.: resultado final).

    Returns:
        O gráfico.
    """
    data = _plain(
        stints,
        [
            "label",
            "team_name",
            "stint_number",
            "compound",
            "lap_start",
            "lap_end",
            "laps",
            "tyre_age_at_start",
        ],
    )
    data["lap_stop"] = data["lap_end"] + 1
    order = list(driver_order) if driver_order else sorted(data["label"].unique())
    return (
        alt.Chart(data)
        .mark_bar(stroke="#333333", strokeWidth=0.5, cornerRadius=2)
        .encode(
            x=alt.X("lap_start:Q", title="Volta"),
            x2="lap_stop:Q",
            y=alt.Y("label:N", title="Piloto", sort=order),
            color=alt.Color(
                "compound:N",
                title="Composto",
                scale=alt.Scale(
                    domain=list(COMPOUND_COLORS), range=list(COMPOUND_COLORS.values())
                ),
            ),
            tooltip=[
                alt.Tooltip("label:N", title="Piloto"),
                alt.Tooltip("stint_number:Q", title="Stint"),
                alt.Tooltip("compound:N", title="Composto"),
                alt.Tooltip("lap_start:Q", title="Volta inicial"),
                alt.Tooltip("lap_end:Q", title="Volta final"),
                alt.Tooltip("laps:Q", title="Voltas"),
                alt.Tooltip("tyre_age_at_start:Q", title="Idade do pneu no início"),
            ],
        )
    )


def fastest_laps_chart(top: pd.DataFrame) -> alt.LayerChart:
    """Voltas mais rápidas de um circuito: um ponto por volta, do 1º ao último.

    O eixo horizontal mostra o tempo de volta sem começar do zero, para que as
    diferenças de milésimos fiquem visíveis; o rótulo ao lado de cada ponto
    traz o tempo formatado e a diferença para a 1ª.

    Args:
        top: Linhas de um circuito em ``analytics.fastest_laps_by_circuit``.

    Returns:
        O gráfico.
    """
    data = _plain(
        top,
        [
            "rank",
            "label",
            "color",
            "full_name",
            "team_name",
            "lap_duration",
            "gap",
            "year",
            "meeting_name",
            "session_name",
            "lap_number",
        ],
    )
    data["position"] = [
        f"{rank}º · {label}"
        for rank, label in zip(data["rank"], data["label"], strict=True)
    ]
    data["time"] = [format_lap_time(value) for value in data["lap_duration"]]
    data["text"] = [
        time if gap == 0 else f"{time}  (+{gap:.3f})"
        for time, gap in zip(data["time"], data["gap"], strict=True)
    ]
    order = data.sort_values("rank")["position"].tolist()
    spread = float(data["lap_duration"].max() - data["lap_duration"].min())
    padding = max(spread * 0.6, 0.2)
    domain = [
        float(data["lap_duration"].min()) - padding * 0.25,
        float(data["lap_duration"].max()) + padding,
    ]
    base = alt.Chart(data).encode(
        x=alt.X(
            "lap_duration:Q",
            title="Tempo de volta (s)",
            scale=alt.Scale(domain=domain, zero=False, nice=False),
        ),
        y=alt.Y("position:N", title=None, sort=order),
        tooltip=[
            alt.Tooltip("rank:Q", title="Posição"),
            alt.Tooltip("full_name:N", title="Piloto"),
            alt.Tooltip("team_name:N", title="Equipe"),
            alt.Tooltip("time:N", title="Tempo"),
            alt.Tooltip("gap:Q", title="Diferença (s)", format="+.3f"),
            alt.Tooltip("year:Q", title="Temporada", format="d"),
            alt.Tooltip("meeting_name:N", title="Grande Prêmio"),
            alt.Tooltip("session_name:N", title="Sessão"),
            alt.Tooltip("lap_number:Q", title="Volta"),
        ],
    )
    rule = base.mark_rule(strokeWidth=2, opacity=0.35).encode(
        x=alt.datum(domain[0]),
        x2="lap_duration:Q",
        color=alt.Color("label:N", scale=driver_color_scale(top), legend=None),
    )
    points = base.mark_circle(size=220, opacity=1).encode(
        color=alt.Color("label:N", scale=driver_color_scale(top), legend=None),
    )
    labels = base.mark_text(align="left", dx=14, fontSize=13).encode(text="text:N")
    return alt.layer(rule, points, labels).properties(height=60 * len(data) + 20)


def driver_podium_chart(top: pd.DataFrame) -> alt.Chart:
    """Quantas voltas cada piloto tem entre as mais rápidas dos circuitos.

    Args:
        top: Saída de ``analytics.fastest_laps_by_circuit``.

    Returns:
        Barras horizontais empilhadas por posição no ranking.
    """
    data = _plain(top, ["label", "color", "full_name", "rank", "circuit"])
    order = data["label"].value_counts().sort_values(ascending=False, kind="stable")
    return (
        alt.Chart(data)
        .mark_bar(cornerRadius=2)
        .encode(
            x=alt.X("count():Q", title="Voltas entre as mais rápidas"),
            y=alt.Y("label:N", title="Piloto", sort=order.index.tolist()),
            color=alt.Color("label:N", scale=driver_color_scale(top), legend=None),
            opacity=alt.Opacity(
                "rank:O",
                title="Posição",
                scale=alt.Scale(range=[1.0, 0.35]),
            ),
            tooltip=[
                alt.Tooltip("full_name:N", title="Piloto"),
                alt.Tooltip("count():Q", title="Voltas"),
            ],
        )
    )


def position_chart(position: pd.DataFrame) -> alt.Chart:
    """Evolução das posições ao longo da sessão.

    Args:
        position: Saída de ``analytics.position_timeline``.

    Returns:
        O gráfico, com a posição 1 no topo.
    """
    data = _plain(position, ["label", "color", "date", "position"])
    deepest = max(_MIN_POSITIONS, int(data["position"].max()) if len(data) else 0)
    return (
        alt.Chart(data)
        .mark_line(interpolate="step-after", strokeWidth=2)
        .encode(
            x=alt.X("date:T", title="Horário (UTC)"),
            y=alt.Y(
                "position:Q",
                title="Posição",
                scale=alt.Scale(domain=[1, deepest], reverse=True, nice=False),
                axis=alt.Axis(tickMinStep=1),
            ),
            color=alt.Color(
                "label:N", title="Piloto", scale=driver_color_scale(position)
            ),
            tooltip=[
                alt.Tooltip("label:N", title="Piloto"),
                alt.Tooltip("position:Q", title="Posição"),
                alt.Tooltip("date:T", title="Horário (UTC)", format="%H:%M:%S"),
            ],
        )
        .interactive(bind_y=False)
    )
