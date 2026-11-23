"""Machine à états d'une facture.

```
recue -> extraite -> controlee -> a_valider -> validee -> exportee -> payee
          extraite -> a_valider (score bas : court-circuit vers l'humain)
                       ... -> rejetee (depuis tout état non terminal)
```

Une transition impossible lève une exception : jamais de statut fantôme,
jamais de retour arrière (une facture payée ne redevient jamais validee).
"""
from enum import Enum

from ..models.enums import StatutFacture

TRANSITIONS: dict[StatutFacture, set[StatutFacture]] = {
    StatutFacture.RECUE: {StatutFacture.EXTRAITE, StatutFacture.REJETEE},
    StatutFacture.EXTRAITE: {
        StatutFacture.CONTROLEE,
        StatutFacture.A_VALIDER,  # score de confiance bas : file humaine directe
        StatutFacture.REJETEE,
    },
    StatutFacture.CONTROLEE: {StatutFacture.A_VALIDER, StatutFacture.REJETEE},
    StatutFacture.A_VALIDER: {StatutFacture.VALIDEE, StatutFacture.REJETEE},
    StatutFacture.VALIDEE: {StatutFacture.EXPORTEE, StatutFacture.REJETEE},
    StatutFacture.EXPORTEE: {StatutFacture.PAYEE},
    StatutFacture.PAYEE: set(),  # terminal
    StatutFacture.REJETEE: set(),  # terminal
}


class TransitionInvalide(Exception):
    """Transition non autorisée par la machine à états."""


def transitions_valides(statut: StatutFacture | str) -> set[StatutFacture]:
    return TRANSITIONS[StatutFacture(statut)]


def transition_possible(depart: StatutFacture | str, arrivee: StatutFacture | str) -> bool:
    return StatutFacture(arrivee) in transitions_valides(depart)
