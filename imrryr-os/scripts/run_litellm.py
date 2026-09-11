#!/usr/bin/env python3
"""Runner protegido de LiteLLM para Windows."""
import os
import sys

os.environ["PYTHONIOENCODING"] = "utf-8"
os.environ["PYTHONUTF8"] = "1"

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from pathlib import Path
from dotenv import load_dotenv

_env_file = Path(__file__).resolve().parent.parent / "config" / ".env"
if _env_file.exists():
    load_dotenv(_env_file, override=True)

from litellm import run_server

if __name__ == "__main__":
    run_server()
