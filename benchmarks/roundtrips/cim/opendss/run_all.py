from __future__ import annotations

from pathlib import Path

from ieee13_cdpsm_roundtrip import run_fixture


def main() -> None:
    root = Path(__file__).resolve().parent
    fixtures = [
        root / "simple_source_load.xml",
        root / "simple_source_load_shunt.xml",
        root / "ieee13cdpsm.xml",
    ]

    for fixture in fixtures:
        run_fixture(fixture)


if __name__ == "__main__":
    main()
