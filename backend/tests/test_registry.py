import pytest

# Importing the registry module runs jobfinder/adapters/__init__.py, which registers them all.
from jobfinder.adapters import registry
from jobfinder.adapters.base import Adapter
from jobfinder.config import Board
from jobfinder.models import RawJob


def test_available_includes_the_shipped_adapters() -> None:
    names = registry.available()
    for expected in [
        "greenhouse",
        "lever",
        "ashby",
        "smartrecruiters",
        "workable",
        "simplify_listings",
        "bamboohr",
    ]:
        assert expected in names


def test_unknown_adapter_raises_clear_error() -> None:
    with pytest.raises(KeyError, match="no adapter registered"):
        registry.get("not-a-real-adapter")


def test_adding_a_new_adapter_only_needs_registration() -> None:
    @registry.register
    class DummyAdapter(Adapter):
        name = "dummy-for-test"

        def fetch(self, board: Board) -> list[RawJob]:
            return []

    assert registry.get("dummy-for-test") is DummyAdapter
    assert "dummy-for-test" in registry.available()
