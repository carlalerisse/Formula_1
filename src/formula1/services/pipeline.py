"""Orquestração do ETL: ano → meetings → sessions → endpoints.

Para cada sessão e endpoint, o pipeline extrai os registros da OpenF1, grava o
JSON bruto, normaliza e grava o Parquet. Falhas de uma sessão são registradas e
não interrompem o restante do lote.
"""

import logging
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

from formula1.adapters.openf1_client import Filter, OpenF1Error
from formula1.adapters.storage import PartitionKeys, Storage
from formula1.domain.endpoints import (
    CATALOG_ENDPOINTS,
    DEFAULT_ENDPOINTS,
    EndpointSpec,
    get_endpoint,
    is_race,
)
from formula1.domain.transform import to_dataframe

logger = logging.getLogger(__name__)

RECOVERABLE_ERRORS: tuple[type[Exception], ...] = (
    OpenF1Error,
    OSError,
    ValueError,
    TypeError,
    KeyError,
)
"""Erros que invalidam só a partição atual e não o lote inteiro."""


class OpenF1Source(Protocol):
    """Contrato mínimo da fonte de dados (implementado por ``OpenF1Client``)."""

    def get(
        self, endpoint: str, filters: Iterable[Filter] = ()
    ) -> list[dict[str, Any]]:
        """Consulta um endpoint e devolve a lista de registros."""
        ...


@dataclass(frozen=True)
class Failure:
    """Falha registrada durante a execução.

    Attributes:
        endpoint: Endpoint que falhou.
        meeting_key: Fim de semana, quando conhecido.
        session_key: Sessão, quando conhecida.
        error: Mensagem do erro.
    """

    endpoint: str
    meeting_key: int | None
    session_key: int | None
    error: str


@dataclass
class PipelineReport:
    """Resultado de uma execução do pipeline.

    Attributes:
        year: Temporada processada.
        records: Registros extraídos por endpoint.
        partitions: Partições gravadas por endpoint.
        skipped: Partições puladas por endpoint (já extraídas ou fora de corrida).
        failures: Falhas registradas.
    """

    year: int
    records: Counter[str] = field(default_factory=Counter)
    partitions: Counter[str] = field(default_factory=Counter)
    skipped: Counter[str] = field(default_factory=Counter)
    failures: list[Failure] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """``True`` se não houve falhas."""
        return not self.failures

    def summary(self) -> str:
        """Resumo legível da execução, uma linha por endpoint."""
        endpoints = sorted({*self.records, *self.partitions, *self.skipped})
        lines = [f"Resumo da extração de {self.year}:"]
        lines.extend(
            f"  {name}: {self.records[name]} registros, "
            f"{self.partitions[name]} partições gravadas, {self.skipped[name]} puladas"
            for name in endpoints
        )
        lines.append(f"  falhas: {len(self.failures)}")
        lines.extend(
            f"    - {item.endpoint} meeting={item.meeting_key} "
            f"session={item.session_key}: {item.error}"
            for item in self.failures
        )
        return "\n".join(lines)


@dataclass(frozen=True)
class _RunOptions:
    year: int
    endpoints: tuple[str, ...]
    session_types: frozenset[str] | None
    force: bool

    @property
    def session_endpoints(self) -> list[EndpointSpec]:
        return [
            get_endpoint(name)
            for name in self.endpoints
            if name not in CATALOG_ENDPOINTS
        ]


class ExtractionPipeline:
    """Executa o ETL de uma temporada."""

    def __init__(self, client: OpenF1Source, storage: Storage) -> None:
        """Cria o pipeline.

        Args:
            client: Fonte de dados (normalmente um ``OpenF1Client``).
            storage: Destino dos arquivos.
        """
        self._client = client
        self._storage = storage

    def run(
        self,
        year: int,
        *,
        endpoints: Sequence[str] = DEFAULT_ENDPOINTS,
        session_types: Sequence[str] | None = None,
        force: bool = False,
    ) -> PipelineReport:
        """Extrai, transforma e grava os dados de uma temporada.

        Os catálogos (``meetings`` e ``sessions``) são sempre consultados, porque
        guiam a iteração, e são regravados a cada execução. Os demais endpoints
        são idempotentes: partições já extraídas são puladas, a menos que
        ``force`` seja ``True``.

        Args:
            year: Temporada (2023 em diante).
            endpoints: Endpoints a extrair.
            session_types: Filtra sessões por ``session_type`` ou ``session_name``
                (sem diferenciar maiúsculas). ``None`` processa todas.
            force: Reextrai partições que já existem.

        Returns:
            O relatório com contagens e falhas.

        Raises:
            ValueError: Se algum endpoint não for suportado.
        """
        for name in endpoints:
            get_endpoint(name)
        options = _RunOptions(
            year=year,
            endpoints=tuple(endpoints),
            session_types=(
                frozenset(item.lower() for item in session_types)
                if session_types
                else None
            ),
            force=force,
        )
        report = PipelineReport(year=year)
        try:
            meetings = self._client.get("meetings", [Filter("year", "=", year)])
        except OpenF1Error as exc:
            logger.error("Falha ao listar os meetings de %d: %s", year, exc)
            report.failures.append(Failure("meetings", None, None, str(exc)))
            return report
        if "meetings" in options.endpoints:
            self._save(report, "meetings", PartitionKeys(year), meetings)
        for meeting in meetings:
            if meeting.get("is_cancelled"):
                logger.info("Meeting %s cancelado; pulando", meeting.get("meeting_key"))
                continue
            self._process_meeting(meeting, options, report)
        logger.info(report.summary())
        return report

    def _process_meeting(
        self, meeting: dict[str, Any], options: _RunOptions, report: PipelineReport
    ) -> None:
        meeting_key = int(meeting["meeting_key"])
        try:
            sessions = self._client.get(
                "sessions", [Filter("meeting_key", "=", meeting_key)]
            )
        except OpenF1Error as exc:
            logger.error(
                "Falha ao listar as sessões do meeting %d: %s", meeting_key, exc
            )
            report.failures.append(Failure("sessions", meeting_key, None, str(exc)))
            return
        if "sessions" in options.endpoints:
            self._save(
                report, "sessions", PartitionKeys(options.year, meeting_key), sessions
            )
        for session in sessions:
            if session.get("is_cancelled") or not _matches(
                session, options.session_types
            ):
                continue
            self._process_session(meeting_key, session, options, report)

    def _process_session(
        self,
        meeting_key: int,
        session: dict[str, Any],
        options: _RunOptions,
        report: PipelineReport,
    ) -> None:
        session_key = int(session["session_key"])
        keys = PartitionKeys(options.year, meeting_key, session_key)
        for spec in options.session_endpoints:
            if spec.race_only and not is_race(session.get("session_type")):
                report.skipped[spec.name] += 1
                continue
            if not options.force and self._storage.exists(spec.name, keys):
                logger.info(
                    "%s da sessão %d já extraído; pulando", spec.name, session_key
                )
                report.skipped[spec.name] += 1
                continue
            logger.info("Extraindo %s da sessão %d", spec.name, session_key)
            try:
                records = self._fetch(spec, session_key)
                self._write(spec.name, keys, records)
            except RECOVERABLE_ERRORS as exc:
                logger.exception("Falha em %s da sessão %d", spec.name, session_key)
                report.failures.append(
                    Failure(spec.name, meeting_key, session_key, str(exc))
                )
                continue
            report.records[spec.name] += len(records)
            report.partitions[spec.name] += 1

    def _fetch(self, spec: EndpointSpec, session_key: int) -> list[dict[str, Any]]:
        base = [Filter("session_key", "=", session_key)]
        if not spec.per_driver:
            return self._client.get(spec.name, base)
        drivers = self._client.get("drivers", base)
        numbers = sorted(
            {
                int(d["driver_number"])
                for d in drivers
                if d.get("driver_number") is not None
            }
        )
        records: list[dict[str, Any]] = []
        for number in numbers:
            records.extend(
                self._client.get(
                    spec.name, [*base, Filter("driver_number", "=", number)]
                )
            )
        return records

    def _write(
        self, endpoint: str, keys: PartitionKeys, records: list[dict[str, Any]]
    ) -> None:
        frame = to_dataframe(records, endpoint)
        if not frame.empty:
            self._storage.save_parquet(endpoint, keys, frame)
        self._storage.save_raw(endpoint, keys, records)

    def _save(
        self,
        report: PipelineReport,
        endpoint: str,
        keys: PartitionKeys,
        records: list[dict[str, Any]],
    ) -> None:
        try:
            self._write(endpoint, keys, records)
        except RECOVERABLE_ERRORS as exc:
            logger.exception("Falha ao gravar %s", endpoint)
            report.failures.append(
                Failure(endpoint, keys.meeting_key, keys.session_key, str(exc))
            )
            return
        report.records[endpoint] += len(records)
        report.partitions[endpoint] += 1


def _matches(session: dict[str, Any], session_types: frozenset[str] | None) -> bool:
    if session_types is None:
        return True
    candidates = {
        str(session.get("session_type", "")).lower(),
        str(session.get("session_name", "")).lower(),
    }
    return bool(candidates & session_types)
