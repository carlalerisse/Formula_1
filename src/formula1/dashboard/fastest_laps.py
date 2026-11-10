"""Página "Top 5 voltas por circuito" do dashboard.

Junta as voltas de todas as sessões extraídas da OpenF1 (endpoint ``laps``),
identifica o circuito pelo catálogo ``sessions``/``meetings`` e mostra as 5
voltas mais rápidas já registradas em cada pista.
"""

from pathlib import Path

import pandas as pd
import streamlit as st

from formula1.dashboard import charts, data
from formula1.domain import analytics

LAP_COLUMNS: tuple[str, ...] = (
    "driver_number",
    "lap_number",
    "lap_duration",
    "is_pit_out_lap",
)
"""Colunas de ``laps`` lidas pela página (as demais são ignoradas)."""

DRIVER_COLUMNS: tuple[str, ...] = (
    "driver_number",
    "name_acronym",
    "full_name",
    "team_name",
    "team_colour",
)
"""Colunas de ``drivers`` lidas pela página."""

EXTRACT_HINT: str = (
    "```\npoetry run formula1 extract --year 2024 "
    "--endpoints meetings,sessions,drivers,laps\n```"
)
"""Comando sugerido quando faltam dados."""


@st.cache_data(show_spinner="Lendo as voltas extraídas da OpenF1...")
def load_inputs(data_dir: str, years: tuple[int, ...]) -> dict[str, pd.DataFrame]:
    """Voltas, pilotos e catálogos das temporadas escolhidas (com cache)."""
    root = Path(data_dir)
    sessions, meetings = data.read_catalogs(root, years)
    return {
        "laps": data.read_sessions(root, "laps", years, LAP_COLUMNS),
        "drivers": data.read_sessions(root, "drivers", years, DRIVER_COLUMNS),
        "sessions": sessions,
        "meetings": meetings,
    }


def _session_options(laps: pd.DataFrame, sessions: pd.DataFrame) -> list[str]:
    """Nomes das sessões (Race, Sprint...) que têm voltas extraídas."""
    if laps.empty or sessions.empty or "session_name" not in sessions.columns:
        return []
    keys = set(laps["session_key"].dropna().astype("int64"))
    catalog = sessions.dropna(subset=["session_key", "session_name"])
    names = catalog[catalog["session_key"].astype("int64").isin(keys)]
    return sorted(set(names["session_name"].astype(str)))


def _overview_table(top: pd.DataFrame) -> pd.DataFrame:
    """Uma linha por circuito e uma coluna por posição (``VER · 1:29.708``)."""
    cells = top.assign(
        cell=[
            f"{label} · {analytics.format_lap_time(seconds)} ({year})"
            for label, seconds, year in zip(
                top["label"], top["lap_duration"], top["year"], strict=True
            )
        ],
        column=[f"{rank}º" for rank in top["rank"]],
    )
    table = cells.pivot(index="circuit", columns="column", values="cell")
    ordered = [f"{rank}º" for rank in sorted(top["rank"].unique())]
    return table[ordered].reset_index().rename(columns={"circuit": "Circuito"})


def _detail_table(circuit_top: pd.DataFrame) -> pd.DataFrame:
    frame = circuit_top.assign(
        time=[analytics.format_lap_time(v) for v in circuit_top["lap_duration"]],
    )
    columns = [
        "rank",
        "label",
        "full_name",
        "team_name",
        "time",
        "gap",
        "year",
        "meeting_name",
        "session_name",
        "lap_number",
    ]
    return frame[columns]


def _metrics(top: pd.DataFrame, laps_considered: int) -> None:
    record = top[top["rank"] == 1]
    holders = record["label"].value_counts()
    columns = st.columns(3)
    columns[0].metric("Circuitos", top["circuit"].nunique())
    columns[1].metric("Voltas extraídas", f"{laps_considered:,}".replace(",", "."))
    columns[2].metric(
        "Mais voltas recorde",
        holders.index[0] if not holders.empty else "—",
        f"{int(holders.iloc[0])} circuito(s)" if not holders.empty else None,
        delta_color="off",
    )


def render(data_dir: str, years: list[int]) -> None:
    """Renderiza a página do ranking de voltas por circuito.

    Args:
        data_dir: Diretório raiz dos dados.
        years: Temporadas disponíveis (já verificadas como não vazias).
    """
    st.header(f"Top {analytics.TOP_LAPS} voltas mais rápidas por circuito")
    st.caption(
        "Voltas cronometradas extraídas da API OpenF1 (2023 em diante). "
        "Voltas de saída do pit são desconsideradas."
    )
    chosen = st.sidebar.multiselect("Temporadas", years, default=years)
    if not chosen:
        st.info("Selecione ao menos uma temporada na barra lateral.")
        return
    inputs = load_inputs(data_dir, tuple(sorted(chosen)))
    laps = inputs["laps"]
    if laps.empty:
        st.info(
            "Nenhuma volta (`laps`) extraída para as temporadas escolhidas. "
            f"Para extrair:\n\n{EXTRACT_HINT}"
        )
        return
    options = _session_options(laps, inputs["sessions"])
    session_names = None
    if options:
        session_names = st.sidebar.multiselect(
            "Sessões", options, default=options, help="Ex.: Race, Sprint, Qualifying"
        )
    one_per_driver = st.sidebar.toggle(
        "Só a melhor volta de cada piloto",
        value=False,
        help="Evita que um mesmo piloto ocupe várias posições do ranking.",
    )
    top = analytics.fastest_laps_by_circuit(
        laps,
        inputs["sessions"],
        inputs["meetings"],
        inputs["drivers"],
        session_names=session_names,
        one_per_driver=one_per_driver,
    )
    if top.empty:
        st.info("Nenhuma volta cronometrada para os filtros escolhidos.")
        return
    if inputs["sessions"].empty:
        st.warning(
            "O catálogo `sessions` não foi extraído: os circuitos aparecem pelo "
            f"nome do evento ou pela chave numérica.\n\n{EXTRACT_HINT}"
        )
    _metrics(top, int(laps["lap_duration"].notna().sum()))

    by_circuit, overview, drivers = st.tabs(
        ["Por circuito", "Todos os circuitos", "Pilotos"]
    )
    with by_circuit:
        circuits = sorted(top["circuit"].unique())
        circuit = st.selectbox("Circuito", circuits)
        circuit_top = top[top["circuit"] == circuit]
        st.altair_chart(charts.fastest_laps_chart(circuit_top), width="stretch")
        st.dataframe(
            _detail_table(circuit_top),
            hide_index=True,
            column_config={
                "rank": "Pos.",
                "label": "Piloto",
                "full_name": "Nome",
                "team_name": "Equipe",
                "time": "Tempo",
                "gap": st.column_config.NumberColumn("Diferença (s)", format="+%.3f"),
                "year": st.column_config.NumberColumn("Temporada", format="%d"),
                "meeting_name": "Grande Prêmio",
                "session_name": "Sessão",
                "lap_number": "Volta",
            },
        )
    with overview:
        st.dataframe(_overview_table(top), hide_index=True)
    with drivers:
        st.altair_chart(charts.driver_podium_chart(top), width="stretch")
