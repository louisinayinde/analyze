from modules.analyse.ports.stockage_image import StockageImagePort


class StockageImageFactice(StockageImagePort):
    """Implémentation factice de `StockageImagePort` (D4, backlog.md).

    Câblée au point de composition en attendant l'adaptateur réel (E5 :
    filesystem local en dev, GCS en prod) — même rôle vis-à-vis de D4 que
    `GenerateurIAFactice` (D1) vis-à-vis de D3/D6 : débloquer l'endpoint
    `POST /analyses` de bout en bout sans dépendre d'un ticket ultérieur.
    En mémoire du seul processus API, jamais persisté sur disque : les
    images « stockées » ne survivent pas à un redémarrage, sans conséquence
    tant qu'E5 n'est pas branché (agents.md §4 — remplacer cet adaptateur
    par le vrai ne touche aucune ligne du use-case D3).
    """

    def __init__(self) -> None:
        self.contenus: dict[str, bytes] = {}

    async def stocker(self, contenu: bytes, cle: str) -> str:
        self.contenus[cle] = contenu
        return f"memoire://{cle}"
