"""Create empty tables. Sample rows are added by seed.py, not by this script."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database.session import init_db  # noqa: E402


if __name__ == "__main__":
    init_db()
    print("Database tables are ready.")
