import math

import pandas as pd
import pytest

from formula1.domain.endpoints import get_endpoint
from formula1.domain.transform import parse_gap, parse_laps_behind, to_dataframe

# --- parse_gap / parse_laps_behind --------------------------------------------


@pytest.mark.parametrize(
    ("value", "seconds", "laps"),
    [
        (None, None, None),
        (float("nan"), None, None),
        (0, 0.0, 0),
        (11.987, 11.987, 0),
        ("+12.3", 12.3, 0),
        (" 0.5 ", 0.5, 0),
        ("+1 LAP", None, 1),
        ("+3 LAPS", None, 3),
        ("2 laps", None, 2),
    ],
)
def test_parse_gap_valores_validos(value, seconds, laps):
    assert parse_gap(value) == seconds
    assert parse_laps_behind(value) == laps


@pytest.mark.parametrize(
    "value", ["abc", "+X LAPS", "", "inf", True, [1, 2], {"a": 1}, float("inf")]
)
def test_parse_gap_valor_invalido_lanca_erro(value):
    with pytest.raises(ValueError, match="Gap inválido"):
        parse_gap(value)


def test_parse_laps_behind_valor_invalido_lanca_erro():
    with pytest.raises(ValueError, match="Gap inválido"):
        parse_laps_behind("DNF")


# --- to_dataframe -------------------------------------------------------------


def test_to_dataframe_datas_em_utc(laps_payload):
    frame = to_dataframe(laps_payload, "laps")

    assert str(frame["date_start"].dt.tz) == "UTC"
    assert frame.loc[0, "date_start"] == pd.Timestamp("2023-03-05T15:03:46.123Z")


def test_to_dataframe_tipos_anulaveis(laps_payload):
    frame = to_dataframe(laps_payload, "laps")

    assert frame["driver_number"].dtype == "Int64"
    assert frame["i1_speed"].dtype == "Int64"
    assert pd.isna(frame.loc[1, "i1_speed"])
    assert frame["lap_duration"].dtype == "float64"
    assert frame["is_pit_out_lap"].dtype == "boolean"
    assert frame.loc[0, "segments_sector_1"] == [2048, 2049, None]
    assert frame.loc[0, "segments_sector_3"] is None


def test_to_dataframe_lista_vazia_gera_schema_esperado():
    frame = to_dataframe([], "laps")

    assert frame.empty
    assert list(frame.columns) == list(get_endpoint("laps").columns)
    assert frame["lap_number"].dtype == "Int64"
    assert str(frame["date_start"].dt.tz) == "UTC"


def test_to_dataframe_adiciona_colunas_ausentes():
    frame = to_dataframe([{"session_key": 1, "driver_number": 44}], "pit")

    assert "stop_duration" in frame.columns
    assert frame["stop_duration"].dtype == "float64"
    assert math.isnan(frame.loc[0, "stop_duration"])


@pytest.mark.parametrize(
    ("endpoint", "field"),
    [("drivers", "country_code"), ("pit", "pit_duration")],
)
def test_to_dataframe_remove_campos_depreciados(endpoint, field):
    records = [{"session_key": 1, "driver_number": 1, field: "X"}]

    frame = to_dataframe(records, endpoint)

    assert field not in frame.columns


def test_to_dataframe_preserva_campos_extras():
    frame = to_dataframe([{"session_key": 1, "new_field": "abc"}], "weather")

    assert frame.loc[0, "new_field"] == "abc"
    assert frame["new_field"].dtype == "string"


def test_to_dataframe_intervals_gera_colunas_de_gap(intervals_payload):
    frame = to_dataframe(intervals_payload, "intervals")

    assert frame["gap_to_leader_seconds"].tolist()[1] == 11.987
    assert math.isnan(frame["gap_to_leader_seconds"].tolist()[0])
    assert math.isnan(frame["gap_to_leader_seconds"].tolist()[2])
    assert frame["gap_to_leader_laps_behind"].tolist() == [pd.NA, 0, 1]
    assert frame["interval_seconds"].tolist()[2] == 12.3
    assert frame["gap_to_leader"].tolist() == [pd.NA, "11.987", "+1 LAP"]


def test_to_dataframe_gap_invalido_vira_nulo(caplog):
    records = [{"session_key": 1, "gap_to_leader": "???", "interval": 1.0}]

    frame = to_dataframe(records, "intervals")

    assert math.isnan(frame.loc[0, "gap_to_leader_seconds"])
    assert "inválido" in caplog.text


def test_to_dataframe_session_result_explode_q1_q2_q3(session_result_quali_payload):
    frame = to_dataframe(session_result_quali_payload, "session_result")

    assert frame.loc[0, ["duration_q1", "duration_q2", "duration_q3"]].tolist() == [
        91.295,
        90.503,
        89.708,
    ]
    assert math.isnan(frame.loc[1, "duration_q2"])
    assert frame.loc[1, "gap_to_leader_q1"] == 0.886
    assert frame["duration"].isna().all()
    assert frame["gap_to_leader_seconds"].isna().all()
    assert frame.loc[0, "gap_to_leader"] == "[0, 0, 0]"


def test_to_dataframe_session_result_corrida():
    records = [
        {"session_key": 1, "driver_number": 1, "duration": 5600.1, "gap_to_leader": 0},
        {
            "session_key": 1,
            "driver_number": 2,
            "duration": None,
            "gap_to_leader": "+2 LAPS",
        },
    ]

    frame = to_dataframe(records, "session_result")

    assert frame.loc[0, "duration"] == 5600.1
    assert frame["gap_to_leader_laps_behind"].tolist() == [0, 2]
    assert frame["duration_q1"].isna().all()


def test_to_dataframe_inteiro_com_fracao_vira_float():
    frame = to_dataframe(
        [{"session_key": 1, "humidity": 45, "rainfall": 0.5}], "weather"
    )

    assert frame["rainfall"].dtype == "float64"
    assert frame.loc[0, "rainfall"] == 0.5


def test_to_dataframe_endpoint_desconhecido_lanca_erro():
    with pytest.raises(ValueError, match="Endpoint desconhecido"):
        to_dataframe([], "nao_existe")
