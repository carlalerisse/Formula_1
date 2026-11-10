from pathlib import Path

import pytest

from formula1 import __main__ as cli
from formula1.domain.endpoints import DEFAULT_ENDPOINTS
from formula1.services.pipeline import Failure, PipelineReport


def test_parser_extract_valores_padrao():
    args = cli.build_parser().parse_args(["extract", "--year", "2024"])

    assert args.command == "extract"
    assert args.year == 2024
    assert args.endpoints == DEFAULT_ENDPOINTS
    assert args.session_types is None
    assert args.force is False
    assert args.data_dir is None


def test_parser_extract_todas_as_opcoes():
    args = cli.build_parser().parse_args(
        [
            "--log-level",
            "DEBUG",
            "extract",
            "--year",
            "2023",
            "--endpoints",
            "laps,stints",
            "--session-type",
            "Race",
            "--session-type",
            "Sprint,Qualifying",
            "--force",
            "--data-dir",
            "out",
            "--request-interval",
            "2",
        ]
    )

    assert args.log_level == "DEBUG"
    assert args.endpoints == ("laps", "stints")
    assert cli.split_session_types(args.session_types) == [
        "Race",
        "Sprint",
        "Qualifying",
    ]
    assert args.force is True
    assert args.data_dir == Path("out")
    assert args.request_interval == 2.0


@pytest.mark.parametrize(
    ("argv", "message"),
    [
        (["extract", "--year", "2022"], "a partir de 2023"),
        (["extract", "--year", "abc"], "ano inválido"),
        (["extract", "--year", "2024", "--endpoints", "lapz"], "Endpoint desconhecido"),
        (["extract", "--year", "2024", "--request-interval", "-1"], "negativo"),
        (["extract", "--year", "2024", "--request-interval", "x"], "número inválido"),
        (["extract"], "--year"),
        ([], "command"),
    ],
)
def test_parser_argumentos_invalidos(capsys, argv, message):
    with pytest.raises(SystemExit) as info:
        cli.build_parser().parse_args(argv)

    assert info.value.code == 2
    assert message in capsys.readouterr().err


@pytest.mark.parametrize(
    ("values", "expected"),
    [
        (None, None),
        ([], None),
        ([" , "], None),
        (["Race, Sprint "], ["Race", "Sprint"]),
    ],
)
def test_split_session_types(values, expected):
    assert cli.split_session_types(values) == expected


class _FakePipeline:
    instances: tuple["_FakePipeline", ...] = ()

    def __init__(self, client, storage, failures=()):
        self.client = client
        self.storage = storage
        self.kwargs: dict = {}
        self.failures = list(failures)
        _FakePipeline.instances = (*_FakePipeline.instances, self)

    def run(self, year, **kwargs):
        self.kwargs = {"year": year, **kwargs}
        return PipelineReport(year=year, failures=self.failures)


@pytest.fixture
def fake_pipeline(monkeypatch):
    _FakePipeline.instances = ()
    monkeypatch.setattr(cli, "ExtractionPipeline", _FakePipeline)
    return _FakePipeline


def test_main_executa_pipeline_com_argumentos(fake_pipeline, tmp_path, monkeypatch):
    monkeypatch.setenv("F1_DATA_DIR", str(tmp_path))

    code = cli.main(["extract", "--year", "2023", "--session-type", "Race", "--force"])

    assert code == 0
    pipeline = fake_pipeline.instances[0]
    assert pipeline.storage.base_dir == tmp_path
    assert pipeline.kwargs == {
        "year": 2023,
        "endpoints": DEFAULT_ENDPOINTS,
        "session_types": ["Race"],
        "force": True,
    }


def test_main_data_dir_tem_prioridade(fake_pipeline, tmp_path, monkeypatch):
    monkeypatch.setenv("F1_DATA_DIR", "ignorado")

    cli.main(["extract", "--year", "2023", "--data-dir", str(tmp_path)])

    assert fake_pipeline.instances[0].storage.base_dir == tmp_path


def test_main_retorna_1_quando_ha_falhas(monkeypatch):
    def factory(client, storage):
        return _FakePipeline(client, storage, failures=[Failure("laps", 1, 2, "x")])

    monkeypatch.setattr(cli, "ExtractionPipeline", factory)

    assert cli.main(["extract", "--year", "2023"]) == 1
