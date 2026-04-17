"""Structured logging to both stdout and a dated file under logs/."""
from __future__ import annotations

import logging
from datetime import date
from pathlib import Path


def configure(repo_root: Path, job_name: str) -> None:
    logs_dir = repo_root / "logs"
    logs_dir.mkdir(exist_ok=True)
    log_file = logs_dir / f"{date.today().isoformat()}-{job_name}.log"

    fmt = "%(asctime)s %(levelname)s %(name)s %(message)s"
    logging.basicConfig(
        level=logging.INFO,
        format=fmt,
        handlers=[
            logging.FileHandler(log_file, mode="a", encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )
