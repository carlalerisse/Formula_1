"""Configurações e constantes do pipeline."""

import os
from collections.abc import Mapping
from pathlib import Path

BASE_URL: str = "https://api.openf1.org/v1"
"""URL base da API REST da OpenF1."""

MIN_YEAR: int = 2023
"""Primeiro ano com dados históricos gratuitos na OpenF1."""

DEFAULT_TIMEOUT: float = 30.0
"""Timeout, em segundos, de cada requisição HTTP."""

DEFAULT_MAX_RETRIES: int = 5
"""Quantidade máxima de novas tentativas em erros 429, 5xx ou falhas de rede."""

DEFAULT_BACKOFF_FACTOR: float = 1.0
"""Base, em segundos, do backoff exponencial (1, 2, 4, 8...)."""

MAX_RETRY_AFTER: float = 60.0
"""Teto, em segundos, para o header ``Retry-After`` devolvido pela API."""

DEFAULT_REQUEST_INTERVAL: float = 0.5
"""Pausa mínima, em segundos, entre duas requisições (a API não publica limites)."""

DATA_DIR_ENV_VAR: str = "F1_DATA_DIR"
"""Variável de ambiente que define o diretório de dados."""

DEFAULT_DATA_DIR: Path = Path("data")
"""Diretório de dados usado quando ``F1_DATA_DIR`` não está definida."""


def get_data_dir(env: Mapping[str, str] | None = None) -> Path:
    """Retorna o diretório raiz onde os dados extraídos são gravados.

    Args:
        env: Mapeamento de variáveis de ambiente. Usa ``os.environ`` se omitido.

    Returns:
        O valor de ``F1_DATA_DIR`` ou ``./data`` quando a variável está vazia
        ou ausente.
    """
    source = os.environ if env is None else env
    value = source.get(DATA_DIR_ENV_VAR, "").strip()
    return Path(value) if value else DEFAULT_DATA_DIR
