"""Leitura dos Parquet gravados pelo pipeline, para o dashboard.

As sessões disponíveis são descobertas pelas pastas de partição
(``processed/<endpoint>/year=Y/meeting_key=M/session_key=S``). Os catálogos
``meetings`` e ``sessions`` são usados só para dar nomes legíveis, então o
dashboard funciona mesmo quando eles não foram extraídos.
"""

import re
from collections.abc import Iterable, Sequence
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

from formula1.adapters.storage import PROCESSED_DIR, PartitionKeys, Storage
from formula1.domain.endpoints import CATALOG_ENDPOINTS

SESSION_COLUMNS: tuple[str, ...] = (
    "meeting_key",
    "session_key",
    "meeting_name",
    "session_name",
    "session_type",
    "date_start",
    "label",
)
"""Colunas devolvidas por ``available_sessions``."""

_PARTITION = re.compile(r"^(year|meeting_key|session_key)=(\d+)$")


def _partition_value(path: Path, name: str) -> int | None:
    match = _PARTITION.match(path.name)
    if match and match.group(1) == name:
        return int(match.group(2))
    return None


def _children(path: Path, name: str) -> list[tuple[int, Path]]:
    if not path.is_dir():
        return []
    found = [(_partition_value(child, name), child) for child in path.iterdir()]
    return sorted((value, child) for value, child in found if value is not None)


def available_years(data_dir: Path) -> list[int]:
    """Lista as temporadas que têm algum Parquet gravado.

    Args:
        data_dir: Diretório raiz dos dados (``F1_DATA_DIR``).

    Returns:
        Os anos em ordem decrescente.
    """
    processed = data_dir / PROCESSED_DIR
    if not processed.is_dir():
        return []
    years = {
        year
        for endpoint in processed.iterdir()
        for year, _ in _children(endpoint, "year")
    }
    return sorted(years, reverse=True)


def read_partition(
    data_dir: Path,
    endpoint: str,
    keys: PartitionKeys,
    columns: Sequence[str] | None = None,
) -> pd.DataFrame:
    """Lê o Parquet de uma partição e recoloca as colunas de partição.

    Args:
        data_dir: Diretório raiz dos dados.
        endpoint: Nome do endpoint.
        keys: Chaves da partição.
        columns: Colunas a ler; as que não existirem no arquivo são ignoradas.
            ``None`` lê todas.

    Returns:
        Os dados da partição, ou um DataFrame vazio se ela não existir.
    """
    path = Storage(data_dir).parquet_path(endpoint, keys)
    if not path.is_file():
        return pd.DataFrame()
    if columns is not None:
        present = set(pq.read_schema(path).names)
        columns = [c for c in columns if c in present]
    frame = pd.read_parquet(path, columns=columns)
    for name, value in keys.items():
        frame[name] = pd.Series([value] * len(frame), index=frame.index, dtype="Int64")
    return frame


def was_extracted(data_dir: Path, endpoint: str, keys: PartitionKeys) -> bool:
    """Indica se a partição já foi extraída, mesmo que a API não tenha devolvido dados.

    Args:
        data_dir: Diretório raiz dos dados.
        endpoint: Nome do endpoint.
        keys: Chaves da partição.

    Returns:
        ``True`` se o JSON bruto da partição existir.
    """
    return Storage(data_dir).exists(endpoint, keys)


def _session_partitions(data_dir: Path, year: int) -> set[tuple[int, int]]:
    processed = data_dir / PROCESSED_DIR
    if not processed.is_dir():
        return set()
    pairs: set[tuple[int, int]] = set()
    for endpoint in processed.iterdir():
        if endpoint.name in CATALOG_ENDPOINTS:
            continue
        year_dir = endpoint / f"year={year}"
        for meeting_key, meeting_dir in _children(year_dir, "meeting_key"):
            pairs.update(
                (meeting_key, session_key)
                for session_key, _ in _children(meeting_dir, "session_key")
            )
    return pairs


def session_partitions(
    data_dir: Path, endpoint: str, years: Iterable[int]
) -> list[PartitionKeys]:
    """Lista as partições de sessão gravadas para um endpoint.

    Args:
        data_dir: Diretório raiz dos dados.
        endpoint: Nome do endpoint (ex.: ``laps``).
        years: Temporadas a considerar.

    Returns:
        As chaves ``(ano, meeting, sessão)`` em ordem crescente.
    """
    endpoint_dir = data_dir / PROCESSED_DIR / endpoint
    return [
        PartitionKeys(year, meeting_key, session_key)
        for year in sorted(set(years))
        for meeting_key, meeting_dir in _children(
            endpoint_dir / f"year={year}", "meeting_key"
        )
        for session_key, _ in _children(meeting_dir, "session_key")
    ]


def read_sessions(
    data_dir: Path,
    endpoint: str,
    years: Iterable[int],
    columns: Sequence[str] | None = None,
) -> pd.DataFrame:
    """Lê e concatena as partições de sessão de um endpoint em várias temporadas.

    A leitura é feita partição a partição (e não varrendo o dataset inteiro),
    para evitar conflitos de schema entre temporadas.

    Args:
        data_dir: Diretório raiz dos dados.
        endpoint: Nome do endpoint (ex.: ``laps``).
        years: Temporadas a ler.
        columns: Colunas a ler (além das de partição). ``None`` lê todas.

    Returns:
        Todas as linhas, com ``year``, ``meeting_key`` e ``session_key``; vazio
        se nada foi extraído.
    """
    frames = [
        read_partition(data_dir, endpoint, keys, columns)
        for keys in session_partitions(data_dir, endpoint, years)
    ]
    frames = [frame for frame in frames if not frame.empty]
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def read_catalogs(
    data_dir: Path, years: Iterable[int]
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Lê os catálogos ``sessions`` e ``meetings`` de várias temporadas.

    Args:
        data_dir: Diretório raiz dos dados.
        years: Temporadas a ler.

    Returns:
        ``(sessions, meetings)``; cada um fica vazio quando não foi extraído.
    """
    sessions: list[pd.DataFrame] = []
    meetings: list[pd.DataFrame] = []
    for year in sorted(set(years)):
        sessions.append(_sessions_catalog(data_dir, year))
        meetings.append(read_partition(data_dir, "meetings", PartitionKeys(year)))
    return _concat(sessions), _concat(meetings)


def _concat(frames: list[pd.DataFrame]) -> pd.DataFrame:
    frames = [frame for frame in frames if not frame.empty]
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def _sessions_catalog(data_dir: Path, year: int) -> pd.DataFrame:
    year_dir = data_dir / PROCESSED_DIR / "sessions" / f"year={year}"
    frames = [
        read_partition(data_dir, "sessions", PartitionKeys(year, meeting_key))
        for meeting_key, _ in _children(year_dir, "meeting_key")
    ]
    frames = [frame for frame in frames if not frame.empty]
    if not frames:
        return pd.DataFrame(columns=["meeting_key", "session_key"])
    return pd.concat(frames, ignore_index=True)


def available_sessions(data_dir: Path, year: int) -> pd.DataFrame:
    """Lista as sessões de uma temporada que têm dados extraídos.

    Args:
        data_dir: Diretório raiz dos dados.
        year: Temporada.

    Returns:
        Uma linha por sessão, em ordem cronológica quando os catálogos existem,
        com um ``label`` legível (ex.: ``"Bahrain Grand Prix · Race"``).
    """
    pairs = sorted(_session_partitions(data_dir, year))
    if not pairs:
        return pd.DataFrame(columns=list(SESSION_COLUMNS))
    frame = pd.DataFrame(pairs, columns=["meeting_key", "session_key"])
    sessions = _sessions_catalog(data_dir, year)
    meetings = read_partition(data_dir, "meetings", PartitionKeys(year))
    frame = _merge_names(
        frame,
        sessions,
        ["meeting_key", "session_key"],
        ["session_name", "session_type", "date_start"],
    )
    frame = _merge_names(frame, meetings, ["meeting_key"], ["meeting_name"])
    frame["label"] = [_label(row) for row in frame.to_dict("records")]
    frame = frame.sort_values(
        ["date_start", "meeting_key", "session_key"], na_position="last"
    )
    return frame[list(SESSION_COLUMNS)].reset_index(drop=True)


def _merge_names(
    frame: pd.DataFrame, catalog: pd.DataFrame, keys: list[str], columns: list[str]
) -> pd.DataFrame:
    available = [c for c in columns if c in catalog.columns]
    if catalog.empty or not available:
        return frame.assign(**dict.fromkeys(columns))
    subset = catalog[keys + available].drop_duplicates(keys).copy()
    for key in keys:
        subset[key] = subset[key].astype("int64")
    merged = frame.merge(subset, on=keys, how="left")
    return merged.assign(**{c: None for c in columns if c not in available})


def _label(row: dict[str, object]) -> str:
    meeting = row.get("meeting_name")
    session = row.get("session_name")
    meeting_text = meeting if _present(meeting) else f"Meeting {row['meeting_key']}"
    session_text = session if _present(session) else f"Sessão {row['session_key']}"
    return f"{meeting_text} · {session_text}"


def _present(value: object) -> bool:
    return value is not None and not pd.isna(value) and str(value) != ""
