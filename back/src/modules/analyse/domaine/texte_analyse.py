import re

from shared.errors import EntreeInvalide

# projets.md / backlog.md (D7) : borne le coût d'un appel LLM (proportionnel
# à la longueur du texte envoyé) et le volume qu'un abus pourrait faire
# persister/hasher inutilement (agents.md §2).
TEXTE_LONGUEUR_MAX = 5000

# Caractères de contrôle sans usage légitime dans un texte à analyser. On
# garde \t, \n et \r (un texte collé depuis un profil peut légitimement
# contenir des sauts de ligne) ; le reste (octet nul, escapes ANSI, DEL...)
# n'a aucune raison d'être là et peut perturber l'affichage ou un futur
# parsing en aval.
_CARACTERES_CONTROLE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

# Motifs "grossiers" de prompt injection (backlog.md D7 : sanitisation
# *basique*, pas une détection exhaustive). On cible uniquement des marqueurs
# structurels que la plupart des formats de chat LLM utilisent pour délimiter
# les tours system/user/assistant — un texte "profil GitHub", "historique
# Spotify" ou "bio" légitime n'a aucune raison d'en contenir. On ne filtre
# volontairement pas sur des phrases en langage naturel ("ignore les
# instructions précédentes") : le taux de faux positifs sur un texte
# légitime serait trop élevé (agents.md §13 — la correction prime, on ne
# corrompt pas un texte licite). La vraie défense contre l'injection reste
# le prompt système d'E1, qui doit traiter ce texte comme une donnée à
# analyser, jamais comme des instructions — ce nettoyage n'est qu'un filet
# supplémentaire (agents.md §3 : défense en profondeur).
_MOTIFS_INJECTION = (
    re.compile(r"<\|.*?\|>"),  # jetons spéciaux type <|system|>, <|im_start|>...
    re.compile(r"\[/?(?:INST|SYS)]", re.IGNORECASE),  # [INST], [/INST], [SYS]...
    re.compile(r"<<\s*/?SYS\s*>>", re.IGNORECASE),  # <<SYS>>, <</SYS>>
    re.compile(r"^\s*(?:system|assistant)\s*:", re.IGNORECASE | re.MULTILINE),
)


def valider_et_nettoyer_texte(texte: str) -> str:
    """Valide et sanitise le texte source d'une analyse (D7, agents.md §7).

    Seule source de vérité pour cette règle métier (agents.md §1 — DRY) :
    appelée depuis le use-case (`GenererAnalyse.executer`, D3), donc
    appliquée à tout appelant futur (un worker asynchrone, F1...), pas
    seulement à `POST /analyses` (D4) — c'est exactement ce que demande le
    ticket D7 (« sanitisation... avant tout envoi futur au LLM »). Même
    posture que `modules.auth.domaine.mot_de_passe.valider_robustesse` :
    logique pure, zéro dépendance technique, lève `EntreeInvalide` (422).

    Lève `EntreeInvalide` si le texte est vide, uniquement composé
    d'espaces, ou dépasse `TEXTE_LONGUEUR_MAX` caractères une fois nettoyé.
    Retourne sinon le texte débarrassé des caractères de contrôle et des
    marqueurs de prompt injection grossiers.
    """
    texte_nettoye = texte.strip()
    texte_nettoye = _CARACTERES_CONTROLE.sub("", texte_nettoye)
    for motif in _MOTIFS_INJECTION:
        texte_nettoye = motif.sub("", texte_nettoye)
    texte_nettoye = texte_nettoye.strip()

    if not texte_nettoye:
        raise EntreeInvalide("Le texte à analyser ne peut pas être vide.")

    if len(texte_nettoye) > TEXTE_LONGUEUR_MAX:
        raise EntreeInvalide(
            f"Le texte à analyser ne peut pas dépasser {TEXTE_LONGUEUR_MAX} caractères."
        )

    return texte_nettoye
