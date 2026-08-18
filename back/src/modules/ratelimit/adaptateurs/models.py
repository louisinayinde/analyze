from datetime import datetime

from sqlalchemy import DateTime, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from shared.db import Base


class LimiteDebitModel(Base):
    """Table `limite_debit` (G1, backlog.md) : un seau de jetons par `cle`.

    `cle` namespace le seau (ex. `"ip:1.2.3.4"`, `"user:<uuid>"`),
    construite par l'appelant du port (G2/G3) — ce modèle ne sait ni ce
    qu'est une IP ni ce qu'est un user, il ne connaît qu'une chaîne
    opaque (agents.md §4). Une seule table, partagée par toutes les
    politiques de quota : c'est `capacite`/`taux_recharge_par_seconde`,
    passés à chaque appel (`RateLimiterPort.consommer`) et jamais
    persistés ici, qui distinguent un seau « IP anonyme » d'un seau
    « user authentifié ».
    """

    __tablename__ = "limite_debit"

    cle: Mapped[str] = mapped_column(String, primary_key=True)
    jetons: Mapped[float] = mapped_column(Float, nullable=False)
    maj_a: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
