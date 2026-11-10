"""Testes do app Streamlit com ``streamlit.testing.v1.AppTest`` (sem navegador)."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import formula1.dashboard.app as app_module
from formula1.adapters.storage import PartitionKeys, Storage
from formula1.dashboard import fastest_laps
from tests.unit.conftest import MEETING, QUALI

APP_FILE = str(Path(app_module.__file__))
TIMEOUT = 60


@pytest.fixture
def run_app(monkeypatch):
    def run(data_dir: Path, view: str = app_module.SESSION_VIEW) -> AppTest:
        monkeypatch.setenv("F1_DATA_DIR", str(data_dir))
        app = AppTest.from_file(APP_FILE, default_timeout=TIMEOUT)
        app.run()
        if view != app_module.FASTEST_VIEW:
            app.sidebar.radio[0].set_value(view).run()
        return app

    yield run
    app_module.load_years.clear()
    app_module.load_sessions.clear()
    app_module.load_partition.clear()
    fastest_laps.load_inputs.clear()


def test_app_sem_dados_mostra_instrucoes(run_app, tmp_path):
    app = run_app(tmp_path)

    assert not app.exception
    assert app.title[0].value == "Fórmula 1 · Dashboard"
    assert "Nenhum dado encontrado" in app.warning[0].value


def test_app_renderiza_sessao_padrao(run_app, data_dir):
    app = run_app(data_dir)

    assert not app.exception
    assert [s.label for s in app.sidebar.selectbox] == ["Temporada", "Sessão"]
    assert app.sidebar.selectbox[1].value == 0
    assert "Qualifying" in app.caption[0].value


def test_app_corrida_completa(run_app, data_dir):
    app = run_app(data_dir)

    app.sidebar.selectbox[1].select(1).run()

    assert not app.exception
    assert "Race" in app.caption[0].value
    metrics = {m.label: m.value for m in app.metric}
    assert metrics["Vencedor"] == "VER"
    assert metrics["Volta mais rápida"] == "1:35.100"
    assert metrics["Voltas"] == "4"
    assert metrics["Passagens pelo pit"] == "1"
    assert app.sidebar.multiselect[0].value == ["VER", "PER", "ALO"]
    assert len(app.dataframe) == 2
    assert not app.info


def test_app_toggles_e_filtro_de_pilotos(run_app, data_dir):
    app = run_app(data_dir)
    app.sidebar.selectbox[1].select(1).run()

    app.toggle[0].set_value(False).run()
    app.toggle[1].set_value(True).run()
    app.sidebar.multiselect[0].set_value([]).run()

    assert not app.exception
    messages = [info.value for info in app.info]
    assert "Nenhuma volta cronometrada para os pilotos selecionados." in messages
    assert "Nenhum stint para os pilotos selecionados." in messages
    assert "Nenhuma posição para os pilotos selecionados." in messages


def test_app_sessao_incompleta_mostra_como_extrair(run_app, data_dir):
    app = run_app(data_dir)

    messages = " ".join(info.value for info in app.info)

    assert not app.exception
    assert "--endpoints stints" in messages
    assert "--endpoints position" in messages
    assert "--endpoints session_result" in messages
    assert "--endpoints pit" in messages


def test_app_extraido_sem_registros_explica_limitacao_da_api(run_app, data_dir):
    Storage(data_dir).save_raw("stints", PartitionKeys(2023, MEETING, QUALI), [])

    app = run_app(data_dir)

    messages = " ".join(info.value for info in app.info)
    assert "A OpenF1 não tem dados de `stints`" in messages
    assert "--endpoints stints" not in messages
    assert {m.label: m.value for m in app.metric}["Passagens pelo pit"] == "—"


def test_app_ano_sem_sessoes(run_app, data_dir):
    (data_dir / "processed" / "meetings" / "year=2030").mkdir(parents=True)

    app = run_app(data_dir)

    assert app.sidebar.selectbox[0].value == 2030
    assert "Nenhuma sessão com dados em 2030" in app.warning[0].value


def test_app_abre_no_top_5_por_circuito(run_app, data_dir):
    app = run_app(data_dir, view=app_module.FASTEST_VIEW)

    assert not app.exception
    assert app.sidebar.radio[0].value == app_module.FASTEST_VIEW
    assert app.header[0].value == "Top 5 voltas mais rápidas por circuito"
    assert app.selectbox[0].value == "Sakhir"
    metrics = {m.label: m.value for m in app.metric}
    assert metrics["Circuitos"] == "1"
    assert metrics["Mais voltas recorde"] == "VER"
    assert len(app.dataframe) == 2
    detail = app.dataframe[0].value
    assert detail["rank"].tolist() == [1, 2, 3, 4, 5]
    assert detail["time"].iloc[0] == "1:35.100"


def test_app_top_5_filtros(run_app, data_dir):
    app = run_app(data_dir, view=app_module.FASTEST_VIEW)

    assert app.sidebar.multiselect[1].value == ["Qualifying", "Race"]
    app.sidebar.toggle[0].set_value(True).run()

    assert not app.exception
    assert app.dataframe[0].value["label"].tolist() == ["VER", "PER", "ALO"]

    app.sidebar.multiselect[1].set_value([]).run()
    assert "Nenhuma volta cronometrada para os filtros escolhidos." in [
        info.value for info in app.info
    ]

    app.sidebar.multiselect[0].set_value([]).run()
    assert "Selecione ao menos uma temporada" in app.info[0].value


def test_app_top_5_sem_laps_mostra_como_extrair(run_app, data_dir):
    (data_dir / "processed" / "pit" / "year=2030").mkdir(parents=True)
    app = run_app(data_dir, view=app_module.FASTEST_VIEW)

    app.sidebar.multiselect[0].set_value([2030]).run()

    assert not app.exception
    assert "--endpoints meetings,sessions,drivers,laps" in app.info[0].value
