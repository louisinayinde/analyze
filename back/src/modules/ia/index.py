from modules.ia.adaptateurs.adaptateur_claude import AdaptateurClaude
from modules.ia.adaptateurs.generateur_ia_factice import GenerateurIAFactice

# Seule surface publique du module (agents.md §4). D1 n'expose que
# l'adaptateur factice ; E1 y ajoute `AdaptateurClaude` (texte réel), dont
# E2 complète `generer_image` (template + overlay, voir
# rendu_image_template.py — module interne, pas exposé ici, appelé
# uniquement par `AdaptateurClaude`) sans changer la façon dont le point de
# composition ou les tests importent ce module.
__all__ = ["AdaptateurClaude", "GenerateurIAFactice"]
