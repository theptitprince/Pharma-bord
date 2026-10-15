# Pharma Bord, par ETDEL — https://github.com/theptitprince/Pharma-bord
# Copyright © 2026 ETDEL. Licence GPL-3.0-or-later avec conditions additionnelles
# (article 7) : voir les fichiers LICENSE et NOTICE.
"""Moteur de calcul : dotation exigée pour un navire, état du stock, commande à passer.

Deux étapes :

1. :func:`calculer_exigences` transforme la configuration du navire (dotation de
   base, complément passagers, effectif, options) en une liste d'exigences :
   pour chaque article, la quantité réglementaire à détenir.
2. :func:`analyser` confronte ces exigences aux lots en stock à une date
   d'horizon (fin de la prochaine traversée) et calcule ce qu'il faut commander
   à la prochaine escale.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Dict, List, Optional

from .db import ArticlePerso, ConfigNavire, ExigenceSupplementaire, Lot
from .referentiel import Article, LigneDotation, Referentiel, TYPE_MAT, TYPE_MED

BASE_EFFECTIF_A = 25
DOTATIONS_BASE = ("A", "B", "BR", "C", "CR", "CAT5")
COMPLEMENTS = ("", "P1", "P2", "P3", "P4")

LIBELLES_DOTATION = {
    "A": "Dotation A – navigation sans limitation (base 25 marins)",
    "B": "Dotation B – 20 à 150 milles d'un port médicalement équipé (200 milles avec hélitreuillage)",
    "BR": "Dotation B restreinte – 2e catégorie restreinte, ≤ 60 milles des côtes",
    "C": "Dotation C – ≤ 20 milles des côtes",
    "CR": "Dotation C restreinte – ≤ 20 milles des côtes et < 24 h à la mer",
    "CAT5": "Dotation 5e catégorie de navigation",
    "": "Aucun (navire sans passagers)",
    "P1": "P1 – navire à passagers de jauge brute ≥ 500",
    "P2": "P2 – roulier mixte restant 6 à 24 h à la mer",
    "P3": "P3 – transbordeur / navire à passagers entre 1 h et 6 h d'un port",
    "P4": "P4 – navire à passagers à moins d'une heure d'un port",
}


@dataclass
class Origine:
    """D'où provient une part de la quantité exigée (traçabilité du calcul)."""

    dotation: str
    categorie: str
    quantite_brute: Optional[int]
    coefficient: float
    quantite: Optional[int]
    note: str = ""


@dataclass
class Exigence:
    article: Article
    quantite: Optional[int]            # None si non quantifiable numériquement
    quantite_texte: str = ""
    obligatoire: bool = True
    origines: List[Origine] = field(default_factory=list)
    categorie: str = ""                # catégorie de présentation (première origine)
    liste: str = ""

    @property
    def est_stupefiant(self) -> bool:
        return self.article.est_stupefiant

    @property
    def reglementaire(self) -> bool:
        """Vrai si au moins une part de la quantité vient d'une dotation réglementaire."""
        return any(o.dotation != "SUPP" for o in self.origines)


CAT_HORS_DOTATION_DEFAUT = "Divers"
CAT_AUTRE_DOTATION = "Articles absents de la dotation actuelle"
SOUS_CATEGORIES_HORS_DOTATION = (
    "Antidotes (marchandises dangereuses, GSMU)",
    "Consignes de l'armement",
    "Confort et automédication",
    "Traitements personnels de l'équipage",
    "Matériel complémentaire",
    CAT_HORS_DOTATION_DEFAUT,
)


def article_depuis_perso(p: ArticlePerso) -> Article:
    return Article(item_id=p.item_id, type=p.type, nom=p.nom, voie=p.voie, forme=p.forme, liste=p.liste,
                   remarques=p.remarques, perso=True, categorie_perso=p.categorie or CAT_HORS_DOTATION_DEFAUT)


def coefficient_effectif(effectif: int, base: int = BASE_EFFECTIF_A) -> float:
    """Coefficient d'adaptation des quantités à l'effectif (annexe 217-3.A.7, note 1).

    * +50 % par multiple entier de la base, sans dépasser deux dotations ;
    * -50 % pour un effectif inférieur à la moitié de la base.
    """
    if effectif <= 0:
        return 1.0
    if effectif < base / 2:
        return 0.5
    multiples = effectif // base           # 25..49 -> 1 ; 50..74 -> 2 ; 75.. -> 3
    coef = 1.0 + 0.5 * max(0, multiples - 1)
    return min(coef, 2.0)


def appliquer_coefficient(quantite: Optional[int], coef: float) -> Optional[int]:
    """Applique le coefficient, sauf aux articles en exemplaire unique ; arrondi supérieur."""
    if quantite is None or quantite <= 1 or coef == 1.0:
        return quantite
    return int(math.ceil(quantite * coef - 1e-9))


def _ligne_applicable(l: LigneDotation, cfg: ConfigNavire) -> Optional[float]:
    """Retourne le multiplicateur de la ligne (0 = non applicable), selon les flags."""
    fc, fa = l.flags_categorie, l.flags_article
    mult = 1.0
    if "paludisme" in fc and not cfg.zone_paludisme:
        return 0.0
    if "aes" in fc and not cfg.aes:
        return 0.0
    if "equipage>10" in fc and cfg.effectif <= 10:
        return 0.0
    if "dae_reco" in fc and not cfg.dae:
        return 0.0
    if "pax_kits" in fc:
        n = min(3, cfg.nb_passagers // 100) if cfg.nb_passagers >= 100 else 0
        if n == 0:
            return 0.0
        mult *= n
    if "court_trajet" in fa and cfg.desserte_courte:
        return 0.0
    if "pax400" in fa and cfg.nb_passagers < 400:
        return 0.0
    if "peche_facultatif" in fa and cfg.navire_peche:
        return 0.0
    return mult


def _ajouter(exig: Dict[str, Exigence], l: LigneDotation, coef: float, mult: float,
             mode: str = "somme", note: str = "", obligatoire: bool = True) -> None:
    q_brute = l.quantite
    q = appliquer_coefficient(q_brute, coef)
    if q is not None and mult != 1.0:
        q = int(math.ceil(q * mult - 1e-9))
    e = exig.get(l.article.item_id)
    if e is None:
        e = Exigence(article=l.article, quantite=None, quantite_texte="", obligatoire=obligatoire,
                     categorie=l.categorie, liste=l.article.liste)
        exig[l.article.item_id] = e
    if q is None:
        if l.quantite_texte and l.quantite_texte not in e.quantite_texte:
            e.quantite_texte = (e.quantite_texte + " ; " if e.quantite_texte else "") + l.quantite_texte
    elif mode == "max":
        if e.quantite is None or q > e.quantite:
            e.quantite = q
    else:
        e.quantite = (e.quantite or 0) + q
    e.obligatoire = e.obligatoire or obligatoire
    e.origines.append(Origine(l.dotation, l.categorie, q_brute, coef * mult, q, note))


def calculer_exigences(ref: Referentiel, cfg: ConfigNavire,
                       supp: Optional[Dict[str, ExigenceSupplementaire]] = None,
                       perso: Optional[Dict[str, ArticlePerso]] = None) -> Dict[str, Exigence]:
    """Liste des articles exigés et de leurs quantités pour la configuration donnée."""
    exig: Dict[str, Exigence] = {}

    # 1. dotation de base
    coef = 1.0
    if cfg.dotation_base == "A":
        coef = cfg.coefficient_manuel if cfg.coefficient_manuel else coefficient_effectif(cfg.effectif)
    base = ref.dotation(cfg.dotation_base)
    for l in base.lignes:
        mult = _ligne_applicable(l, cfg)
        if mult:
            note = "recommandé" if "dae_reco" in l.flags_categorie or "aes" in l.flags_categorie else ""
            # une trousse (ex. trousse de premiers secours) est un ensemble au contenu fixe :
            # le coefficient d'effectif ne s'applique pas à sa composition
            _ajouter(exig, l, 1.0 if l.article.kit else coef, mult, note=note,
                     obligatoire=not ("dae_reco" in l.flags_categorie or "aes" in l.flags_categorie))

    # 2. complément passagers (sans coefficient d'effectif)
    if cfg.complement_passagers:
        comp = ref.dotation(cfg.complement_passagers)
        for l in comp.lignes:
            mult = _ligne_applicable(l, cfg)
            if mult:
                _ajouter(exig, l, 1.0, mult, note="complément passagers")

    # 3. sac médical d'urgence : ses articles peuvent être prélevés sur la dotation
    #    du bord quand ils y figurent -> on ne retient que le complément manquant.
    if cfg.sac_medical_urgence and "SMU" in ref.dotations:
        for l in ref.dotation("SMU").lignes:
            _ajouter(exig, l, 1.0, 1.0, mode="max", note="sac médical d'urgence (prélevable sur la dotation)")

    # 4. trousse plongée
    if cfg.plongee and "PLONGEE" in ref.dotations:
        for l in ref.dotation("PLONGEE").lignes:
            _ajouter(exig, l, 1.0, 1.0, note="trousse plongée")

    # 5. exigences supplémentaires de l'utilisateur
    for item_id, s in (supp or {}).items():
        art = ref.article(item_id)
        if art is None and perso and item_id in perso:
            art = article_depuis_perso(perso[item_id])
        if art is None:
            continue
        e = exig.get(item_id)
        if e is None:
            cat = art.categorie_perso if art.perso else CAT_AUTRE_DOTATION
            e = Exigence(article=art, quantite=0, categorie=cat, liste=art.liste)
            exig[item_id] = e
        e.quantite = (e.quantite or 0) + s.quantite
        e.origines.append(Origine("SUPP", s.motif or "supplément", s.quantite, 1.0, s.quantite, s.motif))
    return exig


# ---------------------------------------------------------------------- analyse
STATUT_OK = "OK"
STATUT_A_COMMANDER = "À commander"
STATUT_MANQUANT = "Manquant"
STATUT_PERIME = "Périmé en stock"
STATUT_NON_QUANTIFIE = "À vérifier (non quantifié)"
STATUT_HORS_DOTATION = "Suivi libre"   # article hors dotation sans quantité exigée


@dataclass
class EtatArticle:
    article: Article
    exigence: Optional[Exigence]
    lots: List[Lot]
    requis: Optional[int]
    stock_total: int
    stock_valide_aujourdhui: int
    stock_valide_horizon: int
    a_commander: int
    lots_perimes: List[Lot]
    lots_expirant: List[Lot]          # valides aujourd'hui mais périmés à l'horizon (+ marge)
    prochaine_peremption: Optional[date]
    statut: str

    @property
    def hors_dotation(self) -> bool:
        """Article qui ne relève pas de la dotation réglementaire du navire."""
        return not (self.exigence and self.exigence.reglementaire)

    @property
    def categorie(self) -> str:
        if not self.hors_dotation:
            return self.exigence.categorie
        if self.article.perso:
            return self.article.categorie_perso or CAT_HORS_DOTATION_DEFAUT
        return CAT_AUTRE_DOTATION

    @property
    def obligatoire(self) -> bool:
        return bool(self.exigence and self.exigence.obligatoire)


@dataclass
class Analyse:
    aujourdhui: date
    horizon: date
    marge_jours: int
    etats: List[EtatArticle]

    @property
    def a_commander(self) -> List[EtatArticle]:
        return [e for e in self.etats if e.a_commander > 0]

    @property
    def perimes(self) -> List[EtatArticle]:
        return [e for e in self.etats if e.lots_perimes]

    @property
    def expirant(self) -> List[EtatArticle]:
        return [e for e in self.etats if e.lots_expirant]

    @property
    def non_quantifies(self) -> List[EtatArticle]:
        return [e for e in self.etats if e.statut == STATUT_NON_QUANTIFIE]

    def resume(self) -> Dict[str, int]:
        return {
            "articles exigés": sum(1 for e in self.etats if e.exigence),
            "conformes": sum(1 for e in self.etats if e.exigence and e.statut == STATUT_OK),
            "à commander": len(self.a_commander),
            "manquants (stock nul)": sum(1 for e in self.etats if e.statut == STATUT_MANQUANT),
            "lots périmés": sum(len(e.lots_perimes) for e in self.etats),
            "lots expirant avant l'horizon": sum(len(e.lots_expirant) for e in self.etats),
            "à vérifier manuellement": len(self.non_quantifies),
        }


def analyser(exigences: Dict[str, Exigence], lots_par_article: Dict[str, List[Lot]],
             horizon: date, marge_jours: int = 0, aujourdhui: Optional[date] = None,
             articles_perso: Optional[Dict[str, ArticlePerso]] = None,
             ref: Optional[Referentiel] = None) -> Analyse:
    """Confronte exigences et stock ; ``horizon`` = date jusqu'à laquelle le bord doit être couvert."""
    auj = aujourdhui or date.today()
    limite = horizon + timedelta(days=max(0, marge_jours))
    etats: List[EtatArticle] = []
    perso = articles_perso or {}
    ids = list(exigences.keys())
    vus = set(ids)
    # stock d'articles hors dotation, puis articles hors dotation suivis sans stock ni quantité exigée
    for i in list(lots_par_article) + list(perso):
        if i not in vus:
            ids.append(i)
            vus.add(i)
    for item_id in ids:
        e = exigences.get(item_id)
        lots = list(lots_par_article.get(item_id, []))
        if e is not None:
            art = e.article
        else:
            art = (ref.article(item_id) if ref else None)
            if art is None and item_id in perso:
                art = article_depuis_perso(perso[item_id])
            if art is None:
                art = Article(item_id=item_id, type=TYPE_MAT, nom=item_id)
        total = sum(l.quantite for l in lots)
        perimes = [l for l in lots if l.est_perime(auj)]
        valides_auj = [l for l in lots if not l.est_perime(auj)]
        valides_h = [l for l in valides_auj if l.valide_a(limite)]
        expirant = [l for l in valides_auj if not l.valide_a(limite)]
        st_auj = sum(l.quantite for l in valides_auj)
        st_h = sum(l.quantite for l in valides_h)
        requis = e.quantite if e else None
        dates = sorted(l.peremption for l in lots if l.peremption)
        prochaine = dates[0] if dates else None
        if e is None:
            statut, a_cmd = STATUT_HORS_DOTATION, 0
        elif requis is None:
            statut, a_cmd = STATUT_NON_QUANTIFIE, 0
        else:
            a_cmd = max(0, requis - st_h)
            if a_cmd == 0:
                statut = STATUT_PERIME if perimes else STATUT_OK
            elif st_auj == 0:
                statut = STATUT_MANQUANT
            else:
                statut = STATUT_A_COMMANDER
        etats.append(EtatArticle(article=art, exigence=e, lots=lots, requis=requis, stock_total=total,
                                 stock_valide_aujourdhui=st_auj, stock_valide_horizon=st_h,
                                 a_commander=a_cmd, lots_perimes=perimes, lots_expirant=expirant,
                                 prochaine_peremption=prochaine, statut=statut))
    ordre = {TYPE_MED: 0, TYPE_MAT: 1}
    etats.sort(key=lambda x: (x.hors_dotation, ordre.get(x.article.type, 2), _cle_cat(x.categorie),
                              x.article.kit, x.article.nom.lower(), x.article.forme.lower()))
    return Analyse(aujourdhui=auj, horizon=horizon, marge_jours=marge_jours, etats=etats)


def _cle_cat(cat: str):
    """Trie « 1. Cardiologie » avant « 10. Dermatologie »."""
    num = cat.split(".")[0].strip()
    return (int(num), cat) if num.isdigit() else (999, cat)
