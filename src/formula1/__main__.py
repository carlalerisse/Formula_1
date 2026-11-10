"""Interface de linha de comando: ``formula1 extract --year 2024 ...``."""

import argparse
import logging
from collections.abc import Sequence
from pathlib import Path

from formula1 import config
from formula1.adapters.openf1_client import ClientSettings, OpenF1Client
from formula1.adapters.storage import Storage
from formula1.domain.endpoints import DEFAULT_ENDPOINTS, ENDPOINTS, parse_endpoints
from formula1.services.pipeline import ExtractionPipeline

LOG_LEVELS: tuple[str, ...] = ("DEBUG", "INFO", "WARNING", "ERROR")


def _year(value: str) -> int:
    try:
        year = int(value)
    except ValueError:
        msg = f"ano inválido: {value!r}"
        raise argparse.ArgumentTypeError(msg) from None
    if year < config.MIN_YEAR:
        msg = f"a OpenF1 só tem dados a partir de {config.MIN_YEAR} (recebido {year})"
        raise argparse.ArgumentTypeError(msg)
    return year


def _endpoints(value: str) -> tuple[str, ...]:
    try:
        return parse_endpoints(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from None


def _non_negative(value: str) -> float:
    try:
        number = float(value)
    except ValueError:
        msg = f"número inválido: {value!r}"
        raise argparse.ArgumentTypeError(msg) from None
    if number < 0:
        msg = f"o valor não pode ser negativo: {number}"
        raise argparse.ArgumentTypeError(msg)
    return number


def split_session_types(values: Sequence[str] | None) -> list[str] | None:
    """Junta os valores de ``--session-type`` (repetidos ou separados por vírgula).

    Args:
        values: Valores recebidos pela CLI.

    Returns:
        A lista de tipos ou ``None`` se nenhum tipo foi informado.
    """
    if not values:
        return None
    items = [part.strip() for value in values for part in value.split(",")]
    return [item for item in items if item] or None


def build_parser() -> argparse.ArgumentParser:
    """Cria o parser de argumentos da CLI.

    Returns:
        O parser com o subcomando ``extract``.
    """
    parser = argparse.ArgumentParser(
        prog="formula1",
        description="ETL de dados históricos da Fórmula 1 (API OpenF1).",
    )
    parser.add_argument(
        "--log-level", default="INFO", choices=LOG_LEVELS, help="nível de log"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    extract = commands.add_parser(
        "extract", help="extrai uma temporada para JSON bruto e Parquet"
    )
    extract.add_argument(
        "--year", type=_year, required=True, help="temporada (>= 2023)"
    )
    extract.add_argument(
        "--endpoints",
        type=_endpoints,
        default=DEFAULT_ENDPOINTS,
        help=(
            "lista separada por vírgulas. Padrão: "
            f"{','.join(DEFAULT_ENDPOINTS)}. Disponíveis: {','.join(sorted(ENDPOINTS))}"
        ),
    )
    extract.add_argument(
        "--session-type",
        dest="session_types",
        action="append",
        help="filtra por session_type ou session_name (ex.: Race). Pode repetir.",
    )
    extract.add_argument(
        "--force", action="store_true", help="reextrai partições já existentes"
    )
    extract.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help=f"diretório de dados (padrão: ${config.DATA_DIR_ENV_VAR} ou ./data)",
    )
    extract.add_argument(
        "--request-interval",
        type=_non_negative,
        default=config.DEFAULT_REQUEST_INTERVAL,
        help="pausa mínima entre requisições, em segundos",
    )
    return parser


def run_extract(args: argparse.Namespace) -> int:
    """Executa o subcomando ``extract``.

    Args:
        args: Argumentos já validados pelo parser.

    Returns:
        ``0`` se não houve falhas; ``1`` caso contrário.
    """
    data_dir = args.data_dir or config.get_data_dir()
    settings = ClientSettings(request_interval=args.request_interval)
    with OpenF1Client(settings) as client:
        pipeline = ExtractionPipeline(client, Storage(data_dir))
        report = pipeline.run(
            args.year,
            endpoints=args.endpoints,
            session_types=split_session_types(args.session_types),
            force=args.force,
        )
    return 0 if report.ok else 1


def main(argv: Sequence[str] | None = None) -> int:
    """Ponto de entrada da CLI.

    Args:
        argv: Argumentos (sem o nome do programa). Usa ``sys.argv`` se omitido.

    Returns:
        O código de saída do processo.
    """
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    return run_extract(args)


if __name__ == "__main__":
    raise SystemExit(main())
