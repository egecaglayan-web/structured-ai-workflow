"""Exercise the real ASGI routes offline using synthetic input and a temporary journal."""
import logging
from tempfile import TemporaryDirectory
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from .config import Settings
from .main import create_app


def main():
    with TemporaryDirectory() as directory:
        settings = Settings(database_path=Path(directory) / "demo.sqlite3")
        with TestClient(create_app(settings)) as client:
            payload = {"request_id": str(uuid4()), "text": "My password reset link is broken. How can I login?", "use_references": True}
            response = client.post("/api/process", json=payload)
            response.raise_for_status()
            replay = client.post("/api/process", json=payload)
            assert replay.json() == response.json()
            assert response.json()["mode"] == "demo"
            assert response.json()["citations"]
            logging.getLogger(__name__).info("event=demo_result result=%s", response.json())
            print(response.json())


if __name__ == "__main__":
    main()
