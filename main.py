"""Point d'entrée de Pharma Bord.

    python main.py                 -> interface graphique (base pharma_bord.db à côté du programme)
    python main.py --db chemin.db  -> autre fichier de base (un fichier = un navire)
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pharma_bord.gui import lancer  # noqa: E402


def main():
    p = argparse.ArgumentParser(description="Gestion du stock médical du bord (Division 217).")
    p.add_argument("--db", help="fichier de base de données SQLite (défaut : pharma_bord.db)")
    args = p.parse_args()
    lancer(args.db)


if __name__ == "__main__":
    main()
