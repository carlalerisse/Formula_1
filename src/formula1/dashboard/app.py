"""Aplicação Streamlit do dashboard.

Abre na visão "Top 5 voltas por circuito"; a "Análise por sessão" fica no
seletor da barra lateral. Executar com ``poetry run task dashboard`` (equivale a
``streamlit run src/formula1/dashboard/app.py``).
"""

from collections.abc import Callable
from pathlib import Path

import pandas as pd
import streamlit as st

from formula1 import config
from formula1.adapters.storage import PartitionKeys
from formula1.dashboard import charts, data, fastest_laps
from formula1.domain import analytics

FASTEST_VIEW: str = f"Top {analytics.TOP_LAPS} voltas por circuito"
"""Visão inicial: ranking das voltas mais rápidas de cada circuito."""

SESSION_VIEW: str = "Análise por sessão"
"""Visão detalhada de uma sessão (ritmo, pneus, posições e resultado)."""

VIEWS: tuple[str, ...] = (FASTEST_VIEW, SESSION_VIEW)
"""Visões do dashboard, na ordem do seletor (a primeira abre por padrão)."""

SESSION_ENDPOINTS: tuple[str, ...] = (
    "drivers",
    "laps",
    "stints",
    "position",
    "pit",
    "session_result",
)
"""Endpoints lidos para a sessão selecionada."""


@st.cache_data(show_spinner=False)
def load_years(data_dir: str) -> list[int]:
    """Temporadas disponíveis (com cache)."""
    return data.available_years(Path(data_dir))


@st.cache_data(show_spinner=False)
def load_sessions(data_dir: str, year: int) -> pd.DataFrame:
    """Sessões disponíveis em uma temporada (com cache)."""
    return data.available_sessions(Path(data_dir), year)


@st.cache_data(show_spinner=False)
def load_partition(
    data_dir: str, endpoint: str, year: int, meeting_key: int, session_key: int
) -> pd.DataFrame:
    """Dados de um endpoint em uma sessão (com cache)."""
    keys = PartitionKeys(year, meeting_key, session_key)
    return data.read_partition(Path(data_dir), endpoint, keys)


Notice = Callable[[str], None]
"""Mostra o aviso de dados ausentes de um endpoint."""


def _missing(endpoint: str, year: int, *, extracted: bool) -> None:
    if extracted:
        st.info(
            f"A OpenF1 não tem dados de `{endpoint}` para esta sessão: a "
            "extração foi feita, mas a API não devolveu registros."
        )
        return
    st.info(
        f"Sem dados de `{endpoint}` para esta sessão. Para extrair:\n\n"
        f"```\npoetry run formula1 extract --year {year} --endpoints {endpoint}\n```"
    )


def _sidebar(data_dir: str, years: list[int]) -> tuple[str, int, pd.Series] | None:
    year = st.sidebar.selectbox("Temporada", years)
    sessions = load_sessions(data_dir, year)
    if sessions.empty:
        st.warning(f"Nenhuma sessão com dados em {year}.")
        return None
    index = st.sidebar.selectbox(
        "Sessão",
        range(len(sessions)),
        format_func=lambda i: sessions["label"].iloc[i],
    )
    return data_dir, year, sessions.iloc[index]


def _metrics(summary: analytics.SessionSummary) -> None:
    columns = st.columns(4)
    columns[0].metric("Vencedor", summary.winner or "—")
    fastest = analytics.format_lap_time(summary.fastest_lap)
    columns[1].metric(
        "Volta mais rápida", fastest, summary.fastest_driver, delta_color="off"
    )
    columns[2].metric("Voltas", summary.total_laps or "—")
    pit_stops = "—" if summary.pit_stops is None else summary.pit_stops
    columns[3].metric("Passagens pelo pit", pit_stops)


def _filter(frame: pd.DataFrame, selected: list[str]) -> pd.DataFrame:
    return frame[frame["label"].isin(selected)] if "label" in frame.columns else frame


def _pace_tab(
    laps: pd.DataFrame, labels: pd.DataFrame, selected: list[str], missing: Notice
) -> None:
    if laps.empty:
        missing("laps")
        return
    left, right = st.columns(2)
    hide_slow = left.toggle(
        "Ocultar voltas lentas (> 107% da mais rápida)",
        value=True,
        help="Remove voltas sob safety car, de entrada no pit e com tráfego.",
    )
    pit_out = right.toggle("Incluir voltas de saída do pit", value=False)
    timed = analytics.lap_times(
        laps,
        labels,
        include_pit_out=pit_out,
        max_ratio=analytics.SLOW_LAP_RATIO if hide_slow else None,
    )
    timed = _filter(timed, selected)
    if timed.empty:
        st.info("Nenhuma volta cronometrada para os pilotos selecionados.")
        return
    st.altair_chart(charts.lap_time_chart(timed), width="stretch")
    st.subheader("Distribuição dos tempos")
    st.altair_chart(charts.lap_distribution_chart(timed), width="stretch")


def _tyres_tab(
    stints: pd.DataFrame,
    labels: pd.DataFrame,
    selected: list[str],
    order: list[str],
    missing: Notice,
) -> None:
    if stints.empty:
        missing("stints")
        return
    prepared = _filter(analytics.tyre_stints(stints, labels), selected)
    if prepared.empty:
        st.info("Nenhum stint para os pilotos selecionados.")
        return
    visible = [label for label in order if label in set(prepared["label"])]
    st.altair_chart(
        charts.tyre_strategy_chart(prepared, visible or None), width="stretch"
    )


def _positions_tab(
    position: pd.DataFrame, labels: pd.DataFrame, selected: list[str], missing: Notice
) -> None:
    if position.empty:
        missing("position")
        return
    timeline = _filter(analytics.position_timeline(position, labels), selected)
    if timeline.empty:
        st.info("Nenhuma posição para os pilotos selecionados.")
        return
    st.altair_chart(charts.position_chart(timeline), width="stretch")


def _result_tab(
    table: pd.DataFrame, pit: pd.DataFrame, labels: pd.DataFrame, missing: Notice
) -> None:
    if table.empty:
        missing("session_result")
    else:
        columns = [
            c
            for c in (
                "position",
                "label",
                "full_name",
                "team_name",
                "number_of_laps",
                "gap_to_leader",
                "duration",
                "duration_q1",
                "duration_q2",
                "duration_q3",
                "status",
            )
            if c in table.columns and table[c].notna().any()
        ]
        st.dataframe(
            table[columns],
            hide_index=True,
            column_config={
                "position": "Pos.",
                "label": "Piloto",
                "full_name": "Nome",
                "team_name": "Equipe",
                "number_of_laps": "Voltas",
                "gap_to_leader": "Gap",
                "duration": "Tempo (s)",
                "status": "Status",
            },
        )
    st.subheader("Pit stops")
    if pit.empty:
        missing("pit")
        return
    stops = analytics.attach_labels(pit, labels).sort_values(["lap_number", "label"])
    columns = [
        c
        for c in ("lap_number", "label", "team_name", "lane_duration", "stop_duration")
        if c in stops.columns
    ]
    st.dataframe(
        stops[columns],
        hide_index=True,
        column_config={
            "lap_number": "Volta",
            "label": "Piloto",
            "team_name": "Equipe",
            "lane_duration": "Tempo no pit lane (s)",
            "stop_duration": "Parado (s)",
        },
    )


def main() -> None:
    """Renderiza o dashboard."""
    st.set_page_config(
        page_title="Fórmula 1 · Dashboard", page_icon="🏁", layout="wide"
    )
    st.title("Fórmula 1 · Dashboard")
    view = st.sidebar.radio("Visão", VIEWS)
    st.sidebar.header("Filtros")
    data_dir = st.sidebar.text_input(
        "Diretório de dados",
        str(config.get_data_dir()),
        help=f"Padrão: variável {config.DATA_DIR_ENV_VAR} ou ./data",
    )
    years = load_years(data_dir)
    if not years:
        st.warning(
            f"Nenhum dado encontrado em `{data_dir}`. "
            "Extraia uma temporada primeiro:\n\n"
            "```\npoetry run formula1 extract --year 2024 --session-type Race\n```"
        )
        return
    if view == FASTEST_VIEW:
        fastest_laps.render(data_dir, years)
    else:
        _session_view(data_dir, years)


def _session_view(data_dir: str, years: list[int]) -> None:
    selection = _sidebar(data_dir, years)
    if selection is None:
        return
    data_dir, year, session = selection
    keys = (year, int(session["meeting_key"]), int(session["session_key"]))
    frames = {ep: load_partition(data_dir, ep, *keys) for ep in SESSION_ENDPOINTS}
    partition = PartitionKeys(*keys)

    def missing(endpoint: str) -> None:
        extracted = data.was_extracted(Path(data_dir), endpoint, partition)
        _missing(endpoint, year, extracted=extracted)

    labels = analytics.driver_labels(frames["drivers"])
    table = analytics.result_table(frames["session_result"], labels)
    order = table["label"].tolist() if not table.empty else []
    all_labels = order + [
        label for label in _all_labels(frames, labels) if label not in order
    ]
    selected = st.sidebar.multiselect("Pilotos", all_labels, default=all_labels)

    st.caption(f"{session['label']} · meeting {keys[1]} · sessão {keys[2]}")
    _metrics(
        analytics.summarize(
            frames["session_result"], frames["laps"], frames["pit"], labels
        )
    )
    pace, tyres, positions, result = st.tabs(
        ["Ritmo", "Pneus", "Posições", "Resultado e pit stops"]
    )
    with pace:
        _pace_tab(frames["laps"], labels, selected, missing)
    with tyres:
        _tyres_tab(frames["stints"], labels, selected, order, missing)
    with positions:
        _positions_tab(frames["position"], labels, selected, missing)
    with result:
        _result_tab(table, frames["pit"], labels, missing)


def _all_labels(frames: dict[str, pd.DataFrame], labels: pd.DataFrame) -> list[str]:
    found: set[str] = set(labels["label"])
    for endpoint in ("laps", "stints", "position"):
        frame = frames[endpoint]
        if not frame.empty and "driver_number" in frame.columns:
            found.update(analytics.attach_labels(frame, labels)["label"])
    return sorted(found)


if __name__ == "__main__":
    main()
