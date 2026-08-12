from typing import TypeVar, cast

T = TypeVar("T")


class Registry:
    """Associe un port (interface métier) à son adaptateur concret.

    Alternative volontairement minimale à un framework DI : le câblage
    reste explicite, lisible, et centralisé au point de composition
    (agents.md §2 budget, §4 ports & adaptateurs).
    """

    def __init__(self) -> None:
        self._instances: dict[type, object] = {}

    def register(self, port: type[T], instance: T) -> None:
        self._instances[port] = instance

    def resolve(self, port: type[T]) -> T:
        try:
            return cast(T, self._instances[port])
        except KeyError:
            raise LookupError(f"Aucune implémentation enregistrée pour {port!r}.") from None
