from __future__ import annotations

from fastapi_post_office.backends.base import EmailBackend


class ProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, type[EmailBackend]] = {}

    def register(
        self, name: str, backend_cls: type[EmailBackend], *, override: bool = False
    ) -> None:
        key = name.strip().lower()
        if not key:
            raise ValueError("Provider name must not be empty")
        if key in self._providers and not override:
            raise ValueError(f"Provider '{key}' already registered")
        self._providers[key] = backend_cls

    def unregister(self, name: str) -> None:
        key = name.strip().lower()
        self._providers.pop(key, None)

    def create(self, name: str) -> EmailBackend:
        key = name.strip().lower()
        backend_cls = self._providers.get(key)
        if backend_cls is None:
            raise ValueError(f"Unsupported backend: {key}")
        return backend_cls()

    def names(self) -> list[str]:
        return sorted(self._providers.keys())


registry = ProviderRegistry()


def register_provider(
    name: str, backend_cls: type[EmailBackend], *, override: bool = False
) -> None:
    registry.register(name, backend_cls, override=override)


def unregister_provider(name: str) -> None:
    registry.unregister(name)
