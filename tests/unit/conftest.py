from __future__ import annotations

import sys
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from qat_agent_helpers import apps
from tests.unit.fake_qat import FakeApp, FakeQat


@pytest.fixture
def executable(tmp_path: Path) -> Path:
    """A file for qat_agent_helpers.launch() to accept; the fake Qat never runs it."""
    path = tmp_path / ("demo.exe" if sys.platform == "win32" else "demo")
    path.write_bytes(b"")
    return path


@pytest.fixture
def use_fake(monkeypatch: pytest.MonkeyPatch) -> Iterator[Callable[..., FakeQat]]:
    """Make the library reach a fake Qat that hands out the given apps to launch() and attach()."""

    def use(*fake_apps: FakeApp, **options: str) -> FakeQat:
        fake = FakeQat(*fake_apps, **options)
        monkeypatch.setattr(apps, "_adapter", fake)
        return fake

    yield use
    apps.close_all()
