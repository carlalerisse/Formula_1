import pandas as pd
import pytest

from formula1.dashboard import charts
from formula1.domain import analytics
from formula1.domain.transform import to_dataframe


@pytest.fixture
def prepared(session_frames):
    frames = {ep: to_dataframe(rows, ep) for ep, rows in session_frames.items()}
    labels = analytics.driver_labels(frames["drivers"])
    return {
        "laps": analytics.lap_times(frames["laps"], labels),
        "stints": analytics.tyre_stints(frames["stints"], labels),
        "position": analytics.position_timeline(frames["position"], labels),
    }


def _spec(chart) -> dict:
    return chart.to_dict()


def test_driver_color_scale_mapeia_rotulo_para_cor():
    frame = pd.DataFrame({"label": ["VER", "ALO", "VER"], "color": ["#1", "#2", "#1"]})

    scale = charts.driver_color_scale(frame).to_dict()

    assert scale == {"domain": ["ALO", "VER"], "range": ["#2", "#1"]}


def test_lap_time_chart(prepared):
    spec = _spec(charts.lap_time_chart(prepared["laps"]))

    assert spec["encoding"]["x"]["field"] == "lap_number"
    assert spec["encoding"]["y"]["field"] == "lap_duration"
    assert spec["encoding"]["color"]["scale"]["range"][0] == "#9E9E9E"
    assert spec["params"]


def test_lap_distribution_chart_ordena_pela_mediana(prepared):
    spec = _spec(charts.lap_distribution_chart(prepared["laps"]))

    assert spec["mark"]["type"] == "boxplot"
    assert spec["encoding"]["x"]["sort"] == ["VER", "PER", "ALO"]


def test_tyre_strategy_chart(prepared):
    spec = _spec(charts.tyre_strategy_chart(prepared["stints"], ["PER", "VER"]))

    assert spec["encoding"]["x2"]["field"] == "lap_stop"
    assert spec["encoding"]["y"]["sort"] == ["PER", "VER"]
    assert spec["encoding"]["color"]["scale"]["domain"] == list(
        analytics.COMPOUND_COLORS
    )
    rows = next(iter(spec["datasets"].values()))
    assert [row["lap_stop"] for row in rows] == [3, 4, 5]


def test_tyre_strategy_chart_ordem_padrao(prepared):
    spec = _spec(charts.tyre_strategy_chart(prepared["stints"]))

    assert spec["encoding"]["y"]["sort"] == ["PER", "VER"]


def test_position_chart_inverte_eixo(prepared):
    spec = _spec(charts.position_chart(prepared["position"]))

    scale = spec["encoding"]["y"]["scale"]
    assert scale["reverse"] is True
    assert scale["domain"] == [1, 20]
    rows = next(iter(spec["datasets"].values()))
    assert rows[0]["date"].startswith("2023-03-05T15:03:00")


def test_position_chart_mais_de_20_posicoes():
    frame = pd.DataFrame(
        {
            "label": ["A"],
            "color": ["#000"],
            "date": pd.to_datetime(["2023-01-01T00:00:00Z"]),
            "position": pd.array([22], dtype="Int64"),
        }
    )

    spec = _spec(charts.position_chart(frame))

    assert spec["encoding"]["y"]["scale"]["domain"] == [1, 22]


@pytest.fixture
def fastest(session_frames):
    frames = {ep: to_dataframe(rows, ep) for ep, rows in session_frames.items()}
    laps = frames["laps"].assign(year=2023, meeting_key=1141, session_key=7953)
    sessions = pd.DataFrame(
        {"session_key": [7953], "session_name": ["Race"], "circuit_short_name": ["X"]}
    )
    return analytics.fastest_laps_by_circuit(
        laps, sessions, pd.DataFrame(), frames["drivers"].assign(session_key=7953)
    )


def test_fastest_laps_chart(fastest):
    spec = _spec(charts.fastest_laps_chart(fastest))

    assert len(spec["layer"]) == 3
    rows = next(iter(spec["datasets"].values()))
    assert rows[0]["position"] == "1º · VER"
    assert rows[0]["text"] == "1:35.100"
    assert rows[1]["text"] == "1:35.200  (+0.100)"


def test_driver_podium_chart(fastest):
    spec = _spec(charts.driver_podium_chart(fastest))

    assert spec["mark"]["type"] == "bar"
    assert spec["encoding"]["y"]["sort"][0] in {"VER", "PER"}
