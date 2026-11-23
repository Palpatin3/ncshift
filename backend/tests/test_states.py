"""La machine à états : le garde-fou du produit. Interdiction = exception."""
import pytest

from app.core.states import TransitionInvalide, transition_possible, transitions_valides
from app.models import StatutFacture as S


def test_chemin_nominal_complet():
    chemin = [S.RECUE, S.EXTRAITE, S.CONTROLEE, S.A_VALIDER, S.VALIDEE, S.EXPORTEE, S.PAYEE]
    for depart, arrivee in zip(chemin, chemin[1:]):
        assert transition_possible(depart, arrivee), f"{depart} -> {arrivee}"


def test_score_bas_court_circuite_vers_validation_humaine():
    assert transition_possible(S.EXTRAITE, S.A_VALIDER)


def test_pas_de_retour_arriere():
    assert not transition_possible(S.VALIDEE, S.CONTROLEE)
    assert not transition_possible(S.PAYEE, S.VALIDEE)


def test_etats_terminaux():
    assert transitions_valides(S.PAYEE) == set()
    assert transitions_valides(S.REJETEE) == set()


def test_rejet_depuis_tout_etat_non_terminal():
    for statut in [S.RECUE, S.EXTRAITE, S.CONTROLEE, S.A_VALIDER, S.VALIDEE]:
        assert transition_possible(statut, S.REJETEE)
