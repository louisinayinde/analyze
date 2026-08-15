from shared.errors import EntreeInvalide

# NIST SP 800-63B recommande de privilégier la longueur à des règles de
# composition forcées (majuscule/chiffre/symbole obligatoires), qui poussent
# surtout les users vers des motifs prévisibles (« Password1! »). On borne
# aussi une longueur max : au-delà, on ne gagne plus rien en robustesse et on
# ne fait qu'augmenter inutilement le coût CPU du hachage Argon2id
# (agents.md §2 — chaque calcul a un coût).
LONGUEUR_MIN = 10
LONGUEUR_MAX = 128

# Liste courte de mots de passe extrêmement courants (classements
# NordPass/SplashData récurrents d'une année sur l'autre) : pas une
# protection exhaustive de type « liste de mots de passe compromis », juste
# un filet contre les choix les plus triviaux, sans dépendance externe ni
# appel réseau pour ce ticket (agents.md §2 — pas de dépendance pour ce
# qu'on peut écrire nous-mêmes).
_MOTS_DE_PASSE_COURANTS = frozenset(
    {
        "password",
        "password1",
        "123456",
        "123456789",
        "12345678",
        "qwerty",
        "qwerty123",
        "azerty",
        "azerty123",
        "motdepasse",
        "admin123",
        "letmein",
        "welcome",
        "welcome1",
        "iloveyou",
        "monkey123",
        "football",
        "starwars",
        "dragon123",
        "sunshine",
        "princess",
        "abc123",
    }
)


def valider_robustesse(mot_de_passe: str, email: str) -> None:
    """Rejette les mots de passe manifestement faibles (C3, agents.md §7).

    Logique pure, zéro dépendance technique (agents.md §4) : uniquement des
    opérations sur des chaînes. Lève `EntreeInvalide` (422) au premier
    critère non respecté.
    """
    if not (LONGUEUR_MIN <= len(mot_de_passe) <= LONGUEUR_MAX):
        raise EntreeInvalide(
            f"Le mot de passe doit contenir entre {LONGUEUR_MIN} et {LONGUEUR_MAX} caractères."
        )

    if mot_de_passe.isdigit():
        raise EntreeInvalide("Le mot de passe ne peut pas être uniquement composé de chiffres.")

    mot_de_passe_normalise = mot_de_passe.casefold()

    if mot_de_passe_normalise in _MOTS_DE_PASSE_COURANTS:
        raise EntreeInvalide("Ce mot de passe est trop courant, choisissez-en un autre.")

    partie_locale = email.split("@", 1)[0].casefold()
    if mot_de_passe_normalise in (email.casefold(), partie_locale):
        raise EntreeInvalide("Le mot de passe ne peut pas être basé sur votre adresse email.")
