# Pharma Bord, par ETDEL — https://github.com/theptitprince/Pharma-bord
# Copyright © 2026 ETDEL. Licence GPL-3.0-or-later avec conditions additionnelles
# (article 7) : voir les fichiers LICENSE et NOTICE.
"""Chargement du référentiel réglementaire depuis le dossier ``referentiel/``.

Le référentiel est une transcription de la Division 217 : il n'est pas destiné à
être modifié par l'utilisateur. Le dossier contient un fichier JSON par dotation
(``Dotation_A.json``, ``Complement_P2.json``, ``Sac_medical_urgence.json``, ...) :

    {
      "format": "pharma-bord/referentiel/1",
      "code": "A", "titre": "...", "conditions_emploi": "...", "source": "...",
      "medicaments": [ {"categorie": "1. Cardiologie", "conditions": [...],
                        "articles": [ {"dci", "voie", "forme", "quantite", "liste", "conditions"} ]} ],
      "materiel":    [ {"categorie": "...", "conditions": [...],
                        "articles": [ {"article", "presentation", "quantite", "remarques", "conditions"} ]} ]
    }

Chaque article possède un identifiant stable (``item_id``) construit à partir de
son libellé et de sa forme, identique d'une dotation à l'autre : l'inventaire du
bord est rattaché à ces identifiants et reste valable si le navire change de
zone de navigation.
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

REF_DIR = Path(__file__).resolve().parent.parent / "referentiel"
FORMAT_REFERENTIEL = "pharma-bord/referentiel/1"

TYPE_MED = "MED"
TYPE_MAT = "MAT"

# Codes ATC des principales DCI (annexe 217-3.A.5, bons de commande type).
ATC = {
    "acide acetylsalicylique": "B01AC06",
    "acetylsalicylate de lysine": "B01AC06",
    "atropine": "A03BA01",
    "epinephrine": "C01CA24",
    "furosemide": "C03CA01",
    "trinitrine": "C01DA02",
    "isosorbide dinitrate": "C01DA08",
    "nitrendipine": "C08CA08",
    "atenolol": "C07AB03",
    "ticagrelor": "B01AC24",
    "amiodarone": "C01BD01",
    "enoxaparine sodique": "B01AB05",
    "hydroxydes d'aluminium et de magnesium": "A02AD01",
    "diosmectite": "A07BC05",
    "macrogol 4000": "A06AD15",
    "carraghenates - dioxyde de titane - oxyde de zinc": "C05AX04",
    "carraghenates - dioxyde de titane - oxyde de zinc - lidocaine 2 %": "C05AX04",
    "lavement hydrogenophosphates": "A06AG20",
    "metopimazine": "A04AD05",
    "racecadotril": "A07XA04",
    "racecadotril nourrisson": "A07XA04",
    "omeprazole": "A02BC01",
    "ondansetron": "A04AA01",
    "paracetamol": "N02BE01",
    "phloroglucinol": "A03AX12",
    "colchicine": "M04AC01",
    "ketoprofene": "M01AE03",
    "tramadol": "N02AX02",
    "morphine chlorhydrate": "N02AA01",
    "naloxone": "V03AB15",
    "dimenhydrinate": "R06AA02",
    "hydroxyzine": "N05BB01",
    "zopiclone": "N05CF01",
    "escitalopram": "N06AB10",
    "diazepam": "N05BA01",
    "loxapine": "N05AH01",
    "desloratadine": "R06AX27",
    "prednisolone": "H02AB06",
    "methylprednisolone": "H02AB04",
    "acetylcysteine": "R05CB01",
    "salbutamol": "R03AC02",
    "terbutaline": "R03AC03",
    "ipratropium bromure": "R03BB01",
    "amoxicilline": "J01CA04",
    "amoxicilline - acide clavulanique": "J01CR02",
    "azithromycine": "J01FA10",
    "ceftriaxone": "J01DD04",
    "gentamicine": "J01GB03",
    "levofloxacine": "J01MA12",
    "metronidazole": "J01XD01",
    "valaciclovir": "J05AB11",
    "albendazole": "P02CA03",
    "ivermectine": "P02CF01",
    "oseltamivir": "J05AH02",
    "vaccin diphterie-tetanos-poliomyelite (inactive adsorbe)": "J07CA01",
    "econazole": "G01AF05",
    "misoprostol": "G02AD06",
    "acide tranexamique": "B02AA02",
    "chlorure de sodium": "B05XA03",
    "bicarbonate de sodium": "B05XA02",
    "glucose": "B05BA03",
    "glucose hypertonique": "B05BA03",
    "chlorure de potassium": "A12BA01",
    "eau pour preparation injectable": "V07AB",
    "chlorhexidine": "D08AC02",
    "hexamidine - chlorhexidine - chlorocresol": "D08AC52",
    "vaseline sterilisee": "D02AC",
    "sulfadiazine argentique": "D06BA01",
    "d-phenothrine": "P03AC03",
    "benzoate de benzyle": "P03AX01",
    "mupirocine": "D06AX09",
    "betamethasone": "D07AC01",
    "acide borique - borate de sodium": "S01AX07",
    "hexamidine": "S01AX08",
    "dexamethasone - oxytetracycline": "S01CA01",
    "rifamycine": "S01AA16",
    "ciprofloxacine": "S01AE03",
    "indometacine": "S01BC01",
    "aciclovir": "S01AD03",
    "pilocarpine": "S01EB01",
    "oxybuprocaine chlorhydrate": "S01HA02",
    "fluoresceine": "S01JA01",
    "acetazolamide": "S01EC01",
    "xylene": "S02DC",
    "phenazone - lidocaine": "S02DA01",
    "ofloxacine": "S02AA16",
    "chlorhexidine - chlorobutanol": "A01AB03",
    "amyleine chlorhydrate - levomenthol": "A01AD11",
    "lidocaine": "N01BB02",
    "lidocaine - prilocaine": "N01BB20",
    "piperaquine - artenimol": "P01BF05",
    "quinine": "P01BC01",
    "atovaquone - proguanil": "P01BB51",
    "lamivudine - zidovudine": "J05AR01",
    "lopinavir - ritonavir": "J05AR10",
    "loperamide": "A07DA03",
    "oxytocine": "H01BB02",
    "ibuprofene": "M01AE01",
    "digoxine": "C01AA05",
    "adenosine triphosphate": "C01EB10",
    "magnesium sulfate": "B05XA05",
    "urapidil": "C02CA06",
    "heparine": "B01AB01",
    "beclometasone": "R03BA01",
}


class ErreurReferentiel(Exception):
    """Erreur de lecture du référentiel (fichier absent, feuille manquante, ...)."""


def strip_accents(text: str) -> str:
    """Retire les accents (utilisé pour les identifiants et la recherche)."""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def normalize(text: str) -> str:
    """Forme normalisée d'un libellé : minuscules, sans accents, espaces simples."""
    t = strip_accents(str(text)).lower().replace("’", "'")
    t = re.sub(r"\s+", " ", t).strip()
    return t


def make_id(*parts: str) -> str:
    """Identifiant stable à partir de plusieurs libellés."""
    raw = "|".join(normalize(p) for p in parts if p)
    raw = re.sub(r"[^a-z0-9|]+", "-", raw)
    raw = re.sub(r"-+", "-", raw).strip("-|")
    return raw


@dataclass
class Article:
    """Un article du référentiel (médicament ou matériel)."""

    item_id: str
    type: str                      # MED ou MAT
    nom: str                       # DCI ou désignation
    voie: str = ""                 # médicaments : voie d'administration
    forme: str = ""                # médicaments : forme / composition ; matériel : présentation
    liste: str = ""                # "", "I", "II", "Stupéfiant"
    remarques: str = ""            # matériel : remarques
    kit: str = ""                  # "" ou nom du kit (ex. "trousse")
    atc: str = ""
    perso: bool = False            # article hors dotation créé par l'utilisateur
    categorie_perso: str = ""      # sous-catégorie choisie pour un article hors dotation

    @property
    def libelle(self) -> str:
        base = self.nom
        if self.forme:
            base += f" – {self.forme}"
        if self.kit:
            base = f"[{self.kit.capitalize()}] " + base
        return base

    @property
    def est_stupefiant(self) -> bool:
        return normalize(self.liste).startswith("stup")


@dataclass
class LigneDotation:
    """Une ligne d'une dotation : un article, une quantité réglementaire, un contexte."""

    article: Article
    categorie: str
    quantite: Optional[int]        # None si non numérique
    quantite_texte: str = ""       # texte réglementaire si non numérique
    flags_categorie: List[str] = field(default_factory=list)
    flags_article: List[str] = field(default_factory=list)
    dotation: str = ""             # code de la dotation (A, B, P2, SMU, ...)


@dataclass
class Dotation:
    code: str
    titre: str
    conditions: str = ""
    source: str = ""
    fichier: str = ""
    medicaments: List[LigneDotation] = field(default_factory=list)
    materiel: List[LigneDotation] = field(default_factory=list)

    @property
    def lignes(self) -> List[LigneDotation]:
        return self.medicaments + self.materiel


def _txt(v) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return str(v).strip()


def _flags(v) -> List[str]:
    if isinstance(v, str):
        v = v.split(",")
    return [str(f).strip().lower() for f in (v or []) if str(f).strip()]


class Referentiel:
    """Ensemble des dotations et des articles du référentiel réglementaire (lecture seule)."""

    def __init__(self, dossier: Path = REF_DIR):
        self.dossier = Path(dossier)
        self.dotations: Dict[str, Dotation] = {}
        self.articles: Dict[str, Article] = {}
        self.avertissements: List[str] = []
        self._charger()

    # ------------------------------------------------------------------ lecture
    def _charger(self) -> None:
        if not self.dossier.is_dir():
            raise ErreurReferentiel(f"Dossier du référentiel introuvable : {self.dossier}")
        fichiers = sorted(self.dossier.glob("*.json"))
        if not fichiers:
            raise ErreurReferentiel(f"Aucun fichier de dotation (.json) dans {self.dossier}")
        for fichier in fichiers:
            try:
                data = json.loads(fichier.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                self.avertissements.append(f"{fichier.name} : illisible ({exc})")
                continue
            if not isinstance(data, dict) or data.get("format") != FORMAT_REFERENTIEL:
                self.avertissements.append(f"{fichier.name} : format inconnu, fichier ignoré")
                continue
            self._charger_dotation(fichier, data)

    def _charger_dotation(self, fichier: Path, data: dict) -> None:
        code = _txt(data.get("code")).upper()
        if not code:
            self.avertissements.append(f"{fichier.name} : « code » absent, fichier ignoré")
            return
        if code in self.dotations:
            self.avertissements.append(
                f"{fichier.name} : code {code} déjà défini par {self.dotations[code].fichier}, fichier ignoré")
            return
        dot = Dotation(code=code, titre=_txt(data.get("titre")) or code,
                       conditions=_txt(data.get("conditions_emploi")),
                       source=_txt(data.get("source")), fichier=fichier.name)
        dot.medicaments = self._lire_categories(data.get("medicaments") or [], TYPE_MED, code, fichier.name)
        dot.materiel = self._lire_categories(data.get("materiel") or [], TYPE_MAT, code, fichier.name)
        self.dotations[code] = dot

    def _lire_categories(self, categories: list, typ: str, code: str, nom_fichier: str) -> List[LigneDotation]:
        lignes: List[LigneDotation] = []
        for bloc in categories:
            cat = _txt(bloc.get("categorie"))
            fcat = _flags(bloc.get("conditions"))
            kit = self._kit(fcat)
            for a in bloc.get("articles") or []:
                if typ == TYPE_MED:
                    nom, forme = _txt(a.get("dci")), _txt(a.get("forme"))
                else:
                    nom, forme = _txt(a.get("article")), _txt(a.get("presentation"))
                if not nom:
                    continue
                item_id = make_id(kit, typ.lower(), nom, forme)
                art = self.articles.get(item_id)
                if art is None:
                    if typ == TYPE_MED:
                        art = Article(item_id=item_id, type=TYPE_MED, nom=nom, voie=_txt(a.get("voie")), forme=forme,
                                      liste=_txt(a.get("liste")), kit=kit, atc=ATC.get(normalize(nom), ""))
                    else:
                        art = Article(item_id=item_id, type=TYPE_MAT, nom=nom, forme=forme,
                                      remarques=_txt(a.get("remarques")), kit=kit)
                    self.articles[item_id] = art
                quantite, qte_texte = self._parse_quantite(_txt(a.get("quantite")))
                if quantite is None and not qte_texte:
                    self.avertissements.append(f"{nom_fichier} : quantité vide pour « {nom} »")
                lignes.append(LigneDotation(article=art, categorie=cat, quantite=quantite,
                                            quantite_texte=qte_texte, flags_categorie=fcat,
                                            flags_article=_flags(a.get("conditions")), dotation=code))
        return lignes

    @staticmethod
    def _kit(flags: List[str]) -> str:
        for f in flags:
            if f.startswith("kit:"):
                return f[4:].strip()
        return ""

    @staticmethod
    def _parse_quantite(texte: str):
        t = texte.strip()
        if re.fullmatch(r"\d+", t):
            return int(t), ""
        return None, t

    # ------------------------------------------------------------------ accès
    def dotation(self, code: str) -> Dotation:
        try:
            return self.dotations[code.upper()]
        except KeyError:
            raise ErreurReferentiel(f"Dotation « {code} » absente du référentiel ({self.dossier})")

    def article(self, item_id: str) -> Optional[Article]:
        return self.articles.get(item_id)

    def rechercher(self, texte: str) -> List[Article]:
        n = normalize(texte)
        return [a for a in self.articles.values() if n in normalize(a.libelle)]


_REF: Optional[Referentiel] = None


def get_referentiel(recharger: bool = False) -> Referentiel:
    """Instance partagée du référentiel (chargée une seule fois)."""
    global _REF
    if _REF is None or recharger:
        _REF = Referentiel()
    return _REF
