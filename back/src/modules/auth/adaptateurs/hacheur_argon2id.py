from argon2 import PasswordHasher
from argon2.exceptions import InvalidHash, VerificationError, VerifyMismatchError

from modules.auth.ports.hacheur_mot_de_passe import HacheurMotDePassePort


class HacheurArgon2id(HacheurMotDePassePort):
    """Adaptateur Argon2id du port `HacheurMotDePassePort` (C3, agents.md §7).

    Via `argon2-cffi` (bindings vers l'implémentation de référence en C,
    lauréate de la Password Hashing Competition) — pas d'algorithme maison.
    `PasswordHasher()` sans argument choisit Argon2id par défaut avec des
    paramètres alignés sur les recommandations OWASP courantes ; on ne les
    ajuste que si une mesure de charge réelle le justifie (agents.md §8 :
    pas d'optimisation sans donnée).
    """

    def __init__(self) -> None:
        self._hasher = PasswordHasher()

    def hacher(self, mot_de_passe: str) -> str:
        return self._hasher.hash(mot_de_passe)

    def verifier(self, mot_de_passe: str, hash_mot_de_passe: str) -> bool:
        try:
            self._hasher.verify(hash_mot_de_passe, mot_de_passe)
        except (VerifyMismatchError, VerificationError, InvalidHash):
            return False
        return True
