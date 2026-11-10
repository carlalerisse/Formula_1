import pandas as pd

from formula1.adapters.storage import PartitionKeys
from formula1.dashboard import data
from tests.unit.conftest import MEETING, QUALI, RACE, YEAR


def test_available_years(data_dir):
    (data_dir / "processed" / "laps" / "year=2024").mkdir()
    (data_dir / "processed" / "laps" / "lixo").mkdir()

    assert data.available_years(data_dir) == [2024, 2023]


def test_available_years_sem_dados(tmp_path):
    assert data.available_years(tmp_path) == []


def test_read_partition_recoloca_chaves(data_dir):
    frame = data.read_partition(data_dir, "laps", PartitionKeys(YEAR, MEETING, RACE))

    assert len(frame) == 10
    assert set(frame["session_key"]) == {RACE}
    assert set(frame["year"]) == {YEAR}
    assert frame["meeting_key"].dtype == "Int64"


def test_read_partition_inexistente_devolve_vazio(data_dir):
    frame = data.read_partition(data_dir, "laps", PartitionKeys(YEAR, MEETING, 1))

    assert frame.empty


def test_was_extracted(data_dir):
    race = PartitionKeys(YEAR, MEETING, RACE)
    quali = PartitionKeys(YEAR, MEETING, QUALI)

    assert data.was_extracted(data_dir, "pit", race)
    assert not data.was_extracted(data_dir, "pit", quali)


def test_available_sessions_com_catalogos(data_dir):
    sessions = data.available_sessions(data_dir, YEAR)

    assert list(sessions.columns) == list(data.SESSION_COLUMNS)
    assert sessions["session_key"].tolist() == [QUALI, RACE]
    assert sessions["label"].tolist() == [
        "Bahrain Grand Prix · Qualifying",
        "Bahrain Grand Prix · Race",
    ]


def test_available_sessions_sem_catalogos(data_dir):
    for catalog in ("meetings", "sessions"):
        for file in (data_dir / "processed" / catalog).rglob("*.parquet"):
            file.unlink()

    sessions = data.available_sessions(data_dir, YEAR)

    assert sessions["label"].tolist() == [
        f"Meeting {MEETING} · Sessão {QUALI}",
        f"Meeting {MEETING} · Sessão {RACE}",
    ]
    assert sessions["session_name"].isna().all()


def test_available_sessions_catalogo_sem_colunas_de_nome(data_dir):
    path = data_dir / "processed" / "meetings" / f"year={YEAR}" / "part.parquet"
    pd.DataFrame({"meeting_key": [MEETING]}).to_parquet(path)

    sessions = data.available_sessions(data_dir, YEAR)

    assert sessions["label"].iloc[1] == f"Meeting {MEETING} · Race"


def test_available_sessions_ano_sem_dados(data_dir, tmp_path):
    assert data.available_sessions(data_dir, 2030).empty
    assert data.available_sessions(tmp_path / "vazio", YEAR).empty


def test_session_partitions(data_dir):
    keys = data.session_partitions(data_dir, "laps", [YEAR, 2030])

    assert keys == [
        PartitionKeys(YEAR, MEETING, QUALI),
        PartitionKeys(YEAR, MEETING, RACE),
    ]


def test_read_sessions_concatena_e_filtra_colunas(data_dir):
    frame = data.read_sessions(
        data_dir, "laps", [YEAR], ["driver_number", "lap_duration", "inexistente"]
    )

    assert len(frame) == 12
    assert set(frame.columns) == {
        "driver_number",
        "lap_duration",
        "year",
        "meeting_key",
        "session_key",
    }
    assert set(frame["session_key"]) == {QUALI, RACE}


def test_read_sessions_sem_dados(data_dir):
    assert data.read_sessions(data_dir, "laps", [2030]).empty


def test_read_catalogs(data_dir):
    sessions, meetings = data.read_catalogs(data_dir, [YEAR, 2030])

    assert set(sessions["session_key"]) == {QUALI, RACE}
    assert meetings["meeting_name"].tolist() == ["Bahrain Grand Prix"]
