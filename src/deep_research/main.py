"""Entry point for the deep research service."""

import os

import uvicorn
from dotenv import load_dotenv

load_dotenv()


def main() -> None:
    port = int(os.environ.get("APP_PORT", "8000"))
    uvicorn.run(
        "deep_research.api.app:app",
        host="0.0.0.0",
        port=port,
        reload=True,
    )


if __name__ == "__main__":
    main()
