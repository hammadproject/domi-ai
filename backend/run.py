"""Dev/prod entrypoint: `python run.py`.

psycopg's async mode cannot run on Windows' default ProactorEventLoop, so we
serve uvicorn on a SelectorEventLoop. On Linux (Render) this is the default anyway.
"""

import asyncio
import os
import selectors

import uvicorn


def main() -> None:
    config = uvicorn.Config(
        "app.main:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8000")),
        log_config=None,  # use our JSON logging (set up in app.main) for everything
        access_log=False,  # RequestContextMiddleware writes the access-log line
    )
    server = uvicorn.Server(config)
    asyncio.run(
        server.serve(),
        loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector()),
    )


if __name__ == "__main__":
    main()
