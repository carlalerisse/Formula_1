"""Fixtures compartilhadas: payloads de exemplo e transporte HTTP falso."""

from collections.abc import Callable

import httpx
import pytest

from formula1.adapters.openf1_client import ClientSettings, OpenF1Client

Handler = Callable[[httpx.Request], httpx.Response]


@pytest.fixture
def make_client() -> Callable[..., tuple[OpenF1Client, list[float]]]:
    """Cria um ``OpenF1Client`` sobre ``httpx.MockTransport``, sem rede.

    Retorna o cliente e a lista com as esperas solicitadas ao ``sleep`` falso.
    """
    created: list[httpx.Client] = []

    def factory(
        handler: Handler, **settings: float
    ) -> tuple[OpenF1Client, list[float]]:
        sleeps: list[float] = []
        http = httpx.Client(transport=httpx.MockTransport(handler))
        created.append(http)
        options = {"request_interval": 0.0, "backoff_factor": 1.0, **settings}
        client = OpenF1Client(
            ClientSettings(base_url="https://api.test/v1", **options),
            client=http,
            sleep=sleeps.append,
        )
        return client, sleeps

    yield factory
    for http in created:
        http.close()


@pytest.fixture
def meetings_payload() -> list[dict]:
    return [
        {
            "meeting_key": 1140,
            "meeting_name": "Bahrain Grand Prix",
            "year": 2023,
            "date_start": "2023-03-03T11:30:00+00:00",
            "country_name": "Bahrain",
            "is_cancelled": False,
        },
        {
            "meeting_key": 1999,
            "meeting_name": "Cancelled Grand Prix",
            "year": 2023,
            "date_start": "2023-05-19T11:30:00+00:00",
            "country_name": "Italy",
            "is_cancelled": True,
        },
    ]


@pytest.fixture
def sessions_payload() -> list[dict]:
    return [
        {
            "session_key": 7763,
            "meeting_key": 1140,
            "year": 2023,
            "session_name": "Practice 1",
            "session_type": "Practice",
            "date_start": "2023-03-03T11:30:00+00:00",
            "date_end": "2023-03-03T12:30:00+00:00",
        },
        {
            "session_key": 7953,
            "meeting_key": 1140,
            "year": 2023,
            "session_name": "Race",
            "session_type": "Race",
            "date_start": "2023-03-05T15:00:00+00:00",
            "date_end": "2023-03-05T17:00:00+00:00",
        },
    ]


@pytest.fixture
def laps_payload() -> list[dict]:
    return [
        {
            "meeting_key": 1140,
            "session_key": 7953,
            "driver_number": 1,
            "lap_number": 1,
            "date_start": "2023-03-05T15:03:46.123000+00:00",
            "lap_duration": 99.019,
            "duration_sector_1": None,
            "duration_sector_2": 41.2,
            "duration_sector_3": 25.1,
            "i1_speed": 260,
            "i2_speed": 251,
            "st_speed": 282,
            "is_pit_out_lap": False,
            "segments_sector_1": [2048, 2049, None],
            "segments_sector_2": [2051, 2049],
            "segments_sector_3": None,
        },
        {
            "meeting_key": 1140,
            "session_key": 7953,
            "driver_number": 1,
            "lap_number": 2,
            "date_start": "2023-03-05T15:05:25.142000+00:00",
            "lap_duration": None,
            "duration_sector_1": 32.1,
            "duration_sector_2": 41.0,
            "duration_sector_3": 25.0,
            "i1_speed": None,
            "i2_speed": 249,
            "st_speed": 280,
            "is_pit_out_lap": True,
            "segments_sector_1": None,
            "segments_sector_2": None,
            "segments_sector_3": None,
        },
    ]


@pytest.fixture
def intervals_payload() -> list[dict]:
    return [
        {
            "meeting_key": 1140,
            "session_key": 7953,
            "date": "2023-03-05T15:10:00.000000+00:00",
            "driver_number": 1,
            "gap_to_leader": None,
            "interval": None,
        },
        {
            "meeting_key": 1140,
            "session_key": 7953,
            "date": "2023-03-05T15:10:00.500000+00:00",
            "driver_number": 11,
            "gap_to_leader": 11.987,
            "interval": 11.987,
        },
        {
            "meeting_key": 1140,
            "session_key": 7953,
            "date": "2023-03-05T15:10:01.000000+00:00",
            "driver_number": 2,
            "gap_to_leader": "+1 LAP",
            "interval": "+12.3",
        },
    ]


@pytest.fixture
def session_result_quali_payload() -> list[dict]:
    return [
        {
            "meeting_key": 1140,
            "session_key": 7779,
            "driver_number": 1,
            "position": 1,
            "number_of_laps": 18,
            "duration": [91.295, 90.503, 89.708],
            "gap_to_leader": [0, 0, 0],
            "dnf": False,
            "dns": False,
            "dsq": False,
        },
        {
            "meeting_key": 1140,
            "session_key": 7779,
            "driver_number": 2,
            "position": 20,
            "number_of_laps": 6,
            "duration": [92.181, None, None],
            "gap_to_leader": [0.886, None, None],
            "dnf": False,
            "dns": False,
            "dsq": False,
        },
    ]
