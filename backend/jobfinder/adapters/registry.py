from __future__ import annotations

from jobfinder.adapters.base import Adapter

_REGISTRY: dict[str, type[Adapter]] = {}


def register(cls: type[Adapter]) -> type[Adapter]:
    _REGISTRY[cls.name] = cls
    return cls


def get(name: str) -> type[Adapter]:
    if name not in _REGISTRY:
        raise KeyError(f"no adapter registered for {name!r}; have {available()}")
    return _REGISTRY[name]


def available() -> list[str]:
    return sorted(_REGISTRY)
