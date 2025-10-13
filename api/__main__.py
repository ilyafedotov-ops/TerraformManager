from __future__ import annotations

import os
import uvicorn


def main() -> None:
    host = os.getenv("HOST", "0.0.0.0")
    # Prefer TFM_PORT, then PORT; default to non-standard 8890
    port = int(os.getenv("TFM_PORT") or os.getenv("PORT") or "8890")
    reload = os.getenv("RELOAD", "1") not in {"0", "false", "no", "off"}
    uvicorn.run("api.main:app", host=host, port=port, reload=reload)


if __name__ == "__main__":
    main()
