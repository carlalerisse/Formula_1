"""Armazenamento local: JSON bruto e Parquet particionado no estilo Hive.

Layout:

```text
<data_dir>/raw/<endpoint>/year=Y/meeting_key=M/session_key=S.json
<data_dir>/processed/<endpoint>/year=Y/meeting_key=M/session_key=S/part.parquet
```

As colunas usadas como partição são removidas do Parquet, porque o leitor
(``pd.read_parquet`` / ``pyarrow.dataset``) as reconstrói a partir do caminho.
"""

import json
import os
import tempfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from formula1.domain.endpoints import INT_LIST_COLUMNS

RAW_DIR: str = "raw"
PROCESSED_DIR: str = "processed"
PARQUET_FILE: str = "part.parquet"


@dataclass(frozen=True)
class PartitionKeys:
    """Chaves de partição de um lote de dados.

    Attributes:
        year: Temporada.
        meeting_key: Fim de semana (omitido no catálogo ``meetings``).
        session_key: Sessão (omitida nos catálogos ``meetings`` e ``sessions``).
    """

    year: int
    meeting_key: int | None = None
    session_key: int | None = None

    def __post_init__(self) -> None:
        """Valida a hierarquia das chaves.

        Raises:
            ValueError: Se ``session_key`` for informado sem ``meeting_key``.
        """
        if self.session_key is not None and self.meeting_key is None:
            msg = "session_key exige meeting_key"
            raise ValueError(msg)

    def items(self) -> list[tuple[str, int]]:
        """Retorna os pares ``(nome, valor)`` preenchidos, do geral ao específico."""
        pairs = [
            ("year", self.year),
            ("meeting_key", self.meeting_key),
            ("session_key", self.session_key),
        ]
        return [(name, value) for name, value in pairs if value is not None]

    def parts(self) -> list[str]:
        """Retorna os segmentos de caminho ``nome=valor``."""
        return [f"{name}={value}" for name, value in self.items()]


class Storage:
    """Grava e consulta os dados extraídos em disco."""

    def __init__(self, base_dir: Path | str) -> None:
        """Cria o armazenamento.

        Args:
            base_dir: Diretório raiz dos dados (``F1_DATA_DIR``).
        """
        self.base_dir = Path(base_dir)

    def raw_path(self, endpoint: str, keys: PartitionKeys) -> Path:
        """Caminho do JSON bruto de uma partição."""
        *dirs, leaf = keys.parts()
        return self.base_dir.joinpath(RAW_DIR, endpoint, *dirs, f"{leaf}.json")

    def parquet_path(self, endpoint: str, keys: PartitionKeys) -> Path:
        """Caminho do Parquet de uma partição."""
        return self.base_dir.joinpath(
            PROCESSED_DIR, endpoint, *keys.parts(), PARQUET_FILE
        )

    def exists(self, endpoint: str, keys: PartitionKeys) -> bool:
        """Indica se a partição já foi extraída.

        O JSON bruto é gravado mesmo quando a API não devolve registros, por isso
        é ele que marca a partição como concluída.

        Args:
            endpoint: Nome do endpoint.
            keys: Chaves da partição.

        Returns:
            ``True`` se o JSON bruto da partição existir.
        """
        return self.raw_path(endpoint, keys).is_file()

    def save_raw(
        self, endpoint: str, keys: PartitionKeys, records: Sequence[dict[str, Any]]
    ) -> Path:
        """Grava os registros brutos em JSON (de forma atômica).

        Args:
            endpoint: Nome do endpoint.
            keys: Chaves da partição.
            records: Registros devolvidos pela API.

        Returns:
            O caminho do arquivo gravado.
        """
        path = self.raw_path(endpoint, keys)
        content = json.dumps(list(records), ensure_ascii=False)
        _atomic_write(path, lambda tmp: tmp.write_text(content, encoding="utf-8"))
        return path

    def load_raw(self, endpoint: str, keys: PartitionKeys) -> list[dict[str, Any]]:
        """Lê os registros brutos de uma partição.

        Raises:
            FileNotFoundError: Se a partição não existir.
        """
        text = self.raw_path(endpoint, keys).read_text(encoding="utf-8")
        return json.loads(text)

    def save_parquet(
        self, endpoint: str, keys: PartitionKeys, frame: pd.DataFrame
    ) -> Path:
        """Grava um DataFrame em Parquet (de forma atômica).

        As colunas de partição são removidas e as colunas de listas de inteiros
        são fixadas como ``list<int64>``, para manter o schema estável entre
        partições.

        Args:
            endpoint: Nome do endpoint.
            keys: Chaves da partição.
            frame: Dados normalizados.

        Returns:
            O caminho do arquivo gravado.
        """
        partition_columns = [name for name, _ in keys.items() if name in frame.columns]
        table = pa.Table.from_pandas(
            frame.drop(columns=partition_columns), preserve_index=False
        )
        table = _fix_list_columns(table)
        path = self.parquet_path(endpoint, keys)
        _atomic_write(path, lambda tmp: pq.write_table(table, tmp))
        return path


def _fix_list_columns(table: pa.Table) -> pa.Table:
    list_type = pa.list_(pa.int64())
    for index, field in enumerate(table.schema):
        if field.name in INT_LIST_COLUMNS and field.type != list_type:
            column = table.column(index).cast(list_type)
            table = table.set_column(index, pa.field(field.name, list_type), column)
    return table


def _atomic_write(path: Path, writer: Callable[[Path], object]) -> None:
    """Escreve em um arquivo temporário e o move para o destino."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
    )
    os.close(fd)
    tmp = Path(tmp_name)
    try:
        writer(tmp)
        tmp.replace(path)
    finally:
        tmp.unlink(missing_ok=True)
