"""Fixtures do dashboard: um diretório de dados gravado pelo próprio Storage."""

import pytest

from formula1.adapters.storage import PartitionKeys, Storage
from formula1.domain.transform import to_dataframe

YEAR = 2023
MEETING = 1141
RACE = 7953
QUALI = 7779


def _save(storage: Storage, endpoint: str, keys: PartitionKeys, records: list[dict]):
    storage.save_parquet(endpoint, keys, to_dataframe(records, endpoint))
    storage.save_raw(endpoint, keys, records)


@pytest.fixture
def session_frames():
    """Payloads de uma corrida com três pilotos."""
    drivers = [
        {
            "driver_number": 1,
            "name_acronym": "VER",
            "full_name": "Max VERSTAPPEN",
            "team_name": "Red Bull Racing",
            "team_colour": "3671C6",
        },
        {
            "driver_number": 11,
            "name_acronym": "PER",
            "full_name": "Sergio PEREZ",
            "team_name": "Red Bull Racing",
            "team_colour": "3671C6",
        },
        {
            "driver_number": 14,
            "name_acronym": "ALO",
            "full_name": "Fernando ALONSO",
            "team_name": "Aston Martin",
            "team_colour": None,
        },
    ]
    laps = [
        {
            "driver_number": n,
            "lap_number": lap,
            "lap_duration": base + lap * 0.1,
            "is_pit_out_lap": lap == 3,
        }
        for n, base in ((1, 95.0), (11, 95.5), (14, 96.0))
        for lap in (1, 2, 3)
    ]
    laps.append(
        {
            "driver_number": 1,
            "lap_number": 4,
            "lap_duration": 130.0,
            "is_pit_out_lap": False,
        }
    )
    stints = [
        {
            "driver_number": 1,
            "stint_number": 1,
            "lap_start": 1,
            "lap_end": 2,
            "compound": "SOFT",
            "tyre_age_at_start": 3,
        },
        {
            "driver_number": 1,
            "stint_number": 2,
            "lap_start": 3,
            "lap_end": None,
            "compound": "hard",
            "tyre_age_at_start": 0,
        },
        {
            "driver_number": 11,
            "stint_number": 1,
            "lap_start": 1,
            "lap_end": 4,
            "compound": None,
            "tyre_age_at_start": 0,
        },
    ]
    position = [
        {"driver_number": 1, "date": "2023-03-05T15:03:00+00:00", "position": 1},
        {"driver_number": 11, "date": "2023-03-05T15:03:00+00:00", "position": 2},
        {"driver_number": 14, "date": "2023-03-05T15:03:00+00:00", "position": 3},
        {"driver_number": 14, "date": "2023-03-05T15:30:00+00:00", "position": 2},
        {"driver_number": 11, "date": "2023-03-05T15:30:00+00:00", "position": 3},
    ]
    pit = [
        {
            "driver_number": 1,
            "lap_number": 2,
            "lane_duration": 22.1,
            "stop_duration": 2.4,
            "date": "2023-03-05T15:20:00+00:00",
        },
    ]
    result = [
        {
            "driver_number": 11,
            "position": 2,
            "number_of_laps": 4,
            "duration": 400.1,
            "gap_to_leader": 11.987,
            "dnf": False,
            "dns": False,
            "dsq": False,
        },
        {
            "driver_number": 1,
            "position": 1,
            "number_of_laps": 4,
            "duration": 388.1,
            "gap_to_leader": 0,
            "dnf": False,
            "dns": False,
            "dsq": False,
        },
        {
            "driver_number": 14,
            "position": None,
            "number_of_laps": 1,
            "duration": None,
            "gap_to_leader": None,
            "dnf": True,
            "dns": False,
            "dsq": False,
        },
    ]
    return {
        "drivers": drivers,
        "laps": laps,
        "stints": stints,
        "position": position,
        "pit": pit,
        "session_result": result,
    }


@pytest.fixture
def data_dir(tmp_path, session_frames):
    """Diretório com catálogos, uma corrida completa e uma classificação só com laps."""
    storage = Storage(tmp_path)
    race = PartitionKeys(YEAR, MEETING, RACE)
    for endpoint, records in session_frames.items():
        _save(storage, endpoint, race, records)
    _save(
        storage, "laps", PartitionKeys(YEAR, MEETING, QUALI), session_frames["laps"][:2]
    )
    _save(
        storage,
        "meetings",
        PartitionKeys(YEAR),
        [
            {
                "meeting_key": MEETING,
                "meeting_name": "Bahrain Grand Prix",
                "year": YEAR,
            },
        ],
    )
    _save(
        storage,
        "sessions",
        PartitionKeys(YEAR, MEETING),
        [
            {
                "session_key": QUALI,
                "meeting_key": MEETING,
                "session_name": "Qualifying",
                "session_type": "Qualifying",
                "circuit_short_name": "Sakhir",
                "date_start": "2023-03-04T15:00:00+00:00",
            },
            {
                "session_key": RACE,
                "meeting_key": MEETING,
                "session_name": "Race",
                "session_type": "Race",
                "circuit_short_name": "Sakhir",
                "date_start": "2023-03-05T15:00:00+00:00",
            },
        ],
    )
    return tmp_path
