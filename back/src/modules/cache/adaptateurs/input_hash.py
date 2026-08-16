import hashlib
import unicodedata

from modules.analyse.domaine.analyse import SourceAnalyse


def calculer_input_hash(texte_source: str, source: SourceAnalyse) -> str:
    """Clé du cache exact (D2, backlog.md) : sha256 hex du texte normalisé
    concaténé à `source` — deux sources différentes pour un même texte ne
    partagent jamais le cache (projets.md, table `CACHE_RESULTAT`).

    Détail d'implémentation de l'adaptateur `CachePort`, jamais du domaine
    (agents.md §4) : `Analyse` ne porte pas `input_hash` (voir le
    commentaire de `modules/analyse/domaine/analyse.py`).
    """

    texte_normalise = _normaliser(texte_source)
    return hashlib.sha256(f"{source.value}:{texte_normalise}".encode()).hexdigest()


def _normaliser(texte: str) -> str:
    """Neutralise les variations purement cosmétiques d'un copier-coller
    (espaces de fin de ligne, formes Unicode équivalentes) qui ne doivent
    pas produire une clé de cache différente pour un texte identique en
    substance — sinon la promesse "un seul appel LLM par input" (projets.md
    §1) se casse sur des détails de mise en forme sans rapport avec le
    contenu.
    """

    forme_normalisee = unicodedata.normalize("NFC", texte)
    return " ".join(forme_normalisee.split())
