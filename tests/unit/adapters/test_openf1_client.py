import httpx
import pytest

from formula1.adapters.openf1_client import (
    Filter,
    OpenF1Client,
    OpenF1Error,
    build_query,
)


def _json(status: int, payload: object, **headers: str) -> httpx.Response:
    return httpx.Response(status, json=payload, headers=headers)


# --- Filter / build_query -----------------------------------------------------


@pytest.mark.parametrize(
    ("filters", "expected"),
    [
        ([Filter("session_key", "=", 9161)], "session_key=9161"),
        ([Filter("lap_duration", ">=", 120)], "lap_duration>=120"),
        ([Filter("position", "<=", 3)], "position<=3"),
        ([Filter("interval", ">", 0)], "interval>0"),
        ([Filter("interval", "<", 0.005)], "interval<0.005"),
        (
            [Filter("driver_number", "=", [4, 81])],
            "driver_number=4&driver_number=81",
        ),
        (
            [Filter("session_name", "=", "Sprint Qualifying")],
            "session_name=Sprint%20Qualifying",
        ),
        ([Filter("is_cancelled", "=", False)], "is_cancelled=false"),
        (
            [
                Filter("date", ">=", "2023-09-01"),
                Filter("date", "<", "2023-09-30"),
            ],
            "date>=2023-09-01&date<2023-09-30",
        ),
        ([], ""),
    ],
)
def test_build_query_operadores_e_valores(filters, expected):
    assert build_query(filters) == expected


def test_build_query_codifica_mais_do_fuso_horario():
    query = build_query([Filter("date", ">", "2023-09-16T13:03:35+00:00")])

    assert query == "date>2023-09-16T13%3A03%3A35%2B00%3A00"


@pytest.mark.parametrize("op", ["==", "!=", "=>", "like", ""])
def test_filter_operador_invalido_lanca_erro(op):
    with pytest.raises(ValueError, match="Operador inválido"):
        Filter("position", op, 1)


@pytest.mark.parametrize("field", ["", "1abc", "a b", "x&y=1"])
def test_filter_campo_invalido_lanca_erro(field):
    with pytest.raises(ValueError, match="Campo de filtro inválido"):
        Filter(field, "=", 1)


def test_filter_lista_vazia_lanca_erro():
    with pytest.raises(ValueError, match="ao menos um valor"):
        Filter("driver_number", "=", [])


# --- OpenF1Client -------------------------------------------------------------


def test_get_monta_url_e_devolve_registros(make_client):
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return _json(200, [{"lap_number": 1}])

    client, _ = make_client(handler)

    result = client.get(
        "laps", [Filter("session_key", "=", 9161), Filter("lap_duration", ">=", 90)]
    )

    assert result == [{"lap_number": 1}]
    assert len(seen) == 1
    assert seen[0].startswith("https://api.test/v1/laps?session_key=9161&lap_duration")
    assert seen[0].endswith("90")


def test_build_url_sem_filtros(make_client):
    client, _ = make_client(lambda _r: _json(200, []))

    assert client.build_url("meetings") == "https://api.test/v1/meetings"


@pytest.mark.parametrize("endpoint", ["", "../etc", "laps?x=1", "laps/1"])
def test_get_endpoint_invalido_lanca_erro(make_client, endpoint):
    client, _ = make_client(lambda _r: _json(200, []))

    with pytest.raises(ValueError, match="Endpoint inválido"):
        client.get(endpoint)


@pytest.mark.parametrize("status", [429, 500, 502, 503])
def test_get_repete_em_429_e_5xx(make_client, status):
    responses = iter([_json(status, {"detail": "busy"}), _json(200, [{"ok": 1}])])
    client, sleeps = make_client(lambda _r: next(responses))

    result = client.get("laps")

    assert result == [{"ok": 1}]
    assert sleeps == [1.0]


def test_get_backoff_exponencial(make_client):
    responses = iter([_json(500, {})] * 3 + [_json(200, [])])
    client, sleeps = make_client(lambda _r: next(responses), backoff_factor=0.5)

    client.get("laps")

    assert sleeps == [0.5, 1.0, 2.0]


def test_get_respeita_retry_after(make_client):
    responses = iter([_json(429, {}, **{"Retry-After": "7"}), _json(200, [])])
    client, sleeps = make_client(lambda _r: next(responses))

    client.get("laps")

    assert sleeps == [7.0]


def test_get_esgota_tentativas_e_lanca_erro(make_client):
    calls: list[int] = []

    def handler(_request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return _json(503, {"detail": "down"})

    client, _ = make_client(handler, max_retries=2)

    with pytest.raises(OpenF1Error, match="HTTP 503") as info:
        client.get("laps")

    assert info.value.status_code == 503
    assert len(calls) == 3


def test_get_404_lanca_erro_sem_retry(make_client):
    calls: list[int] = []

    def handler(_request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return _json(404, {"detail": "Not Found"})

    client, sleeps = make_client(handler)

    with pytest.raises(OpenF1Error, match="HTTP 404") as info:
        client.get("unknown_endpoint")

    assert info.value.status_code == 404
    assert len(calls) == 1
    assert sleeps == []


def test_get_404_sem_resultados_vira_lista_vazia(make_client):
    client, _ = make_client(lambda _r: _json(404, {"detail": "No results found."}))

    assert client.get("laps", [Filter("session_key", "=", 1)]) == []


def test_get_404_com_corpo_nao_json_lanca_erro(make_client):
    client, _ = make_client(lambda _r: httpx.Response(404, text="<html>"))

    with pytest.raises(OpenF1Error, match="HTTP 404"):
        client.get("laps")


def test_get_resposta_que_nao_e_lista_lanca_erro(make_client):
    client, _ = make_client(lambda _r: _json(200, {"detail": "x"}))

    with pytest.raises(OpenF1Error, match="esperado lista"):
        client.get("laps")


def test_get_resposta_nao_json_lanca_erro(make_client):
    client, _ = make_client(lambda _r: httpx.Response(200, text="not json"))

    with pytest.raises(OpenF1Error, match="JSON válido"):
        client.get("laps")


def test_get_repete_em_falha_de_rede(make_client):
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        if len(calls) == 1:
            raise httpx.ConnectError("boom", request=request)
        return _json(200, [])

    client, sleeps = make_client(handler)

    assert client.get("laps") == []
    assert sleeps == [1.0]


def test_get_falha_de_rede_persistente_lanca_erro(make_client):
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timeout", request=request)

    client, _ = make_client(handler, max_retries=1)

    with pytest.raises(OpenF1Error, match="Falha de rede"):
        client.get("laps")


def test_get_pausa_entre_requisicoes(make_client):
    client, sleeps = make_client(lambda _r: _json(200, []), request_interval=60.0)

    client.get("laps")
    client.get("laps")

    assert len(sleeps) == 1
    assert 0 < sleeps[0] <= 60.0


def test_context_manager_fecha_cliente_proprio():
    with OpenF1Client() as client:
        http = client._client

    assert http.is_closed


def test_cliente_injetado_nao_e_fechado():
    http = httpx.Client(transport=httpx.MockTransport(lambda _r: _json(200, [])))
    with OpenF1Client(client=http):
        pass

    assert not http.is_closed
    http.close()
