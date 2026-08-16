from modules.ia.adaptateurs.generateur_ia_factice import GenerateurIAFactice

# Seule surface publique du module (agents.md §4). D1 n'expose que
# l'adaptateur factice ; les adaptateurs réels (E1 texte, E2 image)
# rejoindront cette liste au même endroit, sans jamais changer la façon
# dont le point de composition ou les tests importent ce module.
__all__ = ["GenerateurIAFactice"]
