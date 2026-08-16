import uuid
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class SourceAnalyse(StrEnum):
    """Catégorie du texte source collé par l'user (projets.md §1 : profil
    GitHub, historique d'écoute, bio, ou tout autre texte libre).

    Vocabulaire du domaine Analyse (D1) — distincte de `SourceType`
    (modules/cache/adaptateurs/models.py), qui est le type de persistance
    de la table `cache_resultat` (B6). Le mapping entre les deux est un
    détail de l'adaptateur `CachePort` (D2), jamais une préoccupation du
    domaine (agents.md §4 : le port ne connaît pas la techno).
    """

    GITHUB = "github"
    SPOTIFY = "spotify"
    BIO = "bio"
    AUTRE = "autre"


class StatutAnalyse(StrEnum):
    """Statut du cycle de vie d'une analyse, piloté par l'algorithme de
    concurrence du cache exact (projets.md §Concurrence sur le cache) :
    `PENDING` posé par le premier appelant, puis transitionné vers `DONE`
    ou `FAILED` une fois le job de génération terminé (D3).
    """

    PENDING = "pending"
    DONE = "done"
    FAILED = "failed"


@dataclass
class Analyse:
    """Entité du domaine Analyse (D1) — zéro dépendance technique
    (agents.md §4) : ne connaît ni SQLAlchemy ni la table `cache_resultat`
    (B6, `CacheResultatModel`), qui reste un détail de persistance connu
    uniquement de l'adaptateur `CachePort` (D2).

    Ne porte pas `input_hash` : le calcul de la clé de cache (hash du texte
    normalisé + source) est explicitement un détail d'implémentation de
    l'adaptateur `CachePort` (D2, backlog.md), pas une donnée du domaine —
    le use-case (D3) raisonne en termes de texte + source, jamais de hash.
    Ne porte pas non plus `hit_count` : c'est une métrique d'observabilité
    du cache partagé (projets.md §Observabilité), pas un attribut de
    l'analyse elle-même.
    """

    id: uuid.UUID
    texte_source: str
    source: SourceAnalyse
    statut: StatutAnalyse
    created_at: datetime
    resultat_texte: str | None = None
    resultat_image_url: str | None = None
