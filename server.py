from __future__ import annotations

import argparse
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path

from backend.api import AppContext, AppHandler

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_PORT = 1111


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Lokálny server pre Poznámkovník.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--data-dir", type=Path, default=BASE_DIR / "data")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    context = AppContext(BASE_DIR, args.data_dir.resolve())
    server = ThreadingHTTPServer((args.host, args.port), partial(AppHandler, context=context))
    print(f"Poznámkovník beží na http://{args.host}:{args.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
