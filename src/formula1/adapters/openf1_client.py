"""Cliente HTTP da API OpenF1: filtros com operadores, retry e pausa entre chamadas."""

import logging
import re
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from http import HTTPStatus
from types import TracebackType
from typing import Any, Self
from urllib.parse import quote

import httpx

from formula1 import config

logger = logging.getLogger(__name__)

OPERATORS: frozenset[str] = frozenset({"=", ">", ">=", "<", "<="})
"""Operadores de comparação aceitos pela OpenF1."""

FilterValue = str | int | float | bool
"""Tipos aceitos como valor de filtro."""

_NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_NO_RESULTS_MARKER = "no results"


class OpenF1Error(Exception):
    """Erro ao consultar a OpenF1 (HTTP 4xx/5xx, rede ou resposta inesperada).

    Attributes:
        status_code: Código HTTP da resposta, quando houver.
    """

    def __init__(self, message: str, status_code: int | None = None) -> None:
        """Cria o erro.

        Args:
            message: Descrição do problema.
            status_code: Código HTTP da resposta, quando houver.
        """
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class Filter:
    """Filtro da query string da OpenF1.

    Attributes:
        field: Nome do atributo filtrado (ex.: ``session_key``).
        op: Operador: ``=``, ``>``, ``>=``, ``<`` ou ``<=``.
        value: Valor, ou lista/tupla de valores (a chave é repetida na query).
    """

    field: str
    op: str
    value: FilterValue | list[FilterValue] | tuple[FilterValue, ...]

    def __post_init__(self) -> None:
        """Valida o campo, o operador e o valor.

        Raises:
            ValueError: Se o operador, o campo ou a lista de valores for inválido.
        """
        if self.op not in OPERATORS:
            valid = ", ".join(sorted(OPERATORS))
            msg = f"Operador inválido: {self.op!r}. Válidos: {valid}"
            raise ValueError(msg)
        if not _NAME_PATTERN.match(self.field):
            msg = f"Campo de filtro inválido: {self.field!r}"
            raise ValueError(msg)
        if isinstance(self.value, list | tuple) and not self.value:
            msg = f"O filtro {self.field!r} precisa de ao menos um valor"
            raise ValueError(msg)

    def to_query(self) -> str:
        """Gera o trecho da query string deste filtro.

        Returns:
            Trechos ``campo<op>valor`` unidos por ``&``, com os valores codificados
            (espaços viram ``%20``).
        """
        values = self.value if isinstance(self.value, list | tuple) else [self.value]
        return "&".join(f"{self.field}{self.op}{_encode(v)}" for v in values)


def _encode(value: FilterValue) -> str:
    text = str(value).lower() if isinstance(value, bool) else str(value)
    return quote(text, safe="")


def build_query(filters: Iterable[Filter]) -> str:
    """Monta a query string a partir de uma sequência de filtros.

    Args:
        filters: Filtros a aplicar.

    Returns:
        A query string sem o ``?`` inicial (vazia se não houver filtros).
    """
    return "&".join(item.to_query() for item in filters)


@dataclass(frozen=True)
class ClientSettings:
    """Parâmetros de rede do cliente.

    Attributes:
        base_url: URL base da API.
        timeout: Timeout de cada requisição, em segundos.
        max_retries: Novas tentativas em 429, 5xx e falhas de rede.
        backoff_factor: Base do backoff exponencial, em segundos.
        request_interval: Pausa mínima entre requisições, em segundos.
    """

    base_url: str = config.BASE_URL
    timeout: float = config.DEFAULT_TIMEOUT
    max_retries: int = config.DEFAULT_MAX_RETRIES
    backoff_factor: float = config.DEFAULT_BACKOFF_FACTOR
    request_interval: float = config.DEFAULT_REQUEST_INTERVAL


class OpenF1Client:
    """Cliente síncrono da API REST da OpenF1 (dados históricos, sem autenticação).

    Example:
        ```python
        with OpenF1Client() as client:
            laps = client.get("laps", [Filter("session_key", "=", 9161)])
        ```
    """

    def __init__(
        self,
        settings: ClientSettings | None = None,
        client: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        """Cria o cliente.

        Args:
            settings: Parâmetros de rede. Usa os padrões de ``config`` se omitido.
            client: Cliente ``httpx`` injetado (útil nos testes com
                ``httpx.MockTransport``). Se omitido, um cliente próprio é criado.
            sleep: Função de espera, substituível nos testes.
        """
        self._settings = settings or ClientSettings()
        self._owns_client = client is None
        self._client = client or httpx.Client()
        self._sleep = sleep
        self._last_request: float | None = None

    def __enter__(self) -> Self:
        """Entra no contexto do cliente."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Fecha o cliente ao sair do contexto."""
        self.close()

    def close(self) -> None:
        """Fecha o cliente HTTP, se ele tiver sido criado por esta classe."""
        if self._owns_client:
            self._client.close()

    def build_url(self, endpoint: str, filters: Iterable[Filter] = ()) -> str:
        """Monta a URL completa de uma consulta.

        Args:
            endpoint: Nome do endpoint (ex.: ``laps``).
            filters: Filtros da query string.

        Returns:
            A URL com a query string montada manualmente (aceita ``>=``, ``<`` etc.).

        Raises:
            ValueError: Se o nome do endpoint for inválido.
        """
        if not _NAME_PATTERN.match(endpoint):
            msg = f"Endpoint inválido: {endpoint!r}"
            raise ValueError(msg)
        base = f"{self._settings.base_url.rstrip('/')}/{endpoint}"
        query = build_query(filters)
        return f"{base}?{query}" if query else base

    def get(
        self, endpoint: str, filters: Iterable[Filter] = ()
    ) -> list[dict[str, Any]]:
        """Consulta um endpoint e devolve a lista de registros.

        Args:
            endpoint: Nome do endpoint (ex.: ``laps``).
            filters: Filtros da query string.

        Returns:
            Os registros devolvidos. Uma resposta "No results found" vira lista vazia.

        Raises:
            OpenF1Error: Em erro HTTP não recuperável, falha de rede persistente ou
                resposta que não seja uma lista JSON.
            ValueError: Se o nome do endpoint for inválido.
        """
        url = self.build_url(endpoint, filters)
        response = self._request_with_retry(url)
        return self._parse(response, url)

    def _throttle(self) -> None:
        if self._last_request is not None:
            elapsed = time.monotonic() - self._last_request
            wait = self._settings.request_interval - elapsed
            if wait > 0:
                self._sleep(wait)
        self._last_request = time.monotonic()

    def _backoff(self, attempt: int) -> float:
        return float(self._settings.backoff_factor * 2 ** (attempt - 1))

    def _retry_delay(self, response: httpx.Response, attempt: int) -> float:
        header = response.headers.get("Retry-After", "")
        try:
            return min(float(header), config.MAX_RETRY_AFTER)
        except ValueError:
            return self._backoff(attempt)

    def _request_with_retry(self, url: str) -> httpx.Response:
        attempts = self._settings.max_retries + 1
        attempt = 0
        while True:
            attempt += 1
            self._throttle()
            logger.debug("GET %s (tentativa %d/%d)", url, attempt, attempts)
            try:
                response = self._client.get(url, timeout=self._settings.timeout)
            except httpx.TransportError as exc:
                if attempt >= attempts:
                    msg = f"Falha de rede ao acessar {url}: {exc}"
                    raise OpenF1Error(msg) from exc
                delay = self._backoff(attempt)
                logger.warning(
                    "Falha de rede em %s; nova tentativa em %.1fs", url, delay
                )
            else:
                if not _is_retryable(response.status_code) or attempt >= attempts:
                    return response
                delay = self._retry_delay(response, attempt)
                logger.warning(
                    "HTTP %d em %s; nova tentativa em %.1fs",
                    response.status_code,
                    url,
                    delay,
                )
            self._sleep(delay)

    @staticmethod
    def _parse(response: httpx.Response, url: str) -> list[dict[str, Any]]:
        status = response.status_code
        if status == HTTPStatus.NOT_FOUND and _is_no_results(response):
            return []
        if status >= HTTPStatus.BAD_REQUEST:
            msg = f"HTTP {status} em {url}: {response.text[:200]}"
            raise OpenF1Error(msg, status_code=status)
        try:
            payload = response.json()
        except ValueError as exc:
            msg = f"Resposta não é JSON válido em {url}"
            raise OpenF1Error(msg, status_code=status) from exc
        if not isinstance(payload, list):
            msg = f"Resposta inesperada em {url}: esperado lista JSON"
            raise OpenF1Error(msg, status_code=status)
        return payload


def _is_retryable(status: int) -> bool:
    return (
        status == HTTPStatus.TOO_MANY_REQUESTS
        or status >= HTTPStatus.INTERNAL_SERVER_ERROR
    )


def _is_no_results(response: httpx.Response) -> bool:
    try:
        payload = response.json()
    except ValueError:
        return False
    detail = payload.get("detail", "") if isinstance(payload, dict) else ""
    return isinstance(detail, str) and _NO_RESULTS_MARKER in detail.lower()
