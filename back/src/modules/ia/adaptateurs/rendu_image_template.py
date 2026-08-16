from functools import cache
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# E2 (backlog.md) : décision utilisateur — template + overlay de texte plutôt
# qu'un modèle multimodal. Quasi gratuit (aucun appel réseau, aucun coût par
# génération), déterministe (même texte -> même image, cohérent avec le cache
# exact de D2/D3) et sans dépendance à la disponibilité d'un second
# fournisseur IA (agents.md §2, §3). Extrait de `AdaptateurClaude` (E1) dans
# son propre fichier : le rendu d'image et l'appel au SDK Claude sont deux
# raisons de changer distinctes (agents.md §1, SRP) — ce module est pur
# (aucune I/O réseau) et testable sans mocker `AsyncAnthropic`.

# Police bundlée (Noto Sans, SIL Open Font License — voir assets/NotoSans-OFL.txt)
# plutôt que `ImageFont.load_default()` : la police bitmap intégrée à Pillow
# ne couvre pas les caractères accentués (à, é, ç...), ce qui casse tout
# rendu en français — quasiment chaque roast produit par le prompt système
# d'E1 (modules/ia/adaptateurs/adaptateur_claude.py, "Français, 3 à 6
# phrases"). Bundlée dans le repo (pas une police système) pour un rendu
# identique sur n'importe quelle machine (dev, CI, conteneur prod) : c'est
# la même exigence de déterminisme que le choix template lui-même.
_CHEMIN_POLICE = Path(__file__).parent / "assets" / "NotoSans.ttf"

# 1200x630 : ratio ~1.91:1, la taille standard d'une image de preview sociale
# (Open Graph / Twitter Card) que K4 (backlog.md) branchera plus tard.
LARGEUR = 1200
HAUTEUR = 630

_MARGE_HORIZONTALE = 90
_LARGEUR_TEXTE_MAX = LARGEUR - 2 * _MARGE_HORIZONTALE
_HAUTEUR_CORPS_MAX = 460  # espace dispo sous le titre, avant la marge basse
_INTERLIGNE = 12

# Couleurs de marque provisoires : aucun token de design partagé n'existe
# encore côté backend (I2, backlog.md, n'est pas fait) — choisies ici et
# facilement remplaçables sans toucher à la logique de rendu (agents.md §4).
_COULEUR_HAUT = (30, 16, 62)  # violet nuit
_COULEUR_BAS = (91, 33, 122)  # violet plus clair
_COULEUR_TITRE = (255, 200, 87)  # accent doré, ton "roast"
_COULEUR_CORPS = (255, 255, 255)

_TITRE = "ANALYSE-MOI ÇA"
_TAILLE_TITRE = 32

# Échelle de tailles essayées du plus grand au plus petit : la longueur du
# texte produit par le LLM n'est bornée que par `MAX_TOKENS_REPONSE`
# (modules/ia/adaptateurs/adaptateur_claude.py), pas par un nombre de
# caractères — cette échelle absorbe la variabilité sans jamais dépasser le
# canvas (agents.md §3 : on code pour l'échec, y compris un texte plus long
# que prévu).
_TAILLES_CORPS = (44, 38, 32, 26, 22)

# Filet de sécurité ultime, sous la plus petite taille de `_TAILLES_CORPS` :
# borne le pire cas à un temps de rendu constant et à un texte qui tient
# toujours dans le canvas, quoi que retourne le fournisseur IA.
_TEXTE_LONGUEUR_MAX = 480


@cache
def _charger_police(taille: int, graisse: str) -> ImageFont.FreeTypeFont:
    # `cache` : `_ajuster_texte_et_police` essaie plusieurs tailles par
    # appel (jusqu'à `len(_TAILLES_CORPS)`) — évite de reparser le fichier
    # ttf depuis le disque à chaque tentative (agents.md §8, mesuré : le
    # parsing d'un fichier de police n'est pas gratuit, contrairement à la
    # simple sélection d'une instance déjà chargée).
    police = ImageFont.truetype(str(_CHEMIN_POLICE), size=taille)
    police.set_variation_by_name(graisse)
    return police


def generer_image_resultat(texte_resultat: str) -> bytes:
    """Rend l'image partageable du résultat d'analyse en PNG (E2, backlog.md).

    Déterministe et pur : même `texte_resultat` -> mêmes octets en sortie,
    sans appel réseau ni aléa. Destiné à être appelé par
    `GenerateurIAPort.generer_image`, dont le contrat impose de renvoyer le
    contenu binaire de l'image — la persistance reste une préoccupation
    séparée de `StockageImagePort` (agents.md §4).
    """
    image = Image.new("RGB", (LARGEUR, HAUTEUR), _COULEUR_HAUT)
    _dessiner_degrade(image)
    dessin = ImageDraw.Draw(image)

    _dessiner_titre(dessin)
    _dessiner_corps(dessin, texte_resultat)

    tampon = BytesIO()
    image.save(tampon, format="PNG")
    return tampon.getvalue()


def _dessiner_degrade(image: Image.Image) -> None:
    dessin = ImageDraw.Draw(image)
    for y in range(HAUTEUR):
        t = y / (HAUTEUR - 1)
        couleur = tuple(
            round(_COULEUR_HAUT[i] + (_COULEUR_BAS[i] - _COULEUR_HAUT[i]) * t) for i in range(3)
        )
        dessin.line([(0, y), (LARGEUR, y)], fill=couleur)


def _dessiner_titre(dessin: ImageDraw.ImageDraw) -> None:
    police = _charger_police(_TAILLE_TITRE, "SemiBold")
    dessin.text(
        (LARGEUR / 2, 70),
        _TITRE,
        font=police,
        fill=_COULEUR_TITRE,
        anchor="mm",
        align="center",
    )


def _dessiner_corps(dessin: ImageDraw.ImageDraw, texte_resultat: str) -> None:
    texte = texte_resultat.strip()
    if len(texte) > _TEXTE_LONGUEUR_MAX:
        texte = texte[:_TEXTE_LONGUEUR_MAX].rstrip() + "…"

    texte_enveloppe, police = _ajuster_texte_et_police(dessin, texte)
    centre_y = 70 + (HAUTEUR - 70) / 2  # centré dans l'espace sous le titre
    dessin.multiline_text(
        (LARGEUR / 2, centre_y),
        texte_enveloppe,
        font=police,
        fill=_COULEUR_CORPS,
        anchor="mm",
        align="center",
        spacing=_INTERLIGNE,
    )


def _ajuster_texte_et_police(
    dessin: ImageDraw.ImageDraw, texte: str
) -> tuple[str, ImageFont.FreeTypeFont]:
    """Choisit la plus grande taille de `_TAILLES_CORPS` où `texte` tient.

    Retombe sur la plus petite taille si aucune ne suffit (ne devrait pas
    arriver vu `_TEXTE_LONGUEUR_MAX`, mais ne doit jamais lever d'exception
    sur un texte imprévu — agents.md §3, dégradation gracieuse).
    """
    for taille in _TAILLES_CORPS:
        police = _charger_police(taille, "Regular")
        enveloppe = _wrapper_texte(dessin, texte, police, _LARGEUR_TEXTE_MAX)
        boite = dessin.multiline_textbbox(
            (0, 0), enveloppe, font=police, spacing=_INTERLIGNE, align="center"
        )
        if boite[3] - boite[1] <= _HAUTEUR_CORPS_MAX:
            return enveloppe, police

    police = _charger_police(_TAILLES_CORPS[-1], "Regular")
    return _wrapper_texte(dessin, texte, police, _LARGEUR_TEXTE_MAX), police


def _wrapper_texte(
    dessin: ImageDraw.ImageDraw, texte: str, police: ImageFont.FreeTypeFont, largeur_max: float
) -> str:
    """Découpe `texte` en lignes qui tiennent dans `largeur_max` pixels.

    Mesure la largeur réelle des glyphes (`textlength`) plutôt qu'un compte
    de caractères fixe (`textwrap.wrap`) : la police par défaut de Pillow
    n'est pas à chasse fixe, un découpage par caractères sous- ou
    sur-estimerait systématiquement l'espace disponible.
    """
    lignes: list[str] = []
    for paragraphe in texte.split("\n"):
        ligne = ""
        for mot in paragraphe.split():
            candidate = f"{ligne} {mot}".strip()
            if not ligne or dessin.textlength(candidate, font=police) <= largeur_max:
                ligne = candidate
            else:
                lignes.append(ligne)
                ligne = mot
        lignes.append(ligne)
    return "\n".join(lignes)
