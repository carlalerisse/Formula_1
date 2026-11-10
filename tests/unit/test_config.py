from pathlib import Path

import pytest

from formula1.config import DEFAULT_DATA_DIR, get_data_dir


@pytest.mark.parametrize("env", [{}, {"F1_DATA_DIR": ""}, {"F1_DATA_DIR": "   "}])
def test_get_data_dir_padrao(env):
    assert get_data_dir(env) == DEFAULT_DATA_DIR == Path("data")


def test_get_data_dir_usa_variavel_de_ambiente():
    assert get_data_dir({"F1_DATA_DIR": "dados/f1"}) == Path("dados/f1")


def test_get_data_dir_le_os_environ(monkeypatch):
    monkeypatch.setenv("F1_DATA_DIR", "dados")

    assert get_data_dir() == Path("dados")
