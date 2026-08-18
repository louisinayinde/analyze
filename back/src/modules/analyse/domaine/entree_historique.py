import uuid
from dataclasses import dataclass
from datetime import datetime


@dataclass
class EntreeHistorique:
    """Entité du domaine Analyse (H3) — zéro dépendance technique (agents.md §4).

    Une ligne d'historique personnel : un texte soumis par un utilisateur
    authentifié, et l'id du résultat partagé (`resultat_id`, même valeur que
    `Analyse.id`) qu'il a produit ou réutilisé. Ne porte jamais le résultat
    lui-même (texte/image générés) : `GET /historique` ne fait que lister,
    le détail complet reste consulté via `GET /analyses/{id}/statut` en
    suivant `resultat_id` (K6, backlog.md — lien vers `/analyse/[id]`).
    """

    id: uuid.UUID
    resultat_id: uuid.UUID
    input_text: str
    created_at: datetime
