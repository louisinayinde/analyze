from abc import ABC, abstractmethod


class HacheurMotDePassePort(ABC):
    """Port du domaine Auth vers le hachage de mot de passe (agents.md §4, §7).

    Défini dans les termes du métier (hacher, vérifier), pas dans ceux de la
    techno : aucune mention d'Argon2 ici. L'algorithme concret est un détail
    d'implémentation de l'adaptateur (`HacheurArgon2id`, C3), remplaçable
    sans toucher au domaine ni aux use-cases (C3, C4) si le standard
    recommandé change un jour.

    Méthodes synchrones et volontairement pas async : contrairement à
    `DépôtUtilisateurPort`, il n'y a ici aucune I/O réseau, seulement du
    calcul CPU. C'est à l'appelant (le use-case, qui tourne dans une route
    async) de décider comment l'exécuter sans bloquer la boucle d'événements
    — cf. `InscrireUtilisateur` (agents.md §8).
    """

    @abstractmethod
    def hacher(self, mot_de_passe: str) -> str:
        """Retourne le hash du mot de passe en clair, prêt à être persisté."""
        ...

    @abstractmethod
    def verifier(self, mot_de_passe: str, hash_mot_de_passe: str) -> bool:
        """Retourne `True` si `mot_de_passe` correspond à `hash_mot_de_passe`."""
        ...
