import hashlib

from modules.analyse.index import GenerateurIAPort, SourceAnalyse


class GenerateurIAFactice(GenerateurIAPort):
    """Implémentation factice de `GenerateurIAPort` (D1, backlog.md).

    Fournie dès D1 pour permettre de tester la logique de concurrence
    (D3) et le test de concurrence lui-même (D6 : « un seul appel à
    `GenerateurIAPort` déclenché ») sans dépendre d'un vrai fournisseur LLM
    (EPIC E). Vit dans `modules/ia/adaptateurs/` — pas dans `tests/` —
    car D3 la câble directement au point de composition comme adaptateur
    provisoire, à la place de l'adaptateur réel (E1).

    Déterministe (même texte + même source -> même sortie) : un hash du
    texte source tient lieu de résultat, pour prouver que deux appels avec
    un texte identique produiraient le même résultat sans jamais faire
    d'appel réseau ni utiliser d'aléa. Remplacer cet adaptateur par le vrai
    (E1) ne doit toucher aucune ligne du use-case D3 — c'est le test
    concret du §4 d'agents.md.

    Les compteurs `appels_texte`/`appels_image` sont l'assertion centrale
    de D6 : deux requêtes concurrentes sur le même texte ne doivent
    déclencher qu'un seul appel réel.
    """

    def __init__(self) -> None:
        self.appels_texte = 0
        self.appels_image = 0

    async def generer_texte(self, texte_source: str, source: SourceAnalyse) -> str:
        self.appels_texte += 1
        empreinte = hashlib.sha256(f"{source.value}:{texte_source}".encode()).hexdigest()[:12]
        return f"[analyse factice #{empreinte}] {texte_source.strip()}"

    async def generer_image(self, texte_resultat: str) -> bytes:
        self.appels_image += 1
        empreinte = hashlib.sha256(texte_resultat.encode()).hexdigest()[:12]
        return f"image-factice-{empreinte}".encode()
