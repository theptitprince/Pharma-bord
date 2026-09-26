"""Stockage local (SQLite) : configuration du navire, lots en stock, registre des mouvements.

Une base = un navire. Le fichier ``pharma_bord.db`` est créé dans le dossier du
programme (ou à l'emplacement passé à :class:`BaseDonnees`).
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field, asdict
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Optional

DB_FILE = Path(__file__).resolve().parent.parent / "pharma_bord.db"

TYPES_MOUVEMENT = ("entrée", "distribution", "débarquement", "perte", "sortie", "ajustement")


@dataclass
class ConfigNavire:
    """Configuration du navire et options qui déterminent la dotation exigée."""

    nom: str = ""
    immatriculation: str = ""
    armement: str = ""
    port_attache: str = ""
    capitaine: str = ""
    responsable_soins: str = ""
    effectif: int = 25
    dotation_base: str = "A"           # A, B, BR, C, CR, CAT5
    complement_passagers: str = ""     # "", P1, P2, P3, P4
    nb_passagers: int = 0
    zone_paludisme: bool = False
    aes: bool = False                  # accidents d'exposition au sang (recommandé)
    dae: bool = False                  # DAE recommandé (dotation B)
    sac_medical_urgence: bool = False
    plongee: bool = False
    navire_peche: bool = False
    desserte_courte: bool = False      # dessertes régulières < 30 min (P4)
    marchandises_dangereuses: bool = False
    coefficient_manuel: Optional[float] = None
    delai_jours: int = 90              # horizon par défaut pour les commandes
    marge_jours: int = 30              # marge de sécurité sur les péremptions
    pharmacien: str = ""               # établissement pharmaceutique habituel
    adresse_armement: str = ""
    adresse_pharmacien: str = ""
    fonction_responsable: str = ""     # fonction du signataire du bon de commande

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)

    @classmethod
    def from_json(cls, texte: str) -> "ConfigNavire":
        data = json.loads(texte) if texte else {}
        cfg = cls()
        for k, v in data.items():
            if hasattr(cfg, k):
                setattr(cfg, k, v)
        return cfg


@dataclass
class Lot:
    """Une boîte / un lot physique d'un article, avec sa propre date de péremption."""

    id: Optional[int]
    item_id: str
    quantite: int
    peremption: Optional[date] = None
    numero_lot: str = ""
    specialite: str = ""      # nom commercial / fabricant
    emplacement: str = ""
    date_entree: Optional[date] = None
    commentaire: str = ""

    def est_perime(self, ref: date) -> bool:
        return self.peremption is not None and self.peremption < ref

    def valide_a(self, horizon: date) -> bool:
        """Vrai si le lot sera encore utilisable à la date ``horizon`` (péremption >= horizon)."""
        return self.peremption is None or self.peremption >= horizon


@dataclass
class Mouvement:
    id: Optional[int]
    horodatage: datetime
    item_id: str
    lot_id: Optional[int]
    type: str
    quantite: int
    motif: str = ""
    personne: str = ""
    patient: str = ""
    commentaire: str = ""


@dataclass
class ArticlePerso:
    """Article ajouté par l'utilisateur, absent du référentiel réglementaire."""

    item_id: str
    type: str
    nom: str
    forme: str = ""
    voie: str = ""
    liste: str = ""
    remarques: str = ""
    categorie: str = ""        # sous-catégorie du groupe « Hors dotation »


@dataclass
class ExigenceSupplementaire:
    """Quantité exigée en plus du réglementaire (consigne armement, médecin, ...)."""

    item_id: str
    quantite: int
    motif: str = ""


def _d(v) -> Optional[date]:
    return date.fromisoformat(v) if v else None


class BaseDonnees:
    """Accès à la base SQLite. Toutes les méthodes valident (commit) immédiatement."""

    def __init__(self, chemin: Path = DB_FILE):
        self.chemin = Path(chemin)
        self.conn = sqlite3.connect(str(self.chemin))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self._creer_schema()

    def close(self) -> None:
        self.conn.close()

    # ------------------------------------------------------------------ schéma
    def _creer_schema(self) -> None:
        c = self.conn
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS parametres (
                cle TEXT PRIMARY KEY,
                valeur TEXT
            );
            CREATE TABLE IF NOT EXISTS articles_perso (
                item_id TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                nom TEXT NOT NULL,
                forme TEXT DEFAULT '',
                voie TEXT DEFAULT '',
                liste TEXT DEFAULT '',
                remarques TEXT DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS exigences_supp (
                item_id TEXT PRIMARY KEY,
                quantite INTEGER NOT NULL,
                motif TEXT DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS lots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id TEXT NOT NULL,
                quantite INTEGER NOT NULL,
                peremption TEXT,
                numero_lot TEXT DEFAULT '',
                specialite TEXT DEFAULT '',
                emplacement TEXT DEFAULT '',
                date_entree TEXT,
                commentaire TEXT DEFAULT ''
            );
            CREATE INDEX IF NOT EXISTS idx_lots_item ON lots(item_id);
            CREATE TABLE IF NOT EXISTS mouvements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                horodatage TEXT NOT NULL,
                item_id TEXT NOT NULL,
                lot_id INTEGER,
                type TEXT NOT NULL,
                quantite INTEGER NOT NULL,
                motif TEXT DEFAULT '',
                personne TEXT DEFAULT '',
                patient TEXT DEFAULT '',
                commentaire TEXT DEFAULT ''
            );
            CREATE INDEX IF NOT EXISTS idx_mvt_item ON mouvements(item_id);
            """
        )
        # migrations des bases créées par une version antérieure
        colonnes = {r["name"] for r in c.execute("PRAGMA table_info(articles_perso)")}
        if "categorie" not in colonnes:
            c.execute("ALTER TABLE articles_perso ADD COLUMN categorie TEXT DEFAULT ''")
        c.commit()

    # ------------------------------------------------------------------ config
    def charger_config(self) -> ConfigNavire:
        row = self.conn.execute("SELECT valeur FROM parametres WHERE cle='config'").fetchone()
        return ConfigNavire.from_json(row["valeur"]) if row else ConfigNavire()

    def sauver_config(self, cfg: ConfigNavire) -> None:
        self.conn.execute(
            "INSERT INTO parametres(cle, valeur) VALUES('config', ?) "
            "ON CONFLICT(cle) DO UPDATE SET valeur=excluded.valeur", (cfg.to_json(),))
        self.conn.commit()

    def parametre(self, cle: str, defaut: str = "") -> str:
        row = self.conn.execute("SELECT valeur FROM parametres WHERE cle=?", (cle,)).fetchone()
        return row["valeur"] if row else defaut

    def sauver_parametre(self, cle: str, valeur: str) -> None:
        self.conn.execute(
            "INSERT INTO parametres(cle, valeur) VALUES(?, ?) "
            "ON CONFLICT(cle) DO UPDATE SET valeur=excluded.valeur", (cle, valeur))
        self.conn.commit()

    # ------------------------------------------------------------------ articles perso
    def articles_perso(self) -> Dict[str, ArticlePerso]:
        rows = self.conn.execute("SELECT * FROM articles_perso ORDER BY nom").fetchall()
        return {r["item_id"]: ArticlePerso(**{k: (r[k] if r[k] is not None else "") for k in r.keys()}) for r in rows}

    def sauver_article_perso(self, a: ArticlePerso) -> None:
        self.conn.execute(
            "INSERT INTO articles_perso(item_id,type,nom,forme,voie,liste,remarques,categorie) VALUES(?,?,?,?,?,?,?,?) "
            "ON CONFLICT(item_id) DO UPDATE SET type=excluded.type, nom=excluded.nom, forme=excluded.forme, "
            "voie=excluded.voie, liste=excluded.liste, remarques=excluded.remarques, categorie=excluded.categorie",
            (a.item_id, a.type, a.nom, a.forme, a.voie, a.liste, a.remarques, a.categorie))
        self.conn.commit()

    def supprimer_article_perso(self, item_id: str) -> None:
        self.conn.execute("DELETE FROM articles_perso WHERE item_id=?", (item_id,))
        self.conn.execute("DELETE FROM exigences_supp WHERE item_id=?", (item_id,))
        self.conn.commit()

    # ------------------------------------------------------------------ exigences supp.
    def exigences_supp(self) -> Dict[str, ExigenceSupplementaire]:
        rows = self.conn.execute("SELECT * FROM exigences_supp").fetchall()
        return {r["item_id"]: ExigenceSupplementaire(r["item_id"], r["quantite"], r["motif"]) for r in rows}

    def sauver_exigence_supp(self, e: ExigenceSupplementaire) -> None:
        if e.quantite <= 0:
            self.conn.execute("DELETE FROM exigences_supp WHERE item_id=?", (e.item_id,))
        else:
            self.conn.execute(
                "INSERT INTO exigences_supp(item_id,quantite,motif) VALUES(?,?,?) "
                "ON CONFLICT(item_id) DO UPDATE SET quantite=excluded.quantite, motif=excluded.motif",
                (e.item_id, e.quantite, e.motif))
        self.conn.commit()

    # ------------------------------------------------------------------ lots
    def lots(self, item_id: Optional[str] = None) -> List[Lot]:
        if item_id is None:
            rows = self.conn.execute("SELECT * FROM lots ORDER BY item_id, peremption").fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM lots WHERE item_id=? ORDER BY peremption IS NULL, peremption", (item_id,)).fetchall()
        return [self._lot(r) for r in rows]

    def lots_par_article(self) -> Dict[str, List[Lot]]:
        res: Dict[str, List[Lot]] = {}
        for lot in self.lots():
            res.setdefault(lot.item_id, []).append(lot)
        return res

    def lot(self, lot_id: int) -> Optional[Lot]:
        row = self.conn.execute("SELECT * FROM lots WHERE id=?", (lot_id,)).fetchone()
        return self._lot(row) if row else None

    @staticmethod
    def _lot(r) -> Lot:
        return Lot(id=r["id"], item_id=r["item_id"], quantite=r["quantite"],
                   peremption=_d(r["peremption"]), numero_lot=r["numero_lot"] or "",
                   specialite=r["specialite"] or "", emplacement=r["emplacement"] or "",
                   date_entree=_d(r["date_entree"]), commentaire=r["commentaire"] or "")

    def ajouter_lot(self, lot: Lot, personne: str = "", motif: str = "Réception") -> Lot:
        """Crée un lot et enregistre le mouvement d'entrée correspondant."""
        cur = self.conn.execute(
            "INSERT INTO lots(item_id,quantite,peremption,numero_lot,specialite,emplacement,date_entree,commentaire) "
            "VALUES(?,?,?,?,?,?,?,?)",
            (lot.item_id, lot.quantite, lot.peremption.isoformat() if lot.peremption else None,
             lot.numero_lot, lot.specialite, lot.emplacement,
             (lot.date_entree or date.today()).isoformat(), lot.commentaire))
        lot.id = cur.lastrowid
        self._mouvement(lot.item_id, lot.id, "entrée", lot.quantite, motif, personne, "", "")
        self.conn.commit()
        return lot

    def modifier_lot(self, lot: Lot, personne: str = "", motif: str = "Correction") -> None:
        """Met à jour un lot ; un écart de quantité est tracé comme ajustement."""
        ancien = self.lot(lot.id)
        self.conn.execute(
            "UPDATE lots SET quantite=?, peremption=?, numero_lot=?, specialite=?, emplacement=?, "
            "date_entree=?, commentaire=? WHERE id=?",
            (lot.quantite, lot.peremption.isoformat() if lot.peremption else None, lot.numero_lot,
             lot.specialite, lot.emplacement, lot.date_entree.isoformat() if lot.date_entree else None,
             lot.commentaire, lot.id))
        if ancien and ancien.quantite != lot.quantite:
            self._mouvement(lot.item_id, lot.id, "ajustement", lot.quantite - ancien.quantite,
                            motif, personne, "", "")
        self.conn.commit()

    def sortie_lot(self, lot_id: int, quantite: int, motif: str = "", personne: str = "",
                   patient: str = "", commentaire: str = "", type_mvt: str = "sortie") -> None:
        """Retire ``quantite`` unités d'un lot (distribution, débarquement de périmés, perte...)."""
        lot = self.lot(lot_id)
        if lot is None:
            raise ValueError("Lot inconnu")
        if quantite <= 0 or quantite > lot.quantite:
            raise ValueError(f"Quantité invalide (stock du lot : {lot.quantite})")
        reste = lot.quantite - quantite
        if reste == 0:
            self.conn.execute("DELETE FROM lots WHERE id=?", (lot_id,))
        else:
            self.conn.execute("UPDATE lots SET quantite=? WHERE id=?", (reste, lot_id))
        self._mouvement(lot.item_id, lot_id, type_mvt, -quantite, motif, personne, patient, commentaire)
        self.conn.commit()

    def supprimer_lot(self, lot_id: int, personne: str = "", motif: str = "Suppression") -> None:
        lot = self.lot(lot_id)
        if lot is None:
            return
        self.conn.execute("DELETE FROM lots WHERE id=?", (lot_id,))
        self._mouvement(lot.item_id, lot_id, "ajustement", -lot.quantite, motif, personne, "", "")
        self.conn.commit()

    # ------------------------------------------------------------------ mouvements
    def _mouvement(self, item_id, lot_id, type_mvt, quantite, motif, personne, patient, commentaire):
        self.conn.execute(
            "INSERT INTO mouvements(horodatage,item_id,lot_id,type,quantite,motif,personne,patient,commentaire) "
            "VALUES(?,?,?,?,?,?,?,?,?)",
            (datetime.now().replace(microsecond=0).isoformat(sep=" "), item_id, lot_id, type_mvt,
             quantite, motif, personne, patient, commentaire))

    def mouvements(self, item_id: Optional[str] = None, limite: int = 5000) -> List[Mouvement]:
        if item_id:
            rows = self.conn.execute(
                "SELECT * FROM mouvements WHERE item_id=? ORDER BY horodatage DESC, id DESC LIMIT ?",
                (item_id, limite)).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM mouvements ORDER BY horodatage DESC, id DESC LIMIT ?", (limite,)).fetchall()
        return [Mouvement(id=r["id"], horodatage=datetime.fromisoformat(r["horodatage"]),
                          item_id=r["item_id"], lot_id=r["lot_id"], type=r["type"], quantite=r["quantite"],
                          motif=r["motif"] or "", personne=r["personne"] or "", patient=r["patient"] or "",
                          commentaire=r["commentaire"] or "") for r in rows]
