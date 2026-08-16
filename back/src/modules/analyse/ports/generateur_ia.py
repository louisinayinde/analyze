from abc import ABC, abstractmethod

from modules.analyse.domaine.analyse import SourceAnalyse


class GenerateurIAPort(ABC):
    """Port du domaine Analyse vers la génération IA (D1, agents.md §4).

    Défini dans les termes du métier (générer un texte d'analyse, générer
    une image à partir de ce texte), pas dans ceux d'un fournisseur LLM
    précis — aucune mention de Claude, OpenAI ou d'un SDK ici.
    L'adaptateur réel (E1 pour le texte, E2 pour l'image, décision de
    fournisseur ouverte en backlog.md) implémente ce contrat ; le câblage
    port -> adaptateur se fait au point de composition, jamais dans le
    domaine ou l'use-case (D3).

    En attendant E1/E2, `GenerateurIAFactice`
    (modules/ia/adaptateurs/generateur_ia_factice.py, fourni dès ce ticket)
    permet de tester la logique de concurrence (D3, D6) sans dépendre de
    l'EPIC E.

    Méthodes asynchrones car tout appel réel est un appel réseau vers un
    fournisseur externe (agents.md §3 : timeout/retry explicites, ajoutés
    en E3, ne doivent jamais bloquer la boucle d'événements).
    """

    @abstractmethod
    async def generer_texte(self, texte_source: str, source: SourceAnalyse) -> str:
        """Produit le texte d'analyse à partir du texte source de l'user."""
        ...

    @abstractmethod
    async def generer_image(self, texte_resultat: str) -> bytes:
        """Produit le contenu binaire de l'image partageable associée.

        Le résultat est destiné à être persisté via `StockageImagePort`,
        jamais directement par cet appel : la génération et le stockage
        sont deux préoccupations séparées (agents.md §4 — un port, une
        responsabilité).
        """
        ...
