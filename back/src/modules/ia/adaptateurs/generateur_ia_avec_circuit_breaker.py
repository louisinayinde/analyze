from modules.analyse.domaine.analyse import SourceAnalyse
from modules.analyse.ports.generateur_ia import GenerateurIAPort
from modules.ia.adaptateurs.circuit_breaker import CircuitBreaker


class GenerateurIAAvecCircuitBreaker(GenerateurIAPort):
    """Décore un `GenerateurIAPort` avec un circuit breaker sur son appel
    réseau réel (E4, backlog.md).

    Décorateur, pas une modification d'`AdaptateurClaude` : la logique de
    circuit breaker est réutilisable pour n'importe quelle implémentation
    du port, et l'ajouter (ou le retirer) ne touche aucune ligne de
    l'adaptateur décoré ni du use-case `GenererAnalyse` — remplaçable et
    supprimable sans casser le reste (agents.md §4).

    Ne protège que `generer_texte` : c'est le seul appel réseau vers le
    fournisseur LLM. `generer_image` (côté `AdaptateurClaude`) délègue à
    `rendu_image_template`, un rendu local sans I/O réseau (E2) — un échec
    de rendu (ex. police manquante) n'a rien à voir avec un incident
    fournisseur et ne doit ni ouvrir le circuit, ni être bloqué par lui
    quand le circuit est déjà ouvert.

    Câblé au point de composition (composition/app.py) autour de
    `AdaptateurClaude`, uniquement quand une clé API est configurée :
    `GenerateurIAFactice` ne fait aucun appel réseau et n'a donc rien à
    protéger.
    """

    def __init__(
        self, delegue: GenerateurIAPort, disjoncteur: CircuitBreaker | None = None
    ) -> None:
        self._delegue = delegue
        self._disjoncteur = disjoncteur or CircuitBreaker()

    async def generer_texte(self, texte_source: str, source: SourceAnalyse) -> str:
        return await self._disjoncteur.appeler(
            lambda: self._delegue.generer_texte(texte_source, source)
        )

    async def generer_image(self, texte_resultat: str) -> bytes:
        return await self._delegue.generer_image(texte_resultat)
