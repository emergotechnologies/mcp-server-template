"""Command-line entry point: `mcp-server-template [--transport stdio|http]`."""

import argparse
import logging
import signal
import sys
from types import FrameType

import uvicorn
from pydantic import ValidationError

from mcp_server_template.config import Settings

logger = logging.getLogger("mcp_server_template")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="mcp-server-template", description="Run the MCP server.")
    parser.add_argument("--transport", help="stdio or http (overrides MCP_TRANSPORT)")
    args = parser.parse_args(argv)

    try:
        settings = Settings(**({"transport": args.transport} if args.transport else {}))
    except ValidationError as exc:
        sys.stderr.write(f"Invalid configuration:\n{_format_errors(exc)}\n")
        sys.exit(2)

    configure_logging(settings.log_level)
    # Treat SIGTERM like Ctrl+C. Uvicorn shuts down gracefully and then re-raises the signal it caught,
    # which lands here as KeyboardInterrupt, so both transports exit with status 0.
    signal.signal(signal.SIGTERM, _interrupt)
    try:
        if settings.transport == "stdio":
            run_stdio(settings)
        else:
            run_http(settings)
    except KeyboardInterrupt:
        logger.info("Shutting down")


def configure_logging(level: str) -> None:
    # stdout belongs to the stdio transport; everything else goes to stderr.
    logging.basicConfig(level=level, stream=sys.stderr, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def run_stdio(settings: Settings) -> None:
    from mcp_server_template.server import create_server

    create_server(settings).run("stdio")


def run_http(settings: Settings) -> None:
    from mcp_server_template.http_app import build_http_app

    app = build_http_app(settings)
    logger.info("MCP endpoint (local): http://%s:%s%s", settings.host, settings.port, settings.http_path)
    if settings.public_endpoint:
        logger.info("MCP endpoint (public): %s", settings.public_endpoint)
    if settings.auth_mode == "none" and settings.is_publicly_exposed:
        logger.warning("Authentication is DISABLED on a publicly reachable server (MCP_ALLOW_INSECURE=true)")
    uvicorn.run(app, host=settings.host, port=settings.port, log_level=settings.log_level.lower(), log_config=None)


def _interrupt(signum: int, frame: FrameType | None) -> None:
    raise KeyboardInterrupt


def _format_errors(exc: ValidationError) -> str:
    lines = []
    for error in exc.errors():
        field = ".".join(str(part) for part in error["loc"])
        name = f"MCP_{field.upper()}: " if field else ""
        lines.append(f"  - {name}{error['msg'].removeprefix('Value error, ')}")
    return "\n".join(lines)
