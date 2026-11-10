"""Dashboard Streamlit: as 5 voltas mais rápidas de Fórmula 1 em cada circuito.

Executar com::

    poetry run streamlit run dashboard.py

Os dados vêm da API OpenF1 e precisam ser extraídos antes::

    poetry run formula1 extract --year 2024 --endpoints meetings,sessions,drivers,laps
"""

from pathlib import Path

import streamlit as st

from formula1 import config
from formula1.dashboard import data, fastest_laps


def main() -> None:
    """Renderiza o dashboard das 5 voltas mais rápidas."""
    st.set_page_config(
        page_title="F1 · 5 voltas mais rápidas", page_icon="🏁", layout="wide"
    )
    st.title("🏁 Fórmula 1 · As 5 voltas mais rápidas")
    st.sidebar.header("Filtros")
    data_dir = st.sidebar.text_input(
        "Diretório de dados",
        str(config.get_data_dir()),
        help=f"Padrão: variável {config.DATA_DIR_ENV_VAR} ou ./data",
    )
    years = data.available_years(Path(data_dir))
    if not years:
        st.warning(
            f"Nenhum dado encontrado em `{data_dir}`. Extraia uma temporada da "
            f"OpenF1 primeiro:\n\n{fastest_laps.EXTRACT_HINT}"
        )
        return
    fastest_laps.render(data_dir, years)


main()
