from abc import ABC, abstractmethod


class StockageImagePort(ABC):
    """Port du domaine Analyse vers le stockage des images générées (D1,
    agents.md §4).

    Défini dans les termes du métier (stocker un contenu, obtenir son URL
    publique), sans mention de filesystem ou de GCS. Deux implémentations
    réelles (E5, backlog.md) : `StockageImageFilesystem` (dev, écrit sur un
    volume Docker et sert les fichiers via `StaticFiles`) et
    `StockageImageGCS` (prod, activée seulement après L4 — provisionnement
    du bucket). Le câblage port -> adaptateur se fait selon l'environnement
    au point de composition (`composition/app.py`, `GCS_BUCKET_IMAGES` de
    `shared/config.py` comme bascule), jamais dans le domaine ou
    l'use-case (D3, agents.md §4).
    """

    @abstractmethod
    async def stocker(self, contenu: bytes, cle: str) -> str:
        """Persiste `contenu` sous la clé `cle` et retourne son URL publique.

        L'URL retournée est celle destinée à `Analyse.resultat_image_url`.
        `cle` identifie l'image de façon stable (ex. dérivée de
        l'`input_hash` du cache) pour rester déterministe d'un appel à
        l'autre sur le même contenu.
        """
        ...
