"""Poller IMAP de la boîte dédiée : le canal n° 1 des TPE-PME."""
from sqlalchemy.orm import Session

from ..config import settings
from ..core.audit import journaliser
from ..models import Canal
from .service import enregistrer_fichier


def traiter_boite(db: Session, *, organisation_id, acteur: str = "system") -> dict:
    """Parcourt les messages non lus, ingère chaque pièce jointe PDF/XML,
    marque lus et déplace dans le dossier de traitement. Renvoie des stats."""
    from imap_tools import MailBox, AND

    stats = {"actif": True, "messages": 0, "fichiers": 0, "doublons": 0}
    if not settings.imap_host:
        stats["actif"] = False
        return stats

    with MailBox(settings.imap_host, port=settings.imap_port).login(
        settings.imap_user,
        settings.imap_password,
        initial_folder=settings.imap_folder,
    ) as boite:
        # Le dossier de traitement est créé au besoin
        if not boite.folder.exists(settings.imap_process_folder):
            boite.folder.create(settings.imap_process_folder)

        uids_traites = []
        for msg in boite.fetch(AND(seen=False), mark_seen=False):
            stats["messages"] += 1
            for att in msg.attachments:
                if not att.filename or not att.payload:
                    continue
                resultat = enregistrer_fichier(
                    db,
                    organisation_id=organisation_id,
                    nom_fichier=att.filename,
                    contenu=att.payload,
                    canal=Canal.MAIL.value,
                    message_id=str(msg.uid),
                    recu_le=msg.date,
                    acteur=acteur,
                )
                if resultat.nouveau:
                    stats["fichiers"] += 1
                else:
                    stats["doublons"] += 1
            uids_traites.append(msg.uid)

        if uids_traites:
            for uid in uids_traites:
                boite.flag(uid, "\\Seen", True)
            boite.move(uids_traites, settings.imap_process_folder)

    journaliser(
        db,
        organisation_id=organisation_id,
        entite_type="organisation",
        entite_id=organisation_id,
        evenement="poll_imap",
        acteur=acteur,
        details=stats,
    )
    return stats
