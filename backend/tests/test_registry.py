import pytest

from jobfinder import adapters  # noqa: F401  (populates the registry)
from jobfinder.adapters import registry
from jobfinder.adapters.base import Adapter


def test_available_includes_the_shipped_adapters():
    names = registry.available()
    for expected in ["greenhouse", "lever", "ashby", "smartrecruiters", "workable", "simplify_listings", "bamboohr"]:
        assert expected in names


def test_unknown_adapter_raises_clear_error():
    with pytest.raises(KeyError, match="no adapter registered"):
        registry.get("not-a-real-adapter")


def test_adding_a_new_adapter_only_needs_registration():
    @registry.register
    class DummyAdapter(Adapter):
        name = "dummy-for-test"

        def fetch(self, board):
            return []

    assert registry.get("dummy-for-test") is DummyAdapter
    assert "dummy-for-test" in registry.available()
