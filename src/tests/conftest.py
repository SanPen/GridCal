from pathlib import Path

import pytest

ROOT_PATH = Path(__file__).parent


@pytest.fixture
def root_path():
    return ROOT_PATH
