import asyncio
import os
import sys

import uvicorn


def _env_flag(name: str, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


if __name__ == "__main__":
    is_windows = sys.platform.startswith("win")

    uvicorn_kwargs = {
        "host": os.getenv("BACKEND_HOST", "0.0.0.0"),
        "port": int(os.getenv("BACKEND_PORT", "8000")),
        "reload": _env_flag("UVICORN_RELOAD", not is_windows),
    }

    if is_windows:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        uvicorn_kwargs["loop"] = (
            "backend.app.agent.utils.async_utils:uvicorn_windows_safe_loop"
        )

    uvicorn.run(
        "backend.app.main:app",
        **uvicorn_kwargs,
    )
