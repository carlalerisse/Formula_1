import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from formula1.adapters.storage import PartitionKeys, Storage
from formula1.domain.transform import to_dataframe


@pytest.fixture
def storage(tmp_path):
    return Storage(tmp_path)


SESSION = PartitionKeys(2023, 1140, 7953)


def test_partition_keys_session_sem_meeting_lanca_erro():
    with pytest.raises(ValueError, match="session_key exige meeting_key"):
        PartitionKeys(2023, session_key=1)


@pytest.mark.parametrize(
    ("keys", "raw", "parquet"),
    [
        (
            SESSION,
            "raw/laps/year=2023/meeting_key=1140/session_key=7953.json",
            "processed/laps/year=2023/meeting_key=1140/session_key=7953/part.parquet",
        ),
        (
            PartitionKeys(2023, 1140),
            "raw/laps/year=2023/meeting_key=1140.json",
            "processed/laps/year=2023/meeting_key=1140/part.parquet",
        ),
        (
            PartitionKeys(2023),
            "raw/laps/year=2023.json",
            "processed/laps/year=2023/part.parquet",
        ),
    ],
)
def test_caminhos_de_particao(storage, tmp_path, keys, raw, parquet):
    assert storage.raw_path("laps", keys) == tmp_path / raw
    assert storage.parquet_path("laps", keys) == tmp_path / parquet


def test_save_raw_e_load_raw(storage):
    records = [{"lap_number": 1, "team_name": "Red Bull Racing", "nome": "São Paulo"}]

    path = storage.save_raw("laps", SESSION, records)

    assert path.is_file()
    assert storage.load_raw("laps", SESSION) == records


def test_exists_marca_idempotencia(storage):
    assert not storage.exists("laps", SESSION)

    storage.save_raw("laps", SESSION, [])

    assert storage.exists("laps", SESSION)
    assert not storage.exists("stints", SESSION)


def test_save_raw_nao_deixa_temporarios(storage):
    path = storage.save_raw("laps", SESSION, [{"a": 1}])

    assert [p.name for p in path.parent.iterdir()] == [path.name]


def test_load_raw_inexistente_lanca_erro(storage):
    with pytest.raises(FileNotFoundError):
        storage.load_raw("laps", SESSION)


def test_save_parquet_remove_colunas_de_particao(storage, laps_payload):
    frame = to_dataframe(laps_payload, "laps")

    path = storage.save_parquet("laps", SESSION, frame)

    names = pq.read_schema(path).names
    assert "session_key" not in names
    assert "meeting_key" not in names
    assert "lap_number" in names


def test_save_parquet_listas_viram_list_int64(storage, laps_payload):
    frame = to_dataframe(laps_payload, "laps")

    path = storage.save_parquet("laps", SESSION, frame)

    schema = pq.read_schema(path)
    for column in ("segments_sector_1", "segments_sector_3"):
        assert schema.field(column).type == pa.list_(pa.int64())


def test_save_parquet_le_dataset_particionado(storage, tmp_path, laps_payload):
    other = PartitionKeys(2023, 1141, 8000)
    race = [dict(item, segments_sector_1=None) for item in laps_payload]
    storage.save_parquet("laps", other, to_dataframe(race, "laps"))
    storage.save_parquet("laps", SESSION, to_dataframe(laps_payload, "laps"))

    frame = pd.read_parquet(tmp_path / "processed" / "laps")

    assert len(frame) == 4
    assert sorted(frame["session_key"].astype(int).unique()) == [7953, 8000]
    assert set(frame["year"].astype(int)) == {2023}


def test_save_parquet_sobrescreve_arquivo(storage, laps_payload):
    frame = to_dataframe(laps_payload, "laps")
    storage.save_parquet("laps", SESSION, frame)

    path = storage.save_parquet("laps", SESSION, frame.head(1))

    assert pq.read_metadata(path).num_rows == 1
