from abc import ABC, abstractmethod


class RateLimiterPort(ABC):
    """Port du module ratelimit vers une limite de débit anti-abus (G1,
    backlog.md ; agents.md §4).

    Contrairement à `CachePort`/`GenerateurIAPort` (définis dans les termes
    du domaine `analyse` qui les consomme), ce port n'a pas de domaine
    métier propriétaire : le rate limiting est une préoccupation
    transverse consommée par un middleware (G2, par IP ; G3, par
    `user_id`), pas par un cas d'usage métier. Le port et son adaptateur
    vivent donc tous les deux dans `modules/ratelimit/` (arborescence
    posée par A4), sans dépendre d'aucun autre module.

    Générique dans les termes de l'algorithme (token bucket), pas dans ceux
    de l'appelant : `cle` identifie le seau (ex. `"ip:1.2.3.4"`,
    `"user:<uuid>"`), `capacite`/`taux_recharge_par_seconde` portent la
    politique de quota. Ni l'un ni l'autre n'est fixé par ce port — c'est
    au middleware (G2/G3) de décider quelle clé et quelle politique
    appliquer à quelle route, pas à l'implémentation du seau (Single
    Responsibility, agents.md §1).
    """

    @abstractmethod
    async def consommer(self, cle: str, capacite: int, taux_recharge_par_seconde: float) -> bool:
        """Tente de consommer un jeton du seau identifié par `cle`.

        `capacite` est la taille maximale du seau (le burst autorisé) ;
        `taux_recharge_par_seconde` est le débit de recharge soutenu. Deux
        appels avec la même `cle` mais des `capacite`/`taux_recharge_par_
        seconde` différents partagent quand même le même état persisté —
        c'est à l'appelant de garder une politique cohérente pour une
        `cle` donnée (G2/G3 n'appliquent chacun qu'une seule politique par
        type de clé).

        Retourne `True` si un jeton a été consommé (requête autorisée),
        `False` si le seau était vide (l'appelant doit alors répondre
        `429`, jamais ce port — il ignore tout de HTTP, agents.md §4).
        """
        ...
