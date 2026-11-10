import pandas as pd
import pytest

from formula1.domain import analytics
from formula1.domain.transform import to_dataframe


@pytest.fixture
def frames(session_frames):
    return {ep: to_dataframe(records, ep) for ep, records in session_frames.items()}


@pytest.fixture
def labels(frames):
    return analytics.driver_labels(frames["drivers"])


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [
        (91.447, "1:31.447"),
        (60.0, "1:00.000"),
        (5.2, "5.200"),
        (3725.5, "62:05.500"),
        (None, "—"),
        (float("nan"), "—"),
        (float("inf"), "—"),
        (-1.0, "—"),
    ],
)
def test_format_lap_time(seconds, expected):
    assert analytics.format_lap_time(seconds) == expected


def test_driver_labels_usa_sigla_e_cor_da_equipe(labels):
    assert labels["label"].tolist() == ["VER", "PER", "ALO"]
    assert labels["color"].tolist() == ["#3671C6", "#3671C6", analytics.DEFAULT_COLOR]
    assert list(labels.columns) == list(analytics.LABEL_COLUMNS)


def test_driver_labels_sem_sigla_usa_numero():
    drivers = to_dataframe([{"driver_number": 44}, {"driver_number": 44}], "drivers")

    labels = analytics.driver_labels(drivers)

    assert labels["label"].tolist() == ["#44"]
    assert labels["full_name"].tolist() == ["#44"]


@pytest.mark.parametrize("drivers", [pd.DataFrame(), pd.DataFrame({"x": [1]})])
def test_driver_labels_vazio(drivers):
    assert analytics.driver_labels(drivers).empty


def test_attach_labels_piloto_desconhecido(labels):
    frame = pd.DataFrame({"driver_number": [1, 99, None]})

    result = analytics.attach_labels(frame, labels)

    assert result["label"].tolist() == ["VER", "#99"]
    assert result["color"].tolist()[1] == analytics.DEFAULT_COLOR


def test_lap_times_remove_pit_out_e_voltas_lentas(frames, labels):
    result = analytics.lap_times(frames["laps"], labels)

    assert 130.0 not in result["lap_duration"].tolist()
    assert 3 not in result["lap_number"].tolist()
    assert len(result) == 6


def test_lap_times_mantem_tudo_quando_pedido(frames, labels):
    result = analytics.lap_times(
        frames["laps"], labels, include_pit_out=True, max_ratio=None
    )

    assert len(result) == 10
    assert result["label"].iloc[0] == "VER"


def test_lap_times_ratio_invalido_lanca_erro(frames, labels):
    with pytest.raises(ValueError, match="max_ratio deve ser >= 1"):
        analytics.lap_times(frames["laps"], labels, max_ratio=0.9)


@pytest.mark.parametrize(
    "function",
    [
        analytics.lap_times,
        analytics.tyre_stints,
        analytics.position_timeline,
        analytics.result_table,
    ],
)
def test_funcoes_aceitam_dataframe_vazio(function, labels):
    result = function(pd.DataFrame(), labels)

    assert result.empty
    assert "label" in result.columns


def test_tyre_stints_normaliza_composto_e_voltas(frames, labels):
    result = analytics.tyre_stints(frames["stints"], labels)

    assert result["compound"].tolist() == ["SOFT", "HARD", "UNKNOWN"]
    assert result["lap_end"].tolist() == [2, 3, 4]
    assert result["laps"].tolist() == [2, 1, 4]


def test_tyre_stints_composto_desconhecido_vira_unknown(labels):
    stints = to_dataframe(
        [
            {
                "driver_number": 1,
                "lap_start": 1,
                "lap_end": 5,
                "compound": "TEST_UNKNOWN",
            }
        ],
        "stints",
    )

    assert analytics.tyre_stints(stints, labels)["compound"].tolist() == ["UNKNOWN"]


def test_position_timeline_ordem_cronologica(frames, labels):
    result = analytics.position_timeline(frames["position"], labels)

    assert result["label"].tolist() == ["VER", "PER", "ALO", "ALO", "PER"]
    assert result["date"].is_monotonic_increasing


def test_result_table_ordena_e_marca_status(frames, labels):
    result = analytics.result_table(frames["session_result"], labels)

    assert result["label"].tolist() == ["VER", "PER", "ALO"]
    assert result["status"].tolist() == ["", "", "DNF"]


def test_summarize(frames, labels):
    summary = analytics.summarize(
        frames["session_result"], frames["laps"], frames["pit"], labels
    )

    assert summary == analytics.SessionSummary(
        winner="VER",
        fastest_driver="VER",
        fastest_lap=95.1,
        total_laps=4,
        pit_stops=1,
    )


def test_summarize_sem_dados(labels):
    empty = pd.DataFrame()

    summary = analytics.summarize(empty, empty, empty, labels)

    assert summary == analytics.SessionSummary(None, None, None, None, None)


@pytest.fixture
def circuit_inputs(frames):
    """Voltas de duas sessões (uma sem cadastro de pilotos) e os catálogos."""
    race = frames["laps"].assign(year=2023, meeting_key=1141, session_key=7953)
    quali = frames["laps"].assign(year=2023, meeting_key=1141, session_key=7779)
    quali["lap_duration"] = quali["lap_duration"] - 1.0
    other = pd.DataFrame(
        {
            "driver_number": [44],
            "lap_number": [5],
            "lap_duration": [80.0],
            "is_pit_out_lap": [False],
            "year": [2024],
            "meeting_key": [1229],
            "session_key": [9000],
        }
    )
    sessions = pd.DataFrame(
        {
            "session_key": [7953, 7779],
            "meeting_key": [1141, 1141],
            "session_name": ["Race", "Qualifying"],
            "session_type": ["Race", "Qualifying"],
            "circuit_short_name": ["Sakhir", "Sakhir"],
        }
    )
    meetings = pd.DataFrame(
        {
            "meeting_key": [1141, 1229],
            "meeting_name": ["Bahrain Grand Prix", "Saudi Arabian Grand Prix"],
        }
    )
    drivers = frames["drivers"].assign(session_key=7953)
    return {
        "laps": pd.concat([race, quali, other], ignore_index=True),
        "sessions": sessions,
        "meetings": meetings,
        "drivers": drivers,
    }


def test_fastest_laps_by_circuit_top_5(circuit_inputs):
    top = analytics.fastest_laps_by_circuit(**circuit_inputs)

    assert list(top.columns) == list(analytics.FASTEST_LAP_COLUMNS)
    sakhir = top[top["circuit"] == "Sakhir"]
    assert sakhir["rank"].tolist() == [1, 2, 3, 4, 5]
    assert sakhir["lap_duration"].tolist() == pytest.approx(
        [94.1, 94.2, 94.6, 94.7, 95.1]
    )
    assert sakhir["gap"].tolist() == pytest.approx([0, 0.1, 0.5, 0.6, 1.0])
    # A classificação não tem drivers: herda a sigla da corrida.
    assert sakhir["label"].tolist() == ["VER", "VER", "PER", "PER", "ALO"]
    assert sakhir["session_name"].iloc[0] == "Qualifying"
    assert sakhir["meeting_name"].iloc[0] == "Bahrain Grand Prix"
    assert not (sakhir["lap_number"] == 3).any()  # voltas de saída do pit


def test_fastest_laps_by_circuit_sem_catalogo_usa_nome_do_evento(circuit_inputs):
    top = analytics.fastest_laps_by_circuit(**circuit_inputs)

    other = top[top["circuit"] == "Saudi Arabian Grand Prix"]
    assert other["label"].tolist() == ["#44"]
    assert other["color"].tolist() == [analytics.DEFAULT_COLOR]


def test_fastest_laps_by_circuit_filtros(circuit_inputs):
    top = analytics.fastest_laps_by_circuit(
        **circuit_inputs, session_names=["Race"], one_per_driver=True, top_n=2
    )

    assert top["circuit"].tolist() == ["Sakhir", "Sakhir"]
    assert top["label"].tolist() == ["VER", "PER"]
    assert top["lap_duration"].tolist() == pytest.approx([95.1, 95.6])


def test_fastest_laps_by_circuit_sem_dados():
    empty = pd.DataFrame()

    top = analytics.fastest_laps_by_circuit(empty, empty, empty, empty)

    assert top.empty
    assert list(top.columns) == list(analytics.FASTEST_LAP_COLUMNS)


def test_fastest_laps_by_circuit_filtro_sem_resultado(circuit_inputs):
    top = analytics.fastest_laps_by_circuit(**circuit_inputs, session_names=[])

    assert top.empty


def test_fastest_laps_by_circuit_top_n_invalido(circuit_inputs):
    with pytest.raises(ValueError, match="top_n"):
        analytics.fastest_laps_by_circuit(**circuit_inputs, top_n=0)


def test_session_driver_labels(frames):
    drivers = pd.concat(
        [
            frames["drivers"].assign(session_key=1),
            frames["drivers"].assign(session_key=2),
        ]
    )

    labels = analytics.session_driver_labels(drivers)

    assert len(labels) == 6
    assert set(labels["session_key"]) == {1, 2}
    assert analytics.session_driver_labels(pd.DataFrame()).empty
