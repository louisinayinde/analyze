import uuid
from dataclasses import dataclass
from datetime import datetime


@dataclass
class Utilisateur:
    """Entité du domaine Auth — zéro dépendance technique (agents.md §4).

    Ne connaît ni SQLAlchemy, ni FastAPI, ni Argon2id : `password_hash` est
    une chaîne opaque du point de vue du domaine, produite et vérifiée par
    les use-cases (C3, C4), jamais interprétée ici. À ne pas confondre avec
    `UtilisateurModel` (adaptateurs/models.py), qui est le modèle de
    persistance et reste inconnu de ce fichier.
    """

    id: uuid.UUID
    email: str
    password_hash: str
    created_at: datetime
    last_login_at: datetime | None = None
