# Pharma Bord, par ETDEL — https://github.com/theptitprince/Pharma-bord
# Copyright © 2026 ETDEL. Licence GPL-3.0-or-later avec conditions additionnelles
# (article 7) : voir les fichiers LICENSE et NOTICE.
"""Point d'entrée de Pharma Bord.

    python main.py                 -> interface graphique (base pharma_bord.db à côté du programme)
    python main.py --db chemin.db  -> autre fichier de base (un fichier = un navire)
    python main.py --version       -> version, mention d'auteur et licence, sans ouvrir la fenêtre
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pharma_bord import texte_version  # noqa: E402
from pharma_bord.gui import lancer  # noqa: E402


def main():
    p = argparse.ArgumentParser(description="Gestion du stock médical du bord (Division 217).",
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--db", help="fichier de base de données SQLite (défaut : pharma_bord.db)")
    p.add_argument("--version", action="version", version=texte_version(),
                   help="affiche la version, la mention d'auteur et la licence, puis quitte")
    args = p.parse_args()
    lancer(args.db)


if __name__ == "__main__":
    main()
