from abc import ABC, abstractmethod

from modules.analyse.domaine.analyse import SourceAnalyse


class GenerateurIAPort(ABC):
    """Port du domaine Analyse vers la génération IA (D1, agents.md §4).

    Défini dans les termes du métier (générer un texte d'analyse, générer
    une image à partir de ce texte), pas dans ceux d'un fournisseur LLM
    précis — aucune mention de Claude, OpenAI ou d'un SDK ici.
    L'adaptateur réel implémente ce contrat ; le câblage port -> adaptateur
    se fait au point de composition, jamais dans le domaine ou l'use-case
    (D3). `AdaptateurClaude` (E1, modules/ia/adaptateurs/adaptateur_claude.py)
    couvre `generer_texte` avec le fournisseur retenu (Claude). Sa
    `generer_image` lève volontairement `NotImplementedError` : la stratégie
    d'image (LLM multimodal vs template) est une décision encore ouverte,
    propre à E2 — tant qu'E2 n'est pas fait, le point de composition
    continue de câbler `GenerateurIAFactice` pour ce port.

    En attendant, `GenerateurIAFactice`
    (modules/ia/adaptateurs/generateur_ia_factice.py, fourni dès D1)
    permet de tester la logique de concurrence (D3, D6) sans dépendre d'un
    vrai fournisseur.

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
