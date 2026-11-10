"""Testes contra a API real. Rodar com: ``poetry run pytest -m integration``."""

import pytest

from formula1.adapters.openf1_client import Filter, OpenF1Client
from formula1.domain.transform import to_dataframe

pytestmark = pytest.mark.integration


def test_sessions_de_corrida_2023():
    with OpenF1Client() as client:
        records = client.get(
            "sessions", [Filter("year", "=", 2023), Filter("session_name", "=", "Race")]
        )

    frame = to_dataframe(records, "sessions")

    assert len(frame) >= 20
    assert set(frame["session_type"]) == {"Race"}
    assert set(frame["year"]) == {2023}
    assert str(frame["date_start"].dt.tz) == "UTC"
