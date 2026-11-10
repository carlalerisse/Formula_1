"""Testes do script ``dashboard.py`` (raiz do projeto) com ``AppTest``."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from formula1.dashboard import fastest_laps

SCRIPT = str(Path(__file__).parents[3] / "dashboard.py")
TIMEOUT = 60


@pytest.fixture
def run_script(monkeypatch):
    def run(data_dir: Path) -> AppTest:
        monkeypatch.setenv("F1_DATA_DIR", str(data_dir))
        app = AppTest.from_file(SCRIPT, default_timeout=TIMEOUT)
        app.run()
        return app

    yield run
    fastest_laps.load_inputs.clear()


def test_dashboard_sem_dados_mostra_como_extrair(run_script, tmp_path):
    app = run_script(tmp_path)

    assert not app.exception
    assert app.title[0].value == "🏁 Fórmula 1 · As 5 voltas mais rápidas"
    assert "--endpoints meetings,sessions,drivers,laps" in app.warning[0].value


def test_dashboard_mostra_top_5(run_script, data_dir):
    app = run_script(data_dir)

    assert not app.exception
    assert app.selectbox[0].value == "Sakhir"
    detail = app.dataframe[0].value
    assert detail["rank"].tolist() == [1, 2, 3, 4, 5]
    assert detail["time"].iloc[0] == "1:35.100"
