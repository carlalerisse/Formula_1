import pytest

from formula1.domain.endpoints import (
    DEFAULT_ENDPOINTS,
    ENDPOINTS,
    get_endpoint,
    is_race,
    parse_endpoints,
)


def test_endpoints_padrao_nao_incluem_alto_volume():
    assert "car_data" not in DEFAULT_ENDPOINTS
    assert "location" not in DEFAULT_ENDPOINTS
    assert all(name in ENDPOINTS for name in DEFAULT_ENDPOINTS)


@pytest.mark.parametrize("value", [None, "", "   "])
def test_parse_endpoints_vazio_usa_padrao(value):
    assert parse_endpoints(value) == DEFAULT_ENDPOINTS


def test_parse_endpoints_remove_espacos_e_repeticoes():
    assert parse_endpoints(" laps, stints,laps,") == ("laps", "stints")


def test_parse_endpoints_desconhecido_lanca_erro():
    with pytest.raises(ValueError, match="Endpoint desconhecido: 'lapz'"):
        parse_endpoints("laps,lapz")


def test_get_endpoint_marca_endpoints_de_corrida():
    assert get_endpoint("intervals").race_only
    assert get_endpoint("championship_teams").race_only
    assert not get_endpoint("laps").race_only
    assert get_endpoint("car_data").per_driver


@pytest.mark.parametrize(
    ("session_type", "expected"),
    [("Race", True), ("Qualifying", False), ("race", False), (None, False)],
)
def test_is_race(session_type, expected):
    assert is_race(session_type) is expected
