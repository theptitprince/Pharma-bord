# Pharma Bord, par ETDEL — https://github.com/theptitprince/Pharma-bord
# Copyright © 2026 ETDEL. Licence GPL-3.0-or-later avec conditions additionnelles
# (article 7) : voir les fichiers LICENSE et NOTICE.
"""Pharma Bord – suivi de la dotation médicale des navires français (Division 217)."""

from pathlib import Path

__version__ = "1.1.0"

# Mentions légales affichées par le programme (bandeau d'en-tête, fenêtre « À propos », --version).
# MENTION est exigée par les conditions additionnelles de la licence (fichier NOTICE, article 7 b).
URL_DEPOT = "https://github.com/theptitprince/Pharma-bord"
MENTION = f"Pharma Bord, par ETDEL — {URL_DEPOT}"
COPYRIGHT = "Copyright © 2026 ETDEL"
URL_LICENCE = "https://www.gnu.org/licenses/gpl-3.0.html"
URL_NOTICE = f"{URL_DEPOT}/blob/main/NOTICE"
FICHIER_LICENCE = Path(__file__).resolve().parent.parent / "LICENSE"
FICHIER_NOTICE = Path(__file__).resolve().parent.parent / "NOTICE"


def texte_a_propos() -> str:
    """Texte de la fenêtre « À propos » ; la première ligne donne le nom et la version."""
    return "\n".join((
        f"Pharma Bord v{__version__}",
        "Gestion du stock médical réglementaire du bord (Division 217).",
        "",
        MENTION,
        COPYRIGHT,
        "",
        "Logiciel libre, distribué sous la licence GNU General Public License, version 3 ou (à votre "
        "choix) toute version ultérieure (GPL-3.0-or-later), avec des conditions additionnelles "
        "(article 7) décrites dans le fichier NOTICE.",
        "",
        "Ce programme est fourni SANS AUCUNE GARANTIE, dans les limites permises par la loi.",
        "",
        f"Texte de la licence : fichier LICENSE à côté du programme, ou {URL_LICENCE}",
        f"Conditions additionnelles : fichier NOTICE à côté du programme, ou {URL_NOTICE}",
        "",
        "Une version modifiée doit le dire, et ne pas se présenter comme l'original "
        "ni comme approuvée par ETDEL.",
    ))


def texte_version() -> str:
    """Texte affiché par ``python main.py --version``."""
    return "\n".join((
        f"Pharma Bord {__version__}",
        MENTION,
        COPYRIGHT,
        "Licence GPL-3.0-or-later, avec conditions additionnelles (article 7) : fichiers LICENSE et NOTICE.",
        "Ce programme est fourni SANS AUCUNE GARANTIE, dans les limites permises par la loi.",
    ))
