from collections.abc import Iterable

import pytest

from formula1.adapters.openf1_client import Filter, OpenF1Error
from formula1.adapters.storage import PartitionKeys, Storage
from formula1.services.pipeline import ExtractionPipeline


class FakeClient:
    """Fonte falsa: devolve payloads fixos por endpoint e registra as chamadas."""

    def __init__(self, responses: dict[str, list[dict]], failing: Iterable[str] = ()):
        self.responses = responses
        self.failing = set(failing)
        self.calls: list[tuple[str, tuple[str, ...]]] = []

    def get(self, endpoint: str, filters: Iterable[Filter] = ()) -> list[dict]:
        self.calls.append((endpoint, tuple(f.to_query() for f in filters)))
        if endpoint in self.failing:
            msg = f"HTTP 500 em {endpoint}"
            raise OpenF1Error(msg, status_code=500)
        return self.responses.get(endpoint, [])

    def endpoints_called(self) -> list[str]:
        return [endpoint for endpoint, _ in self.calls]


@pytest.fixture
def responses(meetings_payload, sessions_payload, laps_payload, intervals_payload):
    return {
        "meetings": meetings_payload,
        "sessions": sessions_payload,
        "laps": laps_payload,
        "intervals": intervals_payload,
        "stints": [],
        "drivers": [{"driver_number": 1}, {"driver_number": 11}, {"driver_number": 1}],
        "car_data": [{"session_key": 7953, "driver_number": 1, "speed": 300}],
    }


@pytest.fixture
def storage(tmp_path):
    return Storage(tmp_path)


RACE = PartitionKeys(2023, 1140, 7953)
PRACTICE = PartitionKeys(2023, 1140, 7763)


def test_run_extrai_e_grava_sessoes(responses, storage):
    client = FakeClient(responses)

    report = ExtractionPipeline(client, storage).run(
        2023, endpoints=["meetings", "sessions", "laps"]
    )

    assert report.ok
    assert report.records["laps"] == 2 * len(responses["laps"])
    assert report.partitions == {"meetings": 1, "sessions": 1, "laps": 2}
    assert storage.parquet_path("laps", RACE).is_file()
    assert storage.parquet_path("meetings", PartitionKeys(2023)).is_file()
    assert storage.parquet_path("sessions", PartitionKeys(2023, 1140)).is_file()
    assert ("meetings", ("year=2023",)) in client.calls


def test_run_ignora_meetings_cancelados(responses, storage):
    client = FakeClient(responses)

    ExtractionPipeline(client, storage).run(2023, endpoints=["laps"])

    session_calls = [f for e, f in client.calls if e == "sessions"]
    assert session_calls == [("meeting_key=1140",)]


def test_run_pula_endpoint_de_corrida_fora_de_race(responses, storage):
    client = FakeClient(responses)

    report = ExtractionPipeline(client, storage).run(2023, endpoints=["intervals"])

    assert report.partitions["intervals"] == 1
    assert report.skipped["intervals"] == 1
    assert storage.exists("intervals", RACE)
    assert not storage.exists("intervals", PRACTICE)


def test_run_filtra_por_tipo_de_sessao(responses, storage):
    client = FakeClient(responses)

    report = ExtractionPipeline(client, storage).run(
        2023, endpoints=["laps"], session_types=["race"]
    )

    assert report.partitions["laps"] == 1
    assert not storage.exists("laps", PRACTICE)


def test_run_filtra_por_nome_de_sessao(responses, storage):
    client = FakeClient(responses)

    report = ExtractionPipeline(client, storage).run(
        2023, endpoints=["laps"], session_types=["Practice 1"]
    )

    assert report.partitions["laps"] == 1
    assert storage.exists("laps", PRACTICE)


def test_run_idempotente_pula_sessoes_existentes(responses, storage):
    ExtractionPipeline(FakeClient(responses), storage).run(2023, endpoints=["laps"])
    client = FakeClient(responses)

    report = ExtractionPipeline(client, storage).run(2023, endpoints=["laps"])

    assert report.skipped["laps"] == 2
    assert report.partitions["laps"] == 0
    assert "laps" not in client.endpoints_called()


def test_run_force_reextrai(responses, storage):
    ExtractionPipeline(FakeClient(responses), storage).run(2023, endpoints=["laps"])
    client = FakeClient(responses)

    report = ExtractionPipeline(client, storage).run(
        2023, endpoints=["laps"], force=True
    )

    assert report.partitions["laps"] == 2
    assert client.endpoints_called().count("laps") == 2


def test_run_resposta_vazia_grava_so_raw(responses, storage):
    report = ExtractionPipeline(FakeClient(responses), storage).run(
        2023, endpoints=["stints"]
    )

    assert report.partitions["stints"] == 2
    assert report.records["stints"] == 0
    assert storage.exists("stints", RACE)
    assert not storage.parquet_path("stints", RACE).exists()


def test_run_falha_isolada_nao_interrompe_lote(responses, storage):
    client = FakeClient(responses, failing=["laps"])

    report = ExtractionPipeline(client, storage).run(2023, endpoints=["laps", "stints"])

    assert not report.ok
    assert len(report.failures) == 2
    assert report.failures[0].endpoint == "laps"
    assert report.failures[0].session_key in {7763, 7953}
    assert report.partitions["stints"] == 2
    assert not storage.exists("laps", RACE)


def test_run_falha_em_meetings_encerra_com_relatorio(responses, storage):
    report = ExtractionPipeline(
        FakeClient(responses, failing=["meetings"]), storage
    ).run(2023)

    assert not report.ok
    assert report.failures[0].endpoint == "meetings"
    assert report.partitions == {}


def test_run_falha_em_sessions_registra_meeting(responses, storage):
    report = ExtractionPipeline(
        FakeClient(responses, failing=["sessions"]), storage
    ).run(2023, endpoints=["laps"])

    assert [(f.endpoint, f.meeting_key) for f in report.failures] == [
        ("sessions", 1140)
    ]


def test_run_alto_volume_extrai_por_piloto(responses, storage):
    client = FakeClient(responses)

    report = ExtractionPipeline(client, storage).run(
        2023, endpoints=["car_data"], session_types=["Race"]
    )

    car_calls = [f for e, f in client.calls if e == "car_data"]
    assert car_calls == [
        ("session_key=7953", "driver_number=1"),
        ("session_key=7953", "driver_number=11"),
    ]
    assert report.records["car_data"] == 2


def test_run_endpoint_desconhecido_lanca_erro(responses, storage):
    with pytest.raises(ValueError, match="Endpoint desconhecido"):
        ExtractionPipeline(FakeClient(responses), storage).run(2023, endpoints=["x"])


def test_run_falha_ao_gravar_catalogo_e_registrada(responses, storage, monkeypatch):
    def boom(*_args, **_kwargs):
        msg = "disco cheio"
        raise OSError(msg)

    monkeypatch.setattr(storage, "save_raw", boom)

    report = ExtractionPipeline(FakeClient(responses), storage).run(
        2023, endpoints=["meetings"]
    )

    assert [f.endpoint for f in report.failures] == ["meetings"]
    assert "disco cheio" in report.failures[0].error


def test_summary_lista_endpoints_e_falhas(responses, storage):
    report = ExtractionPipeline(FakeClient(responses, failing=["laps"]), storage).run(
        2023, endpoints=["laps", "stints"], session_types=["Race"]
    )

    text = report.summary()

    assert "Resumo da extração de 2023" in text
    assert "stints: 0 registros, 1 partições gravadas, 0 puladas" in text
    assert "falhas: 1" in text
    assert "laps meeting=1140 session=7953" in text
