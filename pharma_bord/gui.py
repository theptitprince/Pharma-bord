# Pharma Bord, par ETDEL — https://github.com/theptitprince/Pharma-bord
# Copyright © 2026 ETDEL. Licence GPL-3.0-or-later avec conditions additionnelles
# (article 7) : voir les fichiers LICENSE et NOTICE.
"""Interface graphique (tkinter) de Pharma Bord."""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
import webbrowser
from datetime import date, datetime, timedelta
from pathlib import Path
from tkinter import BooleanVar, IntVar, StringVar, Tk, Toplevel, filedialog, messagebox, ttk
import tkinter as tk
from typing import Callable, Dict, List, Optional

from . import FICHIER_LICENCE, FICHIER_NOTICE, MENTION, URL_DEPOT, __version__, texte_a_propos
from .db import (ArticlePerso, BaseDonnees, ConfigNavire, ExigenceSupplementaire, Lot, DB_FILE)
from .export import (commande_csv, commande_html, inventaire_csv, inventaire_xlsx, lignes_commande,
                     mouvements_csv)
from .moteur import (Analyse, EtatArticle, LIBELLES_DOTATION, SOUS_CATEGORIES_HORS_DOTATION, STATUT_A_COMMANDER,
                     STATUT_HORS_DOTATION, STATUT_MANQUANT, STATUT_NON_QUANTIFIE, STATUT_OK, STATUT_PERIME, analyser,
                     article_depuis_perso, calculer_exigences, coefficient_effectif)
from .referentiel import (Article, ErreurReferentiel, TYPE_MAT, TYPE_MED, get_referentiel, make_id, normalize)

FMT = "%d/%m/%Y"
POLICE = "Segoe UI"

# ---------------------------------------------------------------------- palette
BANDEAU = "#17375e"
ACCENT = "#1f5f9f"
COULEURS = {
    STATUT_OK: "#e3f3e6",
    STATUT_A_COMMANDER: "#fff1c9",
    STATUT_MANQUANT: "#fadbdc",
    STATUT_PERIME: "#f7c9cc",
    STATUT_NON_QUANTIFIE: "#e6e8ea",
    STATUT_HORS_DOTATION: "#efe7fa",
}
SYMBOLES = {
    STATUT_OK: "✓", STATUT_A_COMMANDER: "▲", STATUT_MANQUANT: "✗", STATUT_PERIME: "⚠",
    STATUT_NON_QUANTIFIE: "?", STATUT_HORS_DOTATION: "•",
}
HORS_GROUPE = ("#dccdf2", "#4b2a7b")        # fond, texte de l'en-tête « Hors dotation »
HORS_CATEGORIE = "#ece3f8"
LOT_EXPIRE = "#fff6dc"
LOT_PERIME = "#f7c9cc"
CMD_AJOUT = ("#cfe3fa", "#0b4a8b")          # commandé à la main alors que non nécessaire
CMD_MODIF = ("#e6f0fc", "#1d3b5c")          # quantité modifiée à la main
CMD_RETIRE = ("#eeeeee", "#8a8a8a")         # retiré de la commande à la main

FILTRE_TOUS = "Tous"
FILTRE_NON_CONFORMES = "Non conformes"
FILTRE_HORS = "Hors dotation"


def parse_date(texte: str) -> Optional[date]:
    """Accepte JJ/MM/AAAA, MM/AAAA (fin de mois), AAAA-MM-JJ ; vide -> None."""
    t = texte.strip()
    if not t:
        return None
    for fmt_ in (FMT, "%Y-%m-%d", "%d-%m-%Y", "%d.%m.%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(t, fmt_).date()
        except ValueError:
            pass
    m = re.fullmatch(r"(\d{1,2})[/.-](\d{2}|\d{4})", t)
    if m:  # péremption exprimée en mois : dernier jour du mois
        mois, annee = int(m.group(1)), int(m.group(2))
        if annee < 100:
            annee += 2000
        if not 1 <= mois <= 12:
            raise ValueError(f"Mois invalide : « {texte} »")
        suivant = date(annee + (mois // 12), mois % 12 + 1, 1)
        return suivant - timedelta(days=1)
    raise ValueError(f"Date invalide : « {texte} » (attendu JJ/MM/AAAA ou MM/AAAA)")


def fmt(d: Optional[date]) -> str:
    return d.strftime(FMT) if d else ""


# ---------------------------------------------------------------------- éditeur de cellule
class EditeurCellule:
    """Champ de saisie posé sur une cellule d'un Treeview (édition directe dans le tableau).

    ``on_commit(texte) -> bool`` : True si la valeur est acceptée (l'éditeur se ferme),
    False pour la refuser (l'éditeur reste ouvert). ``on_suivant(sens)`` est appelé après
    Tab (+1) ou Maj+Tab (-1) pour enchaîner sur la cellule voisine.
    """

    def __init__(self, tv: ttk.Treeview, iid: str, col: str, valeur: str,
                 on_commit: Callable[[str], bool], on_suivant: Optional[Callable[[int], None]] = None,
                 on_fermer: Optional[Callable[[], None]] = None):
        self.tv, self.iid, self.col = tv, iid, col
        self.on_commit, self.on_suivant, self.on_fermer = on_commit, on_suivant, on_fermer
        self._ferme = False
        self._occupe = False
        tv.see(iid)
        tv.update_idletasks()
        bbox = tv.bbox(iid, col)
        if not bbox:
            raise RuntimeError("cellule non visible")
        x, y, w, h = bbox
        self.entry = ttk.Entry(tv, font=(POLICE, 10))
        self.entry.place(x=x, y=y, width=max(w, 70), height=h + 2)
        self.entry.insert(0, valeur)
        self.entry.select_range(0, "end")
        self.entry.focus_set()
        self.entry.bind("<Return>", lambda e: self._valider(0))
        self.entry.bind("<KP_Enter>", lambda e: self._valider(0))
        self.entry.bind("<Tab>", lambda e: self._valider(1) or "break")
        self.entry.bind("<Shift-Tab>", lambda e: self._valider(-1) or "break")
        self.entry.bind("<ISO_Left_Tab>", lambda e: self._valider(-1) or "break")
        self.entry.bind("<Escape>", lambda e: self.fermer())
        self.entry.bind("<FocusOut>", lambda e: self._valider(0))

    def _valider(self, sens: int = 0):
        if self._ferme or self._occupe:
            return
        self._occupe = True
        try:
            ok = self.on_commit(self.entry.get())
        finally:
            self._occupe = False
        if ok:
            self.fermer()
            if sens and self.on_suivant:
                self.on_suivant(sens)
        else:
            try:
                self.entry.focus_set()
            except tk.TclError:
                pass

    def fermer(self):
        if self._ferme:
            return
        self._ferme = True
        try:
            self.entry.destroy()
        except tk.TclError:
            pass
        if self.on_fermer:
            self.on_fermer()


# ---------------------------------------------------------------------- info-bulle
class InfoBulle:
    """Info-bulle au survol des lignes d'un Treeview ; ``texte_pour(iid)`` fournit le texte (ou None)."""

    def __init__(self, tv: ttk.Treeview, texte_pour: Callable[[str], Optional[str]], delai: int = 450):
        self.tv, self.texte_pour, self.delai = tv, texte_pour, delai
        self._iid: Optional[str] = None
        self._after = None
        self._fen: Optional[tk.Toplevel] = None
        tv.bind("<Motion>", self._bouge, add="+")
        for ev in ("<Leave>", "<ButtonPress>", "<MouseWheel>", "<KeyPress>"):
            tv.bind(ev, self._cacher, add="+")

    def _bouge(self, event):
        iid = self.tv.identify_row(event.y)
        if iid != self._iid:
            self._cacher(reinit=False)
            self._iid = iid or None
            if iid:
                self._after = self.tv.after(self.delai, self._montrer)

    def _montrer(self):
        self._after = None
        if not self._iid or not self.tv.exists(self._iid):
            return
        texte = self.texte_pour(self._iid)
        if not texte:
            return
        x, y = self.tv.winfo_pointerxy()
        f = tk.Toplevel(self.tv)
        f.wm_overrideredirect(True)
        try:
            f.attributes("-topmost", True)
        except tk.TclError:
            pass
        fixe(tk.Label(f, text=texte, justify="left", relief="solid", bd=1, font=(POLICE, 9), padx=9, pady=6,
                      wraplength=480), bg="#fffdf3", fg="#222").pack()
        f.update_idletasks()
        largeur = f.winfo_reqwidth()
        x = min(x + 16, self.tv.winfo_screenwidth() - largeur - 8)
        f.wm_geometry(f"+{x}+{y + 16}")
        self._fen = f

    def _cacher(self, event=None, reinit: bool = True):
        if self._after:
            self.tv.after_cancel(self._after)
            self._after = None
        if self._fen:
            self._fen.destroy()
            self._fen = None
        if reinit:
            self._iid = None


def fixe(w, **opts):
    """Applique des couleurs explicites à un widget tk et les mémorise : le thème sv_ttk repeint tous
    les widgets classiques (tk_setPalette) à chaque changement de style, elles sont alors réappliquées."""
    w.configure(**opts)
    w._couleurs_fixes = opts
    return w


def reappliquer_couleurs(w) -> None:
    for enfant in w.winfo_children():
        opts = getattr(enfant, "_couleurs_fixes", None)
        if opts:
            try:
                enfant.configure(**opts)
            except tk.TclError:
                pass
        reappliquer_couleurs(enfant)


def legende(parent, items) -> tk.Frame:
    """Bandeau de pastilles de couleur : items = [(fond, texte, couleur_texte), ...]."""
    f = ttk.Frame(parent)
    ttk.Label(f, text="Légende :", font=(POLICE, 9)).pack(side="left", padx=(0, 6))
    for fond, texte, fg in items:
        fixe(tk.Label(f, text=texte, font=(POLICE, 9), padx=7, pady=2, relief="flat", bd=0),
             bg=fond, fg=fg or "#222").pack(side="left", padx=(0, 5))
    return f


class Application(Tk):
    # Colonnes de l'inventaire. Les cinq colonnes d'une boîte sont contiguës, dans l'ordre de saisie.
    COLONNES = ("forme", "liste", "requis", "quantite", "peremption", "lot", "specialite", "emplacement",
                "valide", "commander", "statut")
    COLS_BOITE = ("quantite", "peremption", "lot", "specialite", "emplacement")
    CHAMP_BOITE = {"quantite": "quantite", "peremption": "peremption", "lot": "numero_lot",
                   "specialite": "specialite", "emplacement": "emplacement"}
    INVITES = {"quantite": "qté ?", "peremption": "JJ/MM/AAAA", "lot": "n° de lot", "specialite": "spécialité",
               "emplacement": "emplacement"}

    def __init__(self, chemin_db: Path = DB_FILE):
        super().__init__()
        self.title(f"Pharma Bord – dotation médicale du navire (v{__version__})")
        self.geometry("1500x880")
        self.minsize(1100, 680)
        try:
            self.ref = get_referentiel()
        except ErreurReferentiel as exc:
            messagebox.showerror("Référentiel", str(exc))
            self.destroy()
            raise SystemExit(1)
        self.db = BaseDonnees(chemin_db)
        self.cfg = self.db.charger_config()
        self.analyse: Optional[Analyse] = None
        self.ajustements: Dict[str, int] = self._charger_ajustements()
        self.filtre = StringVar()
        self.filtre_statut = StringVar(value=FILTRE_TOUS)
        self.horizon_var = StringVar()
        self.delai_var = IntVar(value=self.cfg.delai_jours)
        self.marge_var = IntVar(value=self.cfg.marge_jours)
        self._editeur: Optional[EditeurCellule] = None
        self._brouillon: Dict[str, Dict[str, str]] = {}   # saisie en cours sur les lignes « + Ajouter »
        self._iid_item: Dict[str, str] = {}
        self._iid_apres_commit: Dict[str, str] = {}
        self._bulles_cmd: Dict[str, str] = {}
        self._maj_horizon_depuis_delai()
        self._style()
        self._construire()
        self.recalculer()
        if self.ref.avertissements:
            messagebox.showwarning("Référentiel", "\n".join(self.ref.avertissements[:20]))
        self.protocol("WM_DELETE_WINDOW", self._quitter)

    # ------------------------------------------------------------------ apparence
    def _style(self):
        st = ttk.Style(self)
        self.theme_moderne = False
        try:
            import sv_ttk  # thème « Sun Valley » (aspect Windows 11)
            sv_ttk.set_theme("light")
            self.theme_moderne = True
            # Sous Tk 9, le thème ne reçoit plus l'état ouvert / feuille des lignes et dessine une flèche
            # partout : on retire son indicateur et on affiche nos propres marqueurs ▸ / ▾.
            sans_indicateur = [("Treeitem.padding", {"sticky": "nswe", "children": [
                ("Treeitem.image", {"side": "left", "sticky": ""}), ("Treeitem.text", {"sticky": "nswe"})]})]
            st.layout("Item", sans_indicateur)
            st.layout("Treeview.Item", sans_indicateur)
            global MARQUEURS
            MARQUEURS = True
            # Sous Tk 9, la configuration de base du thème (fond clair, police, couleurs de sélection),
            # normalement posée sur <<ThemeChanged>>, n'est jamais appliquée : les widgets créés après le
            # démarrage (dialogues, onglets) sortaient avec un fond gris. On la pose donc nous-mêmes.
            c = {k: self.tk.eval(f"set ttk::theme::sv_light::colors({k})")
                 for k in ("-bg", "-fg", "-selbg", "-selfg", "-disfg")}
            st.configure(".", background=c["-bg"], foreground=c["-fg"], troughcolor=c["-bg"],
                         focuscolor=c["-selbg"], selectbackground=c["-selbg"], selectforeground=c["-selfg"],
                         insertwidth=1, insertcolor=c["-fg"], fieldbackground=c["-bg"],
                         font="SunValleyBodyFont", borderwidth=0, relief="flat")
            st.map(".", foreground=[("disabled", c["-disfg"])])
            self.configure(bg=c["-bg"])
        except Exception:
            try:
                st.theme_use("vista" if sys.platform.startswith("win") else "clam")
            except tk.TclError:
                pass
        st.configure("Treeview", rowheight=27, font=(POLICE, 10))
        st.configure("Treeview.Heading", font=(POLICE, 10, "bold"))
        st.configure("TNotebook.Tab", font=(POLICE, 10), padding=(16, 7))
        st.configure("TLabelframe.Label", font=(POLICE, 10, "bold"))
        st.configure("Accent.TButton", font=(POLICE, 10, "bold"))
        # Tk ≥ 8.6.9 : sans cette correction, les couleurs des tags Treeview ne s'affichent pas.
        def fixed_map(option):
            return [e for e in st.map("Treeview", query_opt=option) if e[:2] != ("!disabled", "!selected")]
        st.map("Treeview", foreground=fixed_map("foreground"), background=fixed_map("background"))
        # si le thème repeint les widgets classiques (tk_setPalette), on remet nos couleurs explicites ensuite
        self.bind("<<ThemeChanged>>", lambda e: self.after_idle(lambda: reappliquer_couleurs(self)), add="+")
        try:
            self.state("zoomed")
        except tk.TclError:
            pass

    def _construire(self):
        self._construire_entete()
        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=12, pady=(8, 4))
        self.onglet_navire = ttk.Frame(self.nb, padding=8)
        self.onglet_inventaire = ttk.Frame(self.nb, padding=8)
        self.onglet_commande = ttk.Frame(self.nb, padding=8)
        self.onglet_historique = ttk.Frame(self.nb, padding=8)
        self.onglet_referentiel = ttk.Frame(self.nb, padding=8)
        self.nb.add(self.onglet_navire, text="Navire & dotation")
        self.nb.add(self.onglet_inventaire, text="Inventaire")
        self.nb.add(self.onglet_commande, text="Commande escale")
        self.nb.add(self.onglet_historique, text="Historique")
        self.nb.add(self.onglet_referentiel, text="Réglementation")
        self._construire_navire()
        self._construire_inventaire()
        self._construire_commande()
        self._construire_historique()
        self._construire_referentiel()
        self.barre = ttk.Label(self, text="", anchor="w", font=(POLICE, 9))
        self.barre.pack(fill="x", padx=14, pady=(0, 6))

    def _construire_entete(self):
        ent = fixe(tk.Frame(self, padx=18, pady=12), bg=BANDEAU)
        ent.pack(fill="x")
        gauche = fixe(tk.Frame(ent), bg=BANDEAU)
        gauche.pack(side="left", fill="y")
        fixe(tk.Label(gauche, text="⚓  Pharma Bord", font=(POLICE, 19, "bold")), bg=BANDEAU, fg="white").pack(anchor="w")
        self.lbl_entete = fixe(tk.Label(gauche, text="", font=(POLICE, 10), justify="left"), bg=BANDEAU, fg="#c8d6e8")
        self.lbl_entete.pack(anchor="w", pady=(2, 0))
        # mention d'auteur exigée par les conditions additionnelles de la licence (NOTICE, article 7 b), suivie du
        # bouton « À propos… » : à gauche du bandeau, ils restent visibles même si la fenêtre est étroite
        ligne = fixe(tk.Frame(gauche), bg=BANDEAU)
        ligne.pack(anchor="w", pady=(4, 0))
        fixe(tk.Label(ligne, text=MENTION, font=(POLICE, 9)), bg=BANDEAU, fg="#9fb4d0").pack(side="left")
        self.btn_a_propos = fixe(tk.Button(ligne, text="À propos…", font=(POLICE, 9), relief="flat", bd=0,
                                           padx=10, pady=1, cursor="hand2", command=self.dialogue_a_propos),
                                 bg="#24507f", fg="white", activebackground="#2f639b", activeforeground="white")
        self.btn_a_propos.pack(side="left", padx=(12, 0))
        self.bind("<F1>", lambda e: self.dialogue_a_propos())
        self.tuiles: Dict[str, tk.Label] = {}
        droite = fixe(tk.Frame(ent), bg=BANDEAU)
        droite.pack(side="right")
        for cle, lib, coul in (("exiges", "articles exigés", ACCENT), ("conformes", "conformes", "#2e7d32"),
                               ("commander", "à commander", "#b26a00"), ("perimes", "boîtes périmées", "#c62828"),
                               ("expirant", "boîtes à remplacer", "#b26a00")):
            carte = fixe(tk.Frame(droite, padx=16, pady=6), bg="white")
            carte.pack(side="left", padx=5)
            v = fixe(tk.Label(carte, text="–", font=(POLICE, 20, "bold")), bg="white", fg=coul)
            v.pack()
            fixe(tk.Label(carte, text=lib, font=(POLICE, 9)), bg="white", fg="#666").pack()
            self.tuiles[cle] = v

    # ---------------- onglet navire
    def _construire_navire(self):
        f = self.onglet_navire
        cfg = self.cfg
        self.v = {
            "nom": StringVar(value=cfg.nom), "immatriculation": StringVar(value=cfg.immatriculation),
            "armement": StringVar(value=cfg.armement), "adresse_armement": StringVar(value=cfg.adresse_armement),
            "port_attache": StringVar(value=cfg.port_attache),
            "capitaine": StringVar(value=cfg.capitaine), "responsable_soins": StringVar(value=cfg.responsable_soins),
            "fonction_responsable": StringVar(value=cfg.fonction_responsable),
            "pharmacien": StringVar(value=cfg.pharmacien), "adresse_pharmacien": StringVar(value=cfg.adresse_pharmacien),
            "effectif": IntVar(value=cfg.effectif), "nb_passagers": IntVar(value=cfg.nb_passagers),
            "zone_paludisme": BooleanVar(value=cfg.zone_paludisme), "aes": BooleanVar(value=cfg.aes),
            "dae": BooleanVar(value=cfg.dae), "sac_medical_urgence": BooleanVar(value=cfg.sac_medical_urgence),
            "plongee": BooleanVar(value=cfg.plongee), "navire_peche": BooleanVar(value=cfg.navire_peche),
            "desserte_courte": BooleanVar(value=cfg.desserte_courte),
            "marchandises_dangereuses": BooleanVar(value=cfg.marchandises_dangereuses),
            "coefficient_manuel": StringVar(value="" if cfg.coefficient_manuel is None else str(cfg.coefficient_manuel)),
        }
        gauche = ttk.LabelFrame(f, text="Identification du navire (reprise sur le bon de commande)", padding=12)
        gauche.grid(row=0, column=0, sticky="nsew", padx=(0, 10), pady=4)
        champs = [("Nom du navire", "nom"), ("Immatriculation", "immatriculation"),
                  ("Armement / armateur", "armement"), ("Adresse de l'armement", "adresse_armement"),
                  ("Port d'attache", "port_attache"), ("Capitaine", "capitaine"),
                  ("Responsable des soins", "responsable_soins"), ("Fonction du responsable", "fonction_responsable"),
                  ("Pharmacie habituelle", "pharmacien"), ("Adresse de la pharmacie", "adresse_pharmacien")]
        for i, (lib, cle) in enumerate(champs):
            ttk.Label(gauche, text=lib).grid(row=i, column=0, sticky="w", pady=3, padx=(0, 10))
            ttk.Entry(gauche, textvariable=self.v[cle], width=38).grid(row=i, column=1, sticky="ew", pady=3)
        gauche.columnconfigure(1, weight=1)

        droite = ttk.LabelFrame(f, text="Zone de navigation et dotation réglementaire", padding=12)
        droite.grid(row=0, column=1, sticky="nsew", pady=4)
        ttk.Label(droite, text="Dotation de base").grid(row=0, column=0, sticky="w", pady=3, padx=(0, 10))
        codes_base = [c for c in ("A", "B", "BR", "C", "CR", "CAT5") if c in self.ref.dotations]
        self.cb_base = ttk.Combobox(droite, state="readonly", width=66,
                                    values=[LIBELLES_DOTATION.get(c, c) for c in codes_base])
        self.cb_base.grid(row=0, column=1, sticky="ew", pady=3)
        self._codes_base = codes_base
        if cfg.dotation_base in codes_base:
            self.cb_base.current(codes_base.index(cfg.dotation_base))
        ttk.Label(droite, text="Complément passagers").grid(row=1, column=0, sticky="w", pady=3, padx=(0, 10))
        codes_comp = [""] + [c for c in ("P1", "P2", "P3", "P4") if c in self.ref.dotations]
        self.cb_comp = ttk.Combobox(droite, state="readonly", width=66,
                                    values=[LIBELLES_DOTATION.get(c, c) for c in codes_comp])
        self.cb_comp.grid(row=1, column=1, sticky="ew", pady=3)
        self._codes_comp = codes_comp
        self.cb_comp.current(codes_comp.index(cfg.complement_passagers) if cfg.complement_passagers in codes_comp else 0)
        eff = ttk.Frame(droite)
        eff.grid(row=2, column=0, columnspan=2, sticky="w", pady=6)
        ttk.Label(eff, text="Effectif (marins)").pack(side="left")
        ttk.Spinbox(eff, from_=1, to=500, textvariable=self.v["effectif"], width=6).pack(side="left", padx=(6, 18))
        ttk.Label(eff, text="Passagers").pack(side="left")
        ttk.Spinbox(eff, from_=0, to=10000, textvariable=self.v["nb_passagers"], width=7).pack(side="left", padx=(6, 18))
        ttk.Label(eff, text="Coefficient manuel (dotation A, vide = automatique)").pack(side="left")
        ttk.Entry(eff, textvariable=self.v["coefficient_manuel"], width=6).pack(side="left", padx=6)
        self.lbl_coef = ttk.Label(droite, wraplength=640, justify="left", font=(POLICE, 9))
        self.lbl_coef.grid(row=3, column=0, columnspan=2, sticky="w", pady=(0, 8))

        opts = ttk.LabelFrame(droite, text="Options", padding=8)
        opts.grid(row=4, column=0, columnspan=2, sticky="ew")
        options = [
            ("zone_paludisme", "Navigation en zone à risque de paludisme (antipaludéens obligatoires)"),
            ("aes", "Accidents d'exposition au sang : kit recommandé après évaluation du risque"),
            ("dae", "Défibrillateur automatisé externe (recommandé en dotation B)"),
            ("sac_medical_urgence", "Sac médical d'urgence (navire à passagers sans médecin, annexe 217-3.A.4)"),
            ("plongee", "Navire support de plongeurs professionnels (trousse de secours plongée)"),
            ("navire_peche", "Navire de pêche (civière treuillable facultative en dotation B)"),
            ("desserte_courte", "Dessertes régulières de très courte durée < 30 min (P4 : articles notés (9) non exigés)"),
            ("marchandises_dangereuses", "Transport de marchandises dangereuses (antidotes du GSMU à suivre en hors dotation)"),
        ]
        for i, (cle, lib) in enumerate(options):
            ttk.Checkbutton(opts, text=lib, variable=self.v[cle]).grid(row=i, column=0, sticky="w", pady=2)

        bas = ttk.Frame(f)
        bas.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(10, 4))
        ttk.Button(bas, text="Enregistrer et recalculer la dotation exigée", style="Accent.TButton",
                   command=self.sauver_config).pack(side="left")
        ttk.Label(bas, text=f"Base de données : {self.db.chemin}", font=(POLICE, 9)).pack(side="left", padx=20)
        self.lbl_resume = ttk.Label(f, text="", justify="left", font=(POLICE, 10))
        self.lbl_resume.grid(row=2, column=0, columnspan=2, sticky="nw", pady=6)
        f.columnconfigure(0, weight=1)
        f.columnconfigure(1, weight=2)
        f.rowconfigure(2, weight=1)
        for cle in ("effectif", "coefficient_manuel"):
            self.v[cle].trace_add("write", lambda *_: self._maj_label_coef())
        self.cb_base.bind("<<ComboboxSelected>>", lambda *_: self._maj_label_coef())
        self._maj_label_coef()

    def _maj_label_coef(self):
        try:
            eff = int(self.v["effectif"].get())
        except (tk.TclError, ValueError):
            eff = 0
        base = self._codes_base[self.cb_base.current()] if self.cb_base.current() >= 0 else ""
        if base != "A":
            self.lbl_coef.config(text="Dotations B, C, 5e catégorie et compléments : quantités fixes, sans référence à l'effectif.")
            return
        manuel = self.v["coefficient_manuel"].get().strip().replace(",", ".")
        try:
            coef = float(manuel) if manuel else coefficient_effectif(eff)
        except ValueError:
            coef = coefficient_effectif(eff)
        self.lbl_coef.config(text=(
            f"Dotation A : quantités de référence pour 25 marins, coefficient appliqué = {coef:g} "
            f"(+50 % par multiple entier de 25 marins, max 2 dotations ; -50 % si effectif < 13 ; "
            f"arrondi supérieur ; articles en exemplaire unique inchangés)."))

    def sauver_config(self):
        cfg = self.cfg
        for cle in ("nom", "immatriculation", "armement", "adresse_armement", "port_attache", "capitaine",
                    "responsable_soins", "fonction_responsable", "pharmacien", "adresse_pharmacien"):
            setattr(cfg, cle, self.v[cle].get().strip())
        try:
            cfg.effectif = int(self.v["effectif"].get())
            cfg.nb_passagers = int(self.v["nb_passagers"].get())
        except (tk.TclError, ValueError):
            messagebox.showerror("Saisie", "Effectif et nombre de passagers doivent être des nombres entiers.")
            return
        for cle in ("zone_paludisme", "aes", "dae", "sac_medical_urgence", "plongee", "navire_peche",
                    "desserte_courte", "marchandises_dangereuses"):
            setattr(cfg, cle, bool(self.v[cle].get()))
        manuel = self.v["coefficient_manuel"].get().strip().replace(",", ".")
        try:
            cfg.coefficient_manuel = float(manuel) if manuel else None
        except ValueError:
            messagebox.showerror("Saisie", "Le coefficient manuel doit être un nombre (ex. 1.5).")
            return
        cfg.dotation_base = self._codes_base[self.cb_base.current()]
        cfg.complement_passagers = self._codes_comp[self.cb_comp.current()]
        try:
            cfg.delai_jours = int(self.delai_var.get())
            cfg.marge_jours = int(self.marge_var.get())
        except tk.TclError:
            pass
        self.db.sauver_config(cfg)
        self.recalculer()
        self.barre.config(text="Configuration enregistrée.")

    # ---------------- onglet inventaire
    def _construire_inventaire(self):
        f = self.onglet_inventaire
        haut = ttk.Frame(f)
        haut.pack(fill="x", pady=(0, 6))
        ttk.Label(haut, text="Rechercher").pack(side="left")
        e = ttk.Entry(haut, textvariable=self.filtre, width=28)
        e.pack(side="left", padx=6)
        e.bind("<KeyRelease>", lambda *_: self.rafraichir_inventaire())
        ttk.Label(haut, text="Afficher").pack(side="left", padx=(12, 4))
        cb = ttk.Combobox(haut, textvariable=self.filtre_statut, state="readonly", width=24,
                          values=[FILTRE_TOUS, FILTRE_NON_CONFORMES, STATUT_OK, STATUT_A_COMMANDER, STATUT_MANQUANT,
                                  STATUT_PERIME, STATUT_NON_QUANTIFIE, FILTRE_HORS])
        cb.pack(side="left")
        cb.bind("<<ComboboxSelected>>", lambda *_: self.rafraichir_inventaire())
        ttk.Button(haut, text="Déplier les catégories", command=lambda: deplier_tout(self.tv, "categories")).pack(side="left", padx=(16, 2))
        ttk.Button(haut, text="Tout déplier (boîtes)", command=lambda: deplier_tout(self.tv, "tout")).pack(side="left", padx=2)
        ttk.Button(haut, text="Tout replier", command=lambda: deplier_tout(self.tv, "rien")).pack(side="left", padx=2)
        ttk.Button(haut, text="Nouvel article hors dotation…", style="Accent.TButton",
                   command=self.dialogue_article_hors_dotation).pack(side="right", padx=2)

        actions = ttk.Frame(f)
        actions.pack(fill="x", pady=(0, 6))
        ttk.Label(actions, text="Boîte sélectionnée :").pack(side="left")
        ttk.Button(actions, text="Sortie (distribution…)", command=lambda: self.dialogue_sortie()).pack(side="left", padx=2)
        ttk.Button(actions, text="Débarquer (périmé)…",
                   command=lambda: self.dialogue_sortie("Débarquement pour péremption")).pack(side="left", padx=2)
        ttk.Button(actions, text="Retirer", command=self.supprimer_lot_selectionne).pack(side="left", padx=2)
        ttk.Button(actions, text="Détails…", command=self.dialogue_modifier_lot).pack(side="left", padx=2)
        ttk.Label(actions, font=(POLICE, 9), text=(
            "   Un clic sur une case d'une boîte ou de la ligne « + Ajouter » ouvre la saisie ; "
            "Tab passe à la case suivante, Entrée valide. Clic droit : autres actions.")
        ).pack(side="left")

        cadre = ttk.Frame(f)
        cadre.pack(fill="both", expand=True)
        self.tv = ttk.Treeview(cadre, columns=self.COLONNES, show="tree headings", selectmode="browse")
        self.tv.heading("#0", text="Catégorie / article / boîte", command=lambda: self._trier("article"))
        self.tv.column("#0", width=300, minwidth=200, anchor="w")
        entetes = {"forme": ("Forme / présentation", 210), "liste": ("Liste", 70), "requis": ("Qté régl.", 70),
                   "quantite": ("Quantité", 72), "peremption": ("Péremption", 96), "lot": ("N° de lot", 92),
                   "specialite": ("Spécialité / marque", 140), "emplacement": ("Emplacement", 110),
                   "valide": ("Valide horizon", 92), "commander": ("À cmd.", 60), "statut": ("Statut", 210)}
        centre = ("liste", "requis", "quantite", "peremption", "valide", "commander")
        for c in self.COLONNES:
            lib, w = entetes[c]
            self.tv.heading(c, text=lib, command=lambda c=c: self._trier(c))
            self.tv.column(c, width=w, minwidth=40, anchor="center" if c in centre else "w")
        configurer_tags(self.tv)
        sb = ttk.Scrollbar(cadre, orient="vertical", command=self.tv.yview)
        self.tv.configure(yscrollcommand=sb.set)
        self.tv.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.tv.bind("<ButtonRelease-1>", self._clic_inventaire)
        self.tv.bind("<Return>", self._entree_inventaire)
        self.tv.bind("<F2>", self._entree_inventaire)
        self.tv.bind("<Delete>", lambda e: self.supprimer_lot_selectionne())
        self.tv.bind("<Button-3>", self._menu_inventaire)
        self.tv.bind("<MouseWheel>", lambda e: self._valider_editeur(), add="+")
        self.tv.bind("<Configure>", lambda e: self._valider_editeur(), add="+")
        InfoBulle(self.tv, self._bulle_inventaire)
        activer_depliage(self.tv)
        legende(f, [(COULEURS[STATUT_OK], "✓ conforme", None), (COULEURS[STATUT_A_COMMANDER], "▲ à commander", None),
                    (COULEURS[STATUT_MANQUANT], "✗ manquant", None), (COULEURS[STATUT_PERIME], "⚠ périmé en stock", None),
                    (COULEURS[STATUT_NON_QUANTIFIE], "? quantité à vérifier", None),
                    (HORS_GROUPE[0], "hors dotation", HORS_GROUPE[1]),
                    (LOT_EXPIRE, "boîte expirant avant l'horizon", None), (LOT_PERIME, "boîte périmée", None),
                    ("#ffffff", "texte rouge : stupéfiant", "#b00020")]).pack(fill="x", pady=(6, 0))
        self._tri = ("article", True)

    # --- saisie directe dans le tableau
    def _nom_colonne(self, ident: str) -> str:
        """'#3' -> nom de colonne ; '#0' -> '#0'."""
        if ident == "#0" or not ident:
            return "#0"
        return self.tv["columns"][int(ident[1:]) - 1]

    def _clic_inventaire(self, event):
        if self.tv.identify_region(event.x, event.y) not in ("cell", "tree"):
            return
        iid = self.tv.identify_row(event.y)
        if not iid or not self.tv.exists(iid):
            return
        col = self._nom_colonne(self.tv.identify_column(event.x))
        if iid.startswith("new:"):
            self._editer(iid, col if col in self.COLS_BOITE else "quantite")
        elif iid.startswith("lot:") and col in self.COLS_BOITE:
            self._editer(iid, col)

    def _entree_inventaire(self, event=None):
        iid = self.tv.focus()
        if iid.startswith(("lot:", "new:")):
            self._editer(iid, "quantite")
            return "break"
        if iid and self.tv.exists(iid) and self.tv.get_children(iid):
            self.tv.item(iid, open=not self.tv.item(iid, "open"))
            return "break"

    def _fermer_editeur(self):
        if self._editeur:
            ed, self._editeur = self._editeur, None
            ed.fermer()

    def _valider_editeur(self):
        if self._editeur:
            self._editeur._valider(0)

    def _valeur_boite(self, iid: str, col: str) -> str:
        champ = self.CHAMP_BOITE[col]
        if iid.startswith("new:"):
            return self._brouillon.get(self._iid_item.get(iid, ""), {}).get(champ, "")
        lot = self.db.lot(int(iid[4:]))
        if lot is None:
            return ""
        if champ == "peremption":
            return fmt(lot.peremption)
        return str(getattr(lot, champ))

    def _editer(self, iid: str, col: str):
        self._fermer_editeur()
        if not self.tv.exists(iid):
            return
        self.tv.selection_set(iid)
        self.tv.focus(iid)
        try:
            self._editeur = EditeurCellule(
                self.tv, iid, col, self._valeur_boite(iid, col),
                on_commit=lambda texte: self._valider_cellule(iid, col, texte),
                on_suivant=lambda sens: self._editer_voisine(iid, col, sens),
                on_fermer=lambda: setattr(self, "_editeur", None))
        except RuntimeError:
            pass

    def _editer_voisine(self, iid: str, col: str, sens: int):
        ordre = list(self.COLS_BOITE)
        i = ordre.index(col) + sens
        if 0 <= i < len(ordre):
            cible = self._iid_apres_commit.get(iid, iid)
            self.after(40, lambda: self.tv.exists(cible) and self._editer(cible, ordre[i]))

    def _valider_cellule(self, iid: str, col: str, texte: str) -> bool:
        champ = self.CHAMP_BOITE[col]
        texte = texte.strip()
        try:
            if champ == "quantite":
                valeur = int(texte) if texte else 0
                if valeur < 0:
                    raise ValueError("La quantité doit être positive.")
            elif champ == "peremption":
                valeur = parse_date(texte)
                texte = fmt(valeur)
            else:
                valeur = texte
        except ValueError as exc:
            messagebox.showerror("Saisie", str(exc) or "Valeur invalide.", parent=self)
            return False
        self._iid_apres_commit = {}
        if iid.startswith("lot:"):
            lot = self.db.lot(int(iid[4:]))
            if lot is None:
                return True
            if getattr(lot, champ) == valeur:
                return True
            if champ == "quantite" and valeur == 0:
                if not messagebox.askyesno("Boîte vide", "Quantité 0 : retirer cette boîte de l'inventaire ?", parent=self):
                    return False
                self.db.supprimer_lot(lot.id, motif="Saisie inventaire")
                self.after(10, lambda: self.recalculer(selection=lot.item_id))
                return True
            setattr(lot, champ, valeur)
            self.db.modifier_lot(lot, motif="Saisie inventaire")
            self.after(10, lambda: self.recalculer(selection=iid))
            return True
        # ligne « + Ajouter » : brouillon jusqu'à ce qu'une quantité soit saisie
        item_id = self._iid_item[iid]
        b = self._brouillon.setdefault(item_id, {})
        b[champ] = texte
        if champ == "quantite" and valeur > 0:
            try:
                per = parse_date(b.get("peremption", ""))
            except ValueError:
                per = None
            lot = Lot(id=None, item_id=item_id, quantite=valeur, peremption=per,
                      numero_lot=b.get("numero_lot", ""), specialite=b.get("specialite", ""),
                      emplacement=b.get("emplacement", ""), date_entree=date.today())
            lot = self.db.ajouter_lot(lot, motif="Saisie inventaire")
            self._brouillon.pop(item_id, None)
            nouveau = f"lot:{lot.id}"
            self._iid_apres_commit = {iid: nouveau}
            self.recalculer(selection=nouveau)
            return True
        self.tv.set(iid, col, texte or self.INVITES[col])
        return True

    def _trier(self, col):
        asc = not self._tri[1] if self._tri[0] == col else True
        self._tri = (col, asc)
        self.rafraichir_inventaire()

    def _etats_filtres(self) -> List[EtatArticle]:
        if not self.analyse:
            return []
        n = normalize(self.filtre.get())
        st = self.filtre_statut.get()
        res = []
        for e in self.analyse.etats:
            if st == FILTRE_NON_CONFORMES and e.statut in (STATUT_OK, STATUT_HORS_DOTATION):
                continue
            if st == FILTRE_HORS and not e.hors_dotation:
                continue
            if st not in (FILTRE_TOUS, FILTRE_NON_CONFORMES, FILTRE_HORS) and e.statut != st:
                continue
            if n and n not in normalize(e.article.libelle + " " + e.categorie + " " + e.article.voie
                                        + " " + " ".join(l.specialite + " " + l.numero_lot for l in e.lots)):
                continue
            res.append(e)
        col, asc = self._tri
        par_nom = lambda e: (e.article.kit, e.article.nom.lower(), e.article.forme.lower())
        cle = {
            "article": par_nom, "lot": par_nom, "specialite": par_nom, "emplacement": par_nom,
            "forme": lambda e: e.article.forme.lower(), "liste": lambda e: e.article.liste,
            "requis": lambda e: e.requis or 0, "quantite": lambda e: e.stock_total,
            "valide": lambda e: e.stock_valide_horizon, "commander": lambda e: e.a_commander,
            "peremption": lambda e: e.prochaine_peremption or date.max, "statut": lambda e: e.statut,
        }[col]
        res.sort(key=cle, reverse=not asc)   # tri stable : appliqué à l'intérieur de chaque catégorie
        return res

    def _enfants_lots(self, e: EtatArticle) -> List["EnfantArbre"]:
        """Lignes « boîte » d'un article + la ligne d'ajout (avec son brouillon éventuel)."""
        auj = self.analyse.aujourdhui
        limite = self.analyse.horizon + timedelta(days=self.analyse.marge_jours)
        enfants = []
        for l in e.lots:
            if l.est_perime(auj):
                etat, tag = "⚠ périmée – à détruire", "lot_perime"
            elif not l.valide_a(limite):
                etat, tag = f"▲ expire avant le {fmt(limite)}", "lot_expire"
            elif l.peremption is None:
                etat, tag = "sans péremption", "lot"
            else:
                etat, tag = "✓ valide", "lot"
            iid = f"lot:{l.id}"
            self._iid_item[iid] = e.article.item_id
            enfants.append(EnfantArbre(iid, f"Boîte n°{l.id}",
                                       ("", "", "", l.quantite, fmt(l.peremption), l.numero_lot, l.specialite,
                                        l.emplacement, "", "", etat), (tag,)))
        iid = f"new:{e.article.item_id}"
        self._iid_item[iid] = e.article.item_id
        b = self._brouillon.get(e.article.item_id, {})
        inv = self.INVITES
        enfants.append(EnfantArbre(iid, "＋ Ajouter une boîte", (
            "", "", "", b.get("quantite") or inv["quantite"], b.get("peremption") or inv["peremption"],
            b.get("numero_lot") or inv["lot"], b.get("specialite") or inv["specialite"],
            b.get("emplacement") or inv["emplacement"], "", "",
            "saisir la quantité pour créer la boîte" if b else "cliquer sur une case"), ("ajout",)))
        return enfants

    def rafraichir_inventaire(self):
        self._fermer_editeur()
        sel = self.tv.selection()
        sel = sel[0] if sel else None
        ouverts = noeuds_ouverts(self.tv)
        self._iid_item = {}
        lignes = []
        for e in self._etats_filtres():
            a = e.article
            tags = [e.statut] + (["stup"] if a.est_stupefiant else [])
            groupe = "HORS" if e.hors_dotation else a.type
            lignes.append(LigneArbre(groupe, e.categorie, a.item_id, nom_article(a), (
                a.forme, a.liste,
                e.requis if e.requis is not None else (e.exigence.quantite_texte if e.exigence else "–"),
                e.stock_total, fmt(e.prochaine_peremption), "", "", "", e.stock_valide_horizon,
                e.a_commander or "", f"{SYMBOLES.get(e.statut, '')} {e.statut}"),
                tags, alerte=e.statut not in (STATUT_OK, STATUT_HORS_DOTATION), a_commander=e.a_commander > 0,
                enfants=self._enfants_lots(e)))
        filtre_actif = bool(self.filtre.get().strip()) or self.filtre_statut.get() != FILTRE_TOUS
        remplir_arbre(self.tv, lignes, ouverts, tout_ouvrir=filtre_actif, colonne_resume=10)
        if sel and self.tv.exists(sel):
            self.tv.selection_set(sel)
            self.tv.see(sel)

    def article_selectionne(self) -> Optional[str]:
        s = self.tv.selection()
        if not s:
            return None
        iid = s[0]
        if iid.startswith(("grp:", "cat:")):
            return None
        if iid.startswith(("lot:", "new:")):
            return self._iid_item.get(iid)
        return iid

    def lot_selectionne(self) -> Optional[Lot]:
        s = self.tv.selection()
        if s and s[0].startswith("lot:"):
            return self.db.lot(int(s[0][4:]))
        return None

    def etat(self, item_id: str) -> Optional[EtatArticle]:
        if not self.analyse:
            return None
        for e in self.analyse.etats:
            if e.article.item_id == item_id:
                return e
        return None

    def _bulle_inventaire(self, iid: str) -> Optional[str]:
        if iid.startswith("new:"):
            return ("Nouvelle boîte : cliquez sur une case pour la saisir.\n"
                    "Ordre de saisie : quantité, péremption, n° de lot, spécialité, emplacement (Tab pour avancer).\n"
                    "La boîte est créée dès que la quantité est saisie ; la péremption accepte JJ/MM/AAAA ou MM/AAAA.")
        if iid.startswith("lot:"):
            lot = self.db.lot(int(iid[4:]))
            if not lot:
                return None
            t = f"Boîte n°{lot.id}, entrée le {fmt(lot.date_entree)}."
            if lot.commentaire:
                t += f"\n{lot.commentaire}"
            return t + "\nCliquez sur une case pour la modifier. Clic droit : sortie, débarquement, détails."
        if iid == "grp:HORS":
            return ("Articles suivis en plus de la dotation réglementaire, rangés par sous-catégorie.\n"
                    "Bouton « Nouvel article hors dotation » ou clic droit pour en créer un.")
        if iid.startswith(("grp:", "cat:")):
            return None
        e = self.etat(iid)
        if not e:
            return None
        a = e.article
        lignes = [a.libelle]
        details = [x for x in (f"voie {a.voie}" if a.voie else "", f"liste {a.liste}" if a.liste else "",
                               f"ATC {a.atc}" if a.atc else "") if x]
        if details:
            lignes.append(" · ".join(details))
        if a.remarques:
            lignes.append(a.remarques)
        if e.exigence:
            q = e.requis if e.requis is not None else e.exigence.quantite_texte
            lignes.append(f"Quantité exigée : {q}")
            for o in e.exigence.origines:
                src = "quantité supplémentaire" if o.dotation == "SUPP" else f"dotation {o.dotation}"
                qb = o.quantite_brute if o.quantite_brute is not None else "?"
                coef = f" × {o.coefficient:g}" if o.coefficient != 1 else ""
                note = f" ({o.note})" if o.note and o.dotation != "SUPP" else (f" : {o.note}" if o.note else "")
                lignes.append(f"   • {src}{note} : {qb}{coef}")
        elif a.perso:
            lignes.append("Article hors dotation, suivi sans quantité exigée.")
        limite = self.analyse.horizon + timedelta(days=self.analyse.marge_jours)
        lignes.append(f"Stock : {e.stock_total}, dont {e.stock_valide_horizon} valides au {fmt(limite)}.")
        if e.lots_perimes:
            lignes.append(f"{len(e.lots_perimes)} boîte(s) périmée(s) à détruire.")
        if e.lots_expirant:
            lignes.append(f"{len(e.lots_expirant)} boîte(s) à remplacer avant le {fmt(limite)}.")
        if e.a_commander:
            lignes.append(f"À commander : {e.a_commander}.")
        if a.perso:
            lignes.append("Clic droit : modifier ou supprimer cet article.")
        return "\n".join(lignes)

    def _menu_inventaire(self, event):
        iid = self.tv.identify_row(event.y)
        m = tk.Menu(self, tearoff=0)
        if iid:
            self._fermer_editeur()
            self.tv.selection_set(iid)
            self.tv.focus(iid)
        if iid.startswith("lot:"):
            m.add_command(label="Sortie (distribution, casse…)…", command=lambda: self.dialogue_sortie())
            m.add_command(label="Débarquer (périmé)…", command=lambda: self.dialogue_sortie("Débarquement pour péremption"))
            m.add_command(label="Détails de la boîte…", command=self.dialogue_modifier_lot)
            m.add_command(label="Retirer la boîte", command=self.supprimer_lot_selectionne)
            m.add_separator()
        item_id = self.article_selectionne() if iid else None
        if item_id:
            m.add_command(label="Ajouter une boîte", command=lambda: self._ajouter_boite(item_id))
            m.add_command(label="Quantité supplémentaire exigée…", command=self.dialogue_exigence_supp)
            art = self._article(item_id)
            if art.perso:
                m.add_command(label="Modifier l'article hors dotation…",
                              command=lambda: self.dialogue_article_hors_dotation(item_id))
                m.add_command(label="Supprimer l'article hors dotation", command=lambda: self.supprimer_article_perso(item_id))
            m.add_separator()
        m.add_command(label="Nouvel article hors dotation…", command=self.dialogue_article_hors_dotation)
        m.tk_popup(event.x_root, event.y_root)

    def _ajouter_boite(self, item_id: str):
        if not self.tv.exists(item_id):
            return
        parent = self.tv.parent(item_id)
        if parent:
            self.tv.item(parent, open=True)
        self.tv.item(item_id, open=True)
        maj_marqueurs(self.tv)
        self.after(20, lambda: self._editer(f"new:{item_id}", "quantite"))

    # ---------------- dialogues boîtes
    def dialogue_modifier_lot(self):
        lot = self.lot_selectionne()
        if not lot:
            messagebox.showinfo("Boîte", "Sélectionnez une boîte dans l'inventaire (clic sur « Boîte n° »).")
            return
        art = self._article(lot.item_id)
        d = Dialogue(self, f"Boîte n°{lot.id} – {art.libelle}")
        champs = d.champs([("Quantité", "quantite", str(lot.quantite)), ("Péremption", "peremption", fmt(lot.peremption)),
                           ("N° de lot", "numero_lot", lot.numero_lot), ("Spécialité / marque", "specialite", lot.specialite),
                           ("Emplacement", "emplacement", lot.emplacement), ("Date d'entrée", "date_entree", fmt(lot.date_entree)),
                           ("Commentaire", "commentaire", lot.commentaire)],
                          bouton_supprimer=True)
        res = d.attendre()
        if res == "supprimer":
            if messagebox.askyesno("Retirer", "Retirer cette boîte de l'inventaire ?"):
                self.db.supprimer_lot(lot.id)
                self.recalculer(selection=lot.item_id)
            return
        if not res:
            return
        try:
            lot.quantite = int(champs["quantite"].get())
            if lot.quantite < 0:
                raise ValueError("Quantité négative")
            lot.peremption = parse_date(champs["peremption"].get())
            lot.date_entree = parse_date(champs["date_entree"].get())
        except ValueError as exc:
            messagebox.showerror("Saisie", str(exc))
            return
        lot.numero_lot = champs["numero_lot"].get().strip()
        lot.specialite = champs["specialite"].get().strip()
        lot.emplacement = champs["emplacement"].get().strip()
        lot.commentaire = champs["commentaire"].get().strip()
        if lot.quantite == 0:
            self.db.supprimer_lot(lot.id, motif="Correction")
            self.recalculer(selection=lot.item_id)
        else:
            self.db.modifier_lot(lot, motif="Correction")
            self.recalculer(selection=f"lot:{lot.id}")

    def supprimer_lot_selectionne(self):
        lot = self.lot_selectionne()
        if not lot:
            return
        if messagebox.askyesno("Retirer", f"Retirer la boîte n°{lot.id} ({lot.quantite}) de l'inventaire ?\n"
                                          "Pour une distribution ou un débarquement, préférez « Sortie » ou « Débarquer »."):
            self.db.supprimer_lot(lot.id)
            self.recalculer(selection=lot.item_id)

    # type de sortie affiché -> type de mouvement enregistré
    TYPES_SORTIE = {
        "Distribution / administration à bord": "distribution",
        "Débarquement pour péremption": "débarquement",
        "Débarquement (autre motif)": "débarquement",
        "Casse ou perte": "perte",
        "Autre sortie": "sortie",
    }

    def dialogue_sortie(self, choix: str = "Distribution / administration à bord"):
        lot = self.lot_selectionne()
        if not lot:
            messagebox.showinfo("Sortie", "Sélectionnez la boîte concernée dans l'inventaire (clic sur « Boîte n° »).")
            return
        art = self._article(lot.item_id)
        d = Dialogue(self, f"Sortie de stock – {art.libelle} (boîte n°{lot.id}, stock {lot.quantite})")
        c = d.champs([("Quantité", "quantite", str(lot.quantite) if choix.startswith("Débarquement") else "1"),
                      ("Type de sortie", "type", choix, list(self.TYPES_SORTIE), False),
                      ("Précision (facultatif)", "commentaire", "")])
        d.note("Secret médical : ne saisissez aucune donnée relative à un patient (nom, pathologie). "
               "L'historique ne sert qu'à la gestion du stock.")
        if art.est_stupefiant:
            d.note("Stupéfiant : reportez aussi ce mouvement dans le registre papier des stupéfiants.", alerte=True)
        if not d.attendre():
            return
        libelle = c["type"].get()
        try:
            self.db.sortie_lot(lot.id, int(c["quantite"].get()), motif=libelle,
                               commentaire=c["commentaire"].get().strip(),
                               type_mvt=self.TYPES_SORTIE.get(libelle, "sortie"))
        except ValueError as exc:
            messagebox.showerror("Saisie", str(exc) or "Quantité invalide.")
            return
        self.recalculer(selection=lot.item_id)
        if art.est_stupefiant:
            self.barre.config(text="Stupéfiant : pensez à reporter ce mouvement dans le registre papier des stupéfiants.")

    # ---------------- articles hors dotation
    def _sous_categories(self) -> List[str]:
        existantes = {p.categorie for p in self.db.articles_perso().values() if p.categorie}
        return list(SOUS_CATEGORIES_HORS_DOTATION) + sorted(existantes - set(SOUS_CATEGORIES_HORS_DOTATION))

    def dialogue_article_hors_dotation(self, item_id: Optional[str] = None):
        perso = self.db.articles_perso()
        p = perso.get(item_id) if item_id else None
        supp = self.db.exigences_supp().get(item_id) if item_id else None
        types = {"Médicament": TYPE_MED, "Matériel": TYPE_MAT}
        d = Dialogue(self, "Modifier l'article hors dotation" if p else "Nouvel article hors dotation")
        c = d.champs([
            ("Type", "type", "Matériel" if p and p.type == TYPE_MAT else "Médicament", list(types), False),
            ("Sous-catégorie", "categorie", (p.categorie if p else "") or SOUS_CATEGORIES_HORS_DOTATION[0],
             self._sous_categories(), True),
            ("Dénomination (DCI ou article)", "nom", p.nom if p else ""),
            ("Forme / présentation", "forme", p.forme if p else ""),
            ("Voie d'administration", "voie", p.voie if p else ""),
            ("Liste", "liste", p.liste if p else "", ["", "I", "II", "Stupéfiant"], True),
            ("Remarques", "remarques", p.remarques if p else ""),
            ("Quantité à détenir (0 = simple suivi)", "quantite", str(supp.quantite if supp else 0)),
            ("Motif de cette quantité", "motif", supp.motif if supp else ""),
        ])
        if not d.attendre():
            return
        typ = types.get(c["type"].get(), TYPE_MED)
        nom = c["nom"].get().strip()
        if not nom:
            messagebox.showerror("Saisie", "La dénomination est obligatoire.")
            return
        try:
            q = int(c["quantite"].get() or 0)
        except ValueError:
            messagebox.showerror("Saisie", "Quantité entière attendue.")
            return
        # l'identifiant reste stable à la modification, pour ne pas perdre les boîtes déjà saisies
        nouvel_id = item_id or make_id("perso", typ.lower(), nom, c["forme"].get())
        self.db.sauver_article_perso(ArticlePerso(
            item_id=nouvel_id, type=typ, nom=nom, forme=c["forme"].get().strip(), voie=c["voie"].get().strip(),
            liste=c["liste"].get().strip(), remarques=c["remarques"].get().strip(),
            categorie=c["categorie"].get().strip() or SOUS_CATEGORIES_HORS_DOTATION[-1]))
        self.db.sauver_exigence_supp(ExigenceSupplementaire(nouvel_id, q, c["motif"].get().strip()))
        if self.filtre_statut.get() not in (FILTRE_TOUS, FILTRE_HORS):
            self.filtre_statut.set(FILTRE_TOUS)
        self.recalculer(selection=nouvel_id)
        if not item_id:
            self._ajouter_boite(nouvel_id)

    def supprimer_article_perso(self, item_id: str):
        if self.db.lots(item_id):
            messagebox.showinfo("Supprimer", "Cet article a encore des boîtes en stock : retirez-les d'abord.")
            return
        if messagebox.askyesno("Supprimer", f"Supprimer l'article « {self._article(item_id).libelle} » ?"):
            self.db.supprimer_article_perso(item_id)
            self.ajustements.pop(item_id, None)
            self._sauver_ajustements()
            self.recalculer()

    def dialogue_exigence_supp(self):
        item_id = self.article_selectionne()
        if not item_id:
            messagebox.showinfo("Quantité supplémentaire", "Sélectionnez un article.")
            return
        art = self._article(item_id)
        supp = self.db.exigences_supp().get(item_id)
        d = Dialogue(self, f"Quantité exigée en plus du réglementaire – {art.libelle}")
        c = d.champs([("Quantité supplémentaire (0 pour retirer)", "quantite", str(supp.quantite if supp else 0)),
                      ("Motif (consigne armement, médecin, ...)", "motif", supp.motif if supp else "")])
        if not d.attendre():
            return
        try:
            q = int(c["quantite"].get())
        except ValueError:
            messagebox.showerror("Saisie", "Quantité invalide.")
            return
        self.db.sauver_exigence_supp(ExigenceSupplementaire(item_id, q, c["motif"].get().strip()))
        self.recalculer(selection=item_id)

    def _article(self, item_id: str) -> Article:
        e = self.etat(item_id)
        if e:
            return e.article
        a = self.ref.article(item_id)
        if a:
            return a
        p = self.db.articles_perso().get(item_id)
        if p:
            return article_depuis_perso(p)
        return Article(item_id=item_id, type=TYPE_MAT, nom=item_id)

    # ---------------- onglet commande
    def _construire_commande(self):
        f = self.onglet_commande
        haut = ttk.LabelFrame(f, text="Horizon de couverture (prochaine traversée)", padding=10)
        haut.pack(fill="x", pady=(0, 6))
        ttk.Label(haut, text="Délai (jours) :").grid(row=0, column=0, sticky="w")
        sp = ttk.Spinbox(haut, from_=1, to=730, textvariable=self.delai_var, width=6, command=self._maj_horizon_depuis_delai)
        sp.grid(row=0, column=1, padx=6)
        sp.bind("<KeyRelease>", lambda *_: self._maj_horizon_depuis_delai())
        ttk.Label(haut, text="ou date de fin de traversée :").grid(row=0, column=2, padx=(12, 4))
        e = ttk.Entry(haut, textvariable=self.horizon_var, width=12)
        e.grid(row=0, column=3)
        e.bind("<KeyRelease>", lambda *_: self._maj_delai_depuis_horizon())
        ttk.Label(haut, text="Marge sur les péremptions (jours) :").grid(row=0, column=4, padx=(12, 4))
        ttk.Spinbox(haut, from_=0, to=365, textvariable=self.marge_var, width=5).grid(row=0, column=5)
        ttk.Button(haut, text="Calculer la commande", style="Accent.TButton", command=self.sauver_config).grid(row=0, column=6, padx=14)
        ttk.Label(haut, font=(POLICE, 9), wraplength=1300, justify="left", text=(
            "Une boîte est comptée valide si elle n'est pas périmée à la date de fin de traversée + marge. "
            "À commander = quantité réglementaire − stock valide à cette date. Cliquez sur la case « À commander » "
            "pour ajuster une quantité à la main (0 pour retirer la ligne) ; survolez une ligne pour le détail du calcul.")
        ).grid(row=1, column=0, columnspan=7, sticky="w", pady=(6, 0))

        btns = ttk.Frame(f)
        btns.pack(fill="x", pady=(0, 6))
        ttk.Button(btns, text="Imprimer le bon de commande officiel", style="Accent.TButton",
                   command=self.imprimer_bon_commande).pack(side="left", padx=(0, 4))
        ttk.Button(btns, text="Enregistrer le bon (HTML)…", command=lambda: self.exporter("commande_html")).pack(side="left", padx=2)
        ttk.Button(btns, text="Bon complet (toute la dotation)…", command=lambda: self.exporter("commande_html_tout")).pack(side="left", padx=2)
        ttk.Button(btns, text="Commande CSV…", command=lambda: self.exporter("commande_csv")).pack(side="left", padx=2)
        ttk.Button(btns, text="Inventaire Excel…", command=lambda: self.exporter("inventaire_xlsx")).pack(side="left", padx=2)
        ttk.Button(btns, text="Inventaire CSV…", command=lambda: self.exporter("inventaire_csv")).pack(side="left", padx=2)
        ttk.Button(btns, text="Annuler tous les ajustements manuels", command=self.reinit_ajustements).pack(side="right", padx=2)

        pan = ttk.PanedWindow(f, orient="vertical")
        pan.pack(fill="both", expand=True)
        c1 = ttk.LabelFrame(pan, text="Articles à commander pour être conforme à l'horizon", padding=6)
        cols = ("forme", "liste", "requis", "valide", "calcul", "commander", "motif")
        cadre1 = ttk.Frame(c1)
        cadre1.pack(fill="both", expand=True)
        self.tv_cmd = ttk.Treeview(cadre1, columns=cols, show="tree headings", selectmode="browse")
        self.tv_cmd.heading("#0", text="Catégorie / article")
        self.tv_cmd.column("#0", width=360, anchor="w")
        for c, lib, w in (("forme", "Forme / présentation", 280), ("liste", "Liste", 70), ("requis", "Qté régl.", 75),
                          ("valide", "Stock valide", 90), ("calcul", "Calculé", 75), ("commander", "À commander", 100),
                          ("motif", "Motif", 330)):
            self.tv_cmd.heading(c, text=lib)
            self.tv_cmd.column(c, width=w, anchor="center" if c in ("liste", "requis", "valide", "calcul", "commander") else "w")
        configurer_tags(self.tv_cmd)
        sb1 = ttk.Scrollbar(cadre1, orient="vertical", command=self.tv_cmd.yview)
        self.tv_cmd.configure(yscrollcommand=sb1.set)
        self.tv_cmd.pack(side="left", fill="both", expand=True)
        sb1.pack(side="right", fill="y")
        self.tv_cmd.bind("<ButtonRelease-1>", self._clic_commande)
        self.tv_cmd.bind("<Button-3>", self._menu_commande)
        self.tv_cmd.bind("<MouseWheel>", lambda e: self._valider_editeur(), add="+")
        InfoBulle(self.tv_cmd, lambda iid: self._bulles_cmd.get(iid))
        activer_depliage(self.tv_cmd)
        legende(c1, [("#ffffff", "quantité calculée", None), (CMD_AJOUT[0], "commandé à la main, non nécessaire", CMD_AJOUT[1]),
                     (CMD_MODIF[0], "quantité modifiée à la main", CMD_MODIF[1]),
                     (CMD_RETIRE[0], "retiré de la commande à la main", CMD_RETIRE[1]),
                     (HORS_GROUPE[0], "hors dotation", HORS_GROUPE[1])]).pack(fill="x", pady=(6, 0))
        pan.add(c1, weight=3)
        c2 = ttk.LabelFrame(pan, text="Alertes : boîtes périmées ou expirant avant l'horizon, articles à vérifier", padding=6)
        acols = ("article", "forme", "lot", "quantite", "peremption", "alerte")
        self.tv_alertes = ttk.Treeview(c2, columns=acols, show="headings", height=6)
        for c, lib, w in (("article", "Article", 300), ("forme", "Forme / présentation", 300), ("lot", "N° de lot", 100),
                          ("quantite", "Quantité", 70), ("peremption", "Péremption", 100), ("alerte", "Alerte", 420)):
            self.tv_alertes.heading(c, text=lib)
            self.tv_alertes.column(c, width=w, anchor="center" if c in ("quantite", "peremption") else "w")
        self.tv_alertes.tag_configure("perime", background=LOT_PERIME)
        self.tv_alertes.tag_configure("expire", background=LOT_EXPIRE)
        self.tv_alertes.tag_configure("verif", background=COULEURS[STATUT_NON_QUANTIFIE])
        sb2 = ttk.Scrollbar(c2, orient="vertical", command=self.tv_alertes.yview)
        self.tv_alertes.configure(yscrollcommand=sb2.set)
        self.tv_alertes.pack(side="left", fill="both", expand=True)
        sb2.pack(side="right", fill="y")
        pan.add(c2, weight=2)

    def _charger_ajustements(self) -> Dict[str, int]:
        try:
            data = json.loads(self.db.parametre("ajustements", "{}"))
            return {k: int(v) for k, v in data.items()}
        except (ValueError, TypeError):
            return {}

    def _sauver_ajustements(self):
        self.db.sauver_parametre("ajustements", json.dumps(self.ajustements))

    def reinit_ajustements(self):
        if self.ajustements and messagebox.askyesno("Ajustements", "Revenir aux quantités calculées pour toute la commande ?"):
            self.ajustements = {}
            self._sauver_ajustements()
            self.rafraichir_commande()

    def _clic_commande(self, event):
        iid = self.tv_cmd.identify_row(event.y)
        if not iid or not iid.startswith("cmd:"):
            return
        col = self.tv_cmd.identify_column(event.x)
        if col == "#0" or self.tv_cmd["columns"][int(col[1:]) - 1] != "commander":
            return
        self._editer_commande(iid)

    def _editer_commande(self, iid: str):
        item_id = iid[4:]
        self._fermer_editeur()
        try:
            self._editeur = EditeurCellule(
                self.tv_cmd, iid, "commander", str(self.tv_cmd.set(iid, "commander")),
                on_commit=lambda t: self._valider_ajustement(item_id, t),
                on_fermer=lambda: setattr(self, "_editeur", None))
        except RuntimeError:
            pass

    def _menu_commande(self, event):
        iid = self.tv_cmd.identify_row(event.y)
        if not iid or not iid.startswith("cmd:"):
            return
        self.tv_cmd.selection_set(iid)
        item_id = iid[4:]
        m = tk.Menu(self, tearoff=0)
        m.add_command(label="Modifier la quantité…", command=lambda: self._editer_commande(iid))
        if item_id in self.ajustements:
            m.add_command(label="Revenir à la quantité calculée", command=lambda: self._retirer_ajustement(item_id))
        m.add_command(label="Retirer de la commande", command=lambda: self._valider_ajustement(item_id, "0"))
        m.tk_popup(event.x_root, event.y_root)

    def _retirer_ajustement(self, item_id: str):
        self.ajustements.pop(item_id, None)
        self._sauver_ajustements()
        self.rafraichir_commande()

    def _valider_ajustement(self, item_id: str, texte: str) -> bool:
        texte = texte.strip()
        try:
            q = int(texte) if texte else 0
            if q < 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Saisie", "Quantité entière attendue.", parent=self)
            return False
        e = self.etat(item_id)
        if e is not None and q == e.a_commander:
            self.ajustements.pop(item_id, None)
        else:
            self.ajustements[item_id] = q
        self._sauver_ajustements()
        self.after(10, self.rafraichir_commande)
        return True

    def _maj_horizon_depuis_delai(self):
        try:
            self.horizon_var.set(fmt(date.today() + timedelta(days=int(self.delai_var.get()))))
        except (tk.TclError, ValueError):
            pass

    def _maj_delai_depuis_horizon(self):
        try:
            h = parse_date(self.horizon_var.get())
            if h:
                self.delai_var.set(max(1, (h - date.today()).days))
        except ValueError:
            pass

    def horizon(self) -> date:
        try:
            h = parse_date(self.horizon_var.get())
        except ValueError:
            h = None
        if h is None:
            try:
                h = date.today() + timedelta(days=int(self.delai_var.get() or 90))
            except tk.TclError:
                h = date.today() + timedelta(days=90)
        return h

    def rafraichir_commande(self):
        ouverts = noeuds_ouverts(self.tv_cmd)
        self.tv_alertes.delete(*self.tv_alertes.get_children())
        self._bulles_cmd = {}
        if not self.analyse:
            self.tv_cmd.delete(*self.tv_cmd.get_children())
            return
        limite = self.analyse.horizon + timedelta(days=self.analyse.marge_jours)
        au = f"au {fmt(limite)}"
        lignes = []
        commandes = {lc.etat.article.item_id: lc for lc in lignes_commande(self.analyse, self.ajustements)}
        for e in self.analyse.etats:
            a = e.article
            lc = commandes.get(a.item_id)
            retire = lc is None and self.ajustements.get(a.item_id) == 0 and e.a_commander > 0
            if lc is None and not retire:
                continue
            q = lc.quantite if lc else 0
            calc = e.a_commander
            requis = e.requis if e.requis is not None else ""
            calcul = f"Calcul : quantité exigée {requis} − stock valide {au} {e.stock_valide_horizon} = {calc}."
            if retire:
                tag, motif = "cmd_retire", f"retiré à la main (le calcul demande {calc})"
                bulle = (f"Retiré de la commande à la main alors que le calcul demande {calc}.\n{calcul}\n"
                         "Cliquez sur « À commander » pour rétablir une quantité, ou clic droit.")
            elif lc.ajustee and calc == 0:
                tag, motif = "cmd_ajout", "commandé à la main, non nécessaire"
                bulle = (f"Commandé à la main alors que ce n'est pas nécessaire : le calcul ne demande rien.\n{calcul}\n"
                         "Clic droit : revenir à la quantité calculée.")
            elif lc.ajustee:
                tag, motif = "cmd_modif", f"quantité modifiée à la main (calcul : {calc})"
                bulle = f"Quantité modifiée à la main : {q} au lieu de {calc}.\n{calcul}\nClic droit : revenir à la quantité calculée."
            else:
                tag = ""
                if e.statut == STATUT_MANQUANT:
                    motif = "aucun stock valide"
                elif e.lots_expirant or e.lots_perimes:
                    motif = "boîtes périmées ou expirant avant l'horizon"
                else:
                    motif = "stock insuffisant"
                bulle = calcul
                if e.lots_expirant:
                    bulle += f"\n{len(e.lots_expirant)} boîte(s) expirent avant le {fmt(limite)} et ne sont pas comptées."
                if e.lots_perimes:
                    bulle += f"\n{len(e.lots_perimes)} boîte(s) périmée(s) à détruire."
            if e.exigence and not e.exigence.obligatoire:
                motif += " – recommandé, non obligatoire"
            iid = "cmd:" + a.item_id
            self._bulles_cmd[iid] = f"{a.libelle}\n{bulle}"
            tags = ([tag] if tag else []) + (["stup"] if a.est_stupefiant else [])
            groupe = "HORS" if e.hors_dotation else a.type
            lignes.append(LigneArbre(groupe, e.categorie, iid, nom_article(a),
                                     (a.forme, a.liste, requis, e.stock_valide_horizon, calc, q, motif), tags,
                                     alerte=not retire, a_commander=not retire))
        remplir_arbre(self.tv_cmd, lignes, ouverts, colonne_resume=6)
        for e in self.analyse.etats:
            a = e.article
            nom = nom_article(a)
            for l in e.lots_perimes:
                self.tv_alertes.insert("", "end", tags=("perime",), values=(
                    nom, a.forme, l.numero_lot, l.quantite, fmt(l.peremption), "PÉRIMÉE : à retirer et détruire"))
            for l in e.lots_expirant:
                self.tv_alertes.insert("", "end", tags=("expire",), values=(
                    nom, a.forme, l.numero_lot, l.quantite, fmt(l.peremption),
                    f"expire avant le {fmt(limite)} : à remplacer à l'escale"))
            if e.statut == STATUT_NON_QUANTIFIE:
                self.tv_alertes.insert("", "end", tags=("verif",), values=(
                    nom, a.forme, "", e.stock_total, "", f"quantité réglementaire non chiffrée : {e.exigence.quantite_texte}"))
        if self.cfg.marchandises_dangereuses:
            self.tv_alertes.insert("", "end", tags=("verif",), values=(
                "Antidotes GSMU", "", "", "", "", "marchandises dangereuses : suivre les antidotes du Guide des soins "
                                             "médicaux d'urgence en articles hors dotation"))

    def imprimer_bon_commande(self):
        """Génère le bon de commande officiel dans un fichier temporaire et l'ouvre dans le navigateur."""
        if not self.analyse:
            return
        dossier = Path(tempfile.gettempdir()) / "pharma_bord"
        dossier.mkdir(exist_ok=True)
        p = dossier / f"bon_de_commande_{date.today().isoformat()}.html"
        commande_html(self.analyse, self.cfg, p, ajustements=self.ajustements)
        webbrowser.open(p.as_uri())
        self.barre.config(text="Bon de commande ouvert dans le navigateur : vérifiez, puis « Imprimer » (ou Ctrl+P).")

    def exporter(self, quoi: str):
        if not self.analyse:
            return
        types = {"commande_html": ("HTML", ".html"), "commande_html_tout": ("HTML", ".html"), "commande_csv": ("CSV", ".csv"),
                 "inventaire_xlsx": ("Excel", ".xlsx"), "inventaire_csv": ("CSV", ".csv"), "mouvements_csv": ("CSV", ".csv")}
        lib, ext = types[quoi]
        defaut = {"commande_html": "bon_de_commande", "commande_html_tout": "bon_de_commande_complet",
                  "commande_csv": "commande", "inventaire_xlsx": "inventaire_dotation", "inventaire_csv": "inventaire",
                  "mouvements_csv": "historique"}[quoi]
        chemin = filedialog.asksaveasfilename(defaultextension=ext, filetypes=[(lib, "*" + ext)],
                                              initialfile=f"{defaut}_{date.today().isoformat()}{ext}")
        if not chemin:
            return
        p = Path(chemin)
        try:
            if quoi == "commande_html":
                commande_html(self.analyse, self.cfg, p, ajustements=self.ajustements)
            elif quoi == "commande_html_tout":
                commande_html(self.analyse, self.cfg, p, inclure_tout=True, ajustements=self.ajustements)
            elif quoi == "commande_csv":
                commande_csv(self.analyse, p, ajustements=self.ajustements)
            elif quoi == "inventaire_xlsx":
                inventaire_xlsx(self.analyse, self.cfg, p)
            elif quoi == "inventaire_csv":
                inventaire_csv(self.analyse, p)
            elif quoi == "mouvements_csv":
                mouvements_csv(self.db.mouvements(), self._libelles(), p)
        except (OSError, ImportError) as exc:
            messagebox.showerror("Export", str(exc))
            return
        self.barre.config(text=f"Exporté : {p}")
        if ext == ".html":
            webbrowser.open(p.as_uri())
        elif messagebox.askyesno("Export", f"Fichier enregistré :\n{p}\n\nL'ouvrir maintenant ?"):
            try:
                os.startfile(str(p))  # type: ignore[attr-defined]
            except (AttributeError, OSError):
                webbrowser.open(p.as_uri())

    def _libelles(self) -> Dict[str, str]:
        return {i: self._article(i).libelle for i in {m.item_id for m in self.db.mouvements()}}

    # ---------------- onglet historique
    def _construire_historique(self):
        f = self.onglet_historique
        haut = ttk.Frame(f)
        haut.pack(fill="x", pady=(0, 6))
        self.filtre_mvt = StringVar()
        ttk.Label(haut, text="Rechercher").pack(side="left")
        e = ttk.Entry(haut, textvariable=self.filtre_mvt, width=28)
        e.pack(side="left", padx=6)
        e.bind("<KeyRelease>", lambda *_: self.rafraichir_historique())
        ttk.Label(haut, font=(POLICE, 9), text=(
            "   Entrées, distributions, débarquements et corrections du stock, sans donnée patient. "
            "Ne remplace pas les registres tenus à bord (stupéfiants : registre papier).")).pack(side="left")
        ttk.Button(haut, text="Exporter CSV…", command=lambda: self.exporter("mouvements_csv")).pack(side="right", padx=2)
        cols = ("date", "article", "lot", "type", "quantite", "motif", "commentaire")
        self.tv_mvt = ttk.Treeview(f, columns=cols, show="headings")
        for c, lib, w in (("date", "Date", 130), ("article", "Article", 420), ("lot", "Boîte", 60), ("type", "Type", 100),
                          ("quantite", "Qté", 60), ("motif", "Motif", 220), ("commentaire", "Commentaire", 320)):
            self.tv_mvt.heading(c, text=lib)
            self.tv_mvt.column(c, width=w, anchor="center" if c in ("lot", "quantite", "type") else "w")
        self.tv_mvt.tag_configure("neg", background="#fff6ea")
        self.tv_mvt.tag_configure("pos", background="#f1f8f2")
        sb = ttk.Scrollbar(f, orient="vertical", command=self.tv_mvt.yview)
        self.tv_mvt.configure(yscrollcommand=sb.set)
        self.tv_mvt.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

    def rafraichir_historique(self):
        self.tv_mvt.delete(*self.tv_mvt.get_children())
        n = normalize(self.filtre_mvt.get())
        libelles = self._libelles()
        for m in self.db.mouvements():
            lib = libelles.get(m.item_id, m.item_id)
            if n and n not in normalize(lib + " " + m.motif + " " + m.commentaire + " " + m.type):
                continue
            self.tv_mvt.insert("", "end", tags=("neg" if m.quantite < 0 else "pos",), values=(
                m.horodatage.strftime("%d/%m/%Y %H:%M"), lib, m.lot_id or "", m.type,
                f"{m.quantite:+d}", m.motif, m.commentaire))

    # ---------------- onglet réglementation
    def _construire_referentiel(self):
        f = self.onglet_referentiel
        haut = ttk.Frame(f)
        haut.pack(fill="x", pady=(0, 6))
        ttk.Label(haut, text="Dotation :").pack(side="left")
        self.cb_ref = ttk.Combobox(haut, state="readonly", width=48,
                                   values=[f"{d.code} – {d.titre}" for d in self.ref.dotations.values()])
        self.cb_ref.pack(side="left", padx=6)
        self.cb_ref.bind("<<ComboboxSelected>>", lambda *_: self.rafraichir_referentiel())
        ttk.Label(haut, font=(POLICE, 9),
                  text="   Transcription de la Division 217 (consultation seule).").pack(side="left")
        self.lbl_ref = ttk.Label(f, wraplength=1350, justify="left", font=(POLICE, 9))
        self.lbl_ref.pack(fill="x", pady=(0, 6))
        cols = ("voie", "forme", "quantite", "liste", "flags", "remarques")
        cadre = ttk.Frame(f)
        cadre.pack(fill="both", expand=True)
        self.tv_ref = ttk.Treeview(cadre, columns=cols, show="tree headings")
        self.tv_ref.heading("#0", text="Catégorie / article")
        self.tv_ref.column("#0", width=380, anchor="w")
        for c, lib, w in (("voie", "Voie", 110), ("forme", "Forme / présentation", 300), ("quantite", "Quantité", 80),
                          ("liste", "Liste", 70), ("flags", "Conditions", 150), ("remarques", "Remarques", 340)):
            self.tv_ref.heading(c, text=lib)
            self.tv_ref.column(c, width=w, anchor="center" if c in ("quantite", "liste") else "w")
        configurer_tags(self.tv_ref)
        activer_depliage(self.tv_ref)
        sb = ttk.Scrollbar(cadre, orient="vertical", command=self.tv_ref.yview)
        self.tv_ref.configure(yscrollcommand=sb.set)
        self.tv_ref.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        if self.ref.dotations:
            self.cb_ref.current(0)
            self.rafraichir_referentiel()

    def rafraichir_referentiel(self):
        self.tv_ref.delete(*self.tv_ref.get_children())
        i = self.cb_ref.current()
        if i < 0:
            return
        d = list(self.ref.dotations.values())[i]
        self.lbl_ref.config(text=f"{d.conditions}\nSource : {d.source}")
        conditions = {"paludisme": "zone de paludisme", "aes": "recommandé (AES)", "equipage>10": "équipage > 10",
                      "pax_kits": "1 par tranche de 100 passagers (max 3)", "dae_reco": "recommandé",
                      "sac": "sac d'intervention", "peche_facultatif": "facultatif pêche",
                      "court_trajet": "non exigé si trajet < 30 min", "pax400": "≥ 400 passagers"}
        lignes = []
        for n, l in enumerate(d.lignes):
            a = l.article
            flags = ", ".join(conditions.get(x, x) for x in l.flags_categorie + l.flags_article if not x.startswith("kit:"))
            lignes.append(LigneArbre(a.type, l.categorie, f"ref:{n}", nom_article(a), (
                a.voie, a.forme, l.quantite if l.quantite is not None else l.quantite_texte, a.liste, flags, a.remarques),
                ["stup"] if a.est_stupefiant else []))
        remplir_arbre(self.tv_ref, lignes, None, colonne_resume=None)

    # ------------------------------------------------------------------ calcul global
    def recalculer(self, selection: Optional[str] = None):
        self._fermer_editeur()
        try:
            exig = calculer_exigences(self.ref, self.cfg, self.db.exigences_supp(), self.db.articles_perso())
        except ErreurReferentiel as exc:
            messagebox.showerror("Référentiel", str(exc))
            return
        try:
            marge = int(self.marge_var.get() or 0)
        except tk.TclError:
            marge = 0
        self.analyse = analyser(exig, self.db.lots_par_article(), self.horizon(), marge,
                                articles_perso=self.db.articles_perso(), ref=self.ref)
        self.rafraichir_inventaire()
        if selection and self.tv.exists(selection):
            noeud = self.tv.parent(selection)
            while noeud:
                self.tv.item(noeud, open=True)
                maj_marqueur(self.tv, noeud)
                noeud = self.tv.parent(noeud)
            self.tv.selection_set(selection)
            self.tv.focus(selection)
            self.tv.see(selection)
        self.rafraichir_commande()
        self.rafraichir_historique()
        self._maj_resume()

    def _maj_resume(self):
        r = self.analyse.resume()
        dot = LIBELLES_DOTATION.get(self.cfg.dotation_base, self.cfg.dotation_base)
        entete = f"{self.cfg.nom or 'Navire sans nom'}"
        if self.cfg.immatriculation:
            entete += f" ({self.cfg.immatriculation})"
        entete += f"   ·   {dot}"
        if self.cfg.complement_passagers:
            entete += f"  +  complément {self.cfg.complement_passagers}"
        entete += f"\nCouverture jusqu'au {fmt(self.analyse.horizon)} (+{self.analyse.marge_jours} j de marge)"
        self.lbl_entete.config(text=entete)
        self.tuiles["exiges"].config(text=str(r["articles exigés"]))
        self.tuiles["conformes"].config(text=str(r["conformes"]))
        self.tuiles["commander"].config(text=str(r["à commander"]))
        self.tuiles["perimes"].config(text=str(r["lots périmés"]))
        self.tuiles["expirant"].config(text=str(r["lots expirant avant l'horizon"]))
        opts = [lib for cle, lib in (("zone_paludisme", "paludisme"), ("aes", "AES"), ("dae", "DAE"),
                                     ("sac_medical_urgence", "sac médical d'urgence"), ("plongee", "plongée"),
                                     ("navire_peche", "pêche"), ("desserte_courte", "desserte < 30 min"),
                                     ("marchandises_dangereuses", "marchandises dangereuses")) if getattr(self.cfg, cle)]
        lignes = [f"Dotation : {dot}"]
        if self.cfg.complement_passagers:
            lignes.append(f"Complément passagers : {LIBELLES_DOTATION.get(self.cfg.complement_passagers)}")
        lignes.append(f"Effectif : {self.cfg.effectif} marins, {self.cfg.nb_passagers} passagers.  Options : {', '.join(opts) or 'aucune'}")
        lignes.append(f"Horizon de couverture : {fmt(self.analyse.horizon)} (+{self.analyse.marge_jours} j de marge)")
        lignes.append("")
        for k, v in r.items():
            lignes.append(f"• {k} : {v}")
        self.lbl_resume.config(text="\n".join(lignes))
        a_remplacer = r["lots expirant avant l'horizon"]
        self.barre.config(text=f"{r['articles exigés']} articles exigés – {r['à commander']} à commander – "
                               f"{r['lots périmés']} boîtes périmées – {a_remplacer} boîtes à remplacer")

    # ------------------------------------------------------------------ à propos
    def dialogue_a_propos(self):
        """Fenêtre « À propos » (bouton du bandeau ou F1) : version, mention d'auteur, licence, absence de
        garantie ; « Lire la licence » et « Lire NOTICE » affichent ces fichiers dans le programme."""
        if getattr(self, "_a_propos_ouvert", False):
            return
        self._a_propos_ouvert = True
        try:
            d = Dialogue(self, "À propos de Pharma Bord")
            titre, _, corps = texte_a_propos().partition("\n")
            ttk.Label(d.corps, text=titre, font=(POLICE, 14, "bold")).pack(anchor="w")
            ttk.Label(d.corps, text=corps.strip("\n"), justify="left", wraplength=660,
                      font=(POLICE, 10)).pack(anchor="w", pady=(6, 0))
            fermer = ttk.Button(d.boutons, text="Fermer", style="Accent.TButton", command=lambda: d._fermer(True))
            fermer.pack(side="right")
            ttk.Button(d.boutons, text="Lire la licence", command=lambda: afficher_fichier(
                d, "Licence – GNU GPL version 3", FICHIER_LICENCE)).pack(side="left")
            ttk.Button(d.boutons, text="Lire NOTICE", command=lambda: afficher_fichier(
                d, "NOTICE – conditions additionnelles (article 7)", FICHIER_NOTICE)).pack(side="left", padx=4)
            # Entrée actionne le bouton qui a le focus (atteint par Tab) ; ailleurs, elle ferme la fenêtre
            d.bind("<Return>", lambda e: e.widget.invoke() if isinstance(e.widget, ttk.Button) else d._fermer(True))
            fermer.focus_set()          # Échap et Entrée ferment la fenêtre dès son ouverture
            d.attendre()
        finally:
            self._a_propos_ouvert = False

    def _quitter(self):
        try:
            self.cfg.delai_jours = int(self.delai_var.get() or 90)
            self.cfg.marge_jours = int(self.marge_var.get() or 0)
        except tk.TclError:
            pass
        self.db.sauver_config(self.cfg)
        self.db.close()
        self.destroy()


def _cle_cat(cat: str):
    num = cat.split(".")[0].strip()
    return (int(num), cat) if num.isdigit() else (999, cat)


# ---------------------------------------------------------------------- arbres groupés
GROUPES = {TYPE_MED: "MÉDICAMENTS", TYPE_MAT: "MATÉRIEL MÉDICAL ET OBJETS DE PANSEMENT",
           "HORS": "HORS DOTATION"}
ORDRE_GROUPES = {TYPE_MED: 0, TYPE_MAT: 1, "HORS": 2}


class EnfantArbre:
    """Une ligne sous un article (boîte / lot, ou ligne d'ajout)."""

    __slots__ = ("iid", "texte", "values", "tags")

    def __init__(self, iid, texte, values, tags=()):
        self.iid, self.texte, self.values, self.tags = iid, texte, values, list(tags)


class LigneArbre:
    """Une feuille à insérer dans un arbre groupé (groupe > catégorie > article [> boîtes])."""

    __slots__ = ("groupe", "categorie", "iid", "texte", "values", "tags", "alerte", "a_commander", "enfants")

    def __init__(self, groupe, categorie, iid, texte, values, tags=(), alerte=False, a_commander=False, enfants=None):
        self.groupe, self.categorie, self.iid, self.texte = groupe, categorie, iid, texte
        self.values, self.tags, self.alerte, self.a_commander = values, list(tags), alerte, a_commander
        self.enfants: List[EnfantArbre] = enfants or []


MARQUEURS = False          # True quand l'indicateur du thème est remplacé par ▸ / ▾
FERME, OUVERT = "▸  ", "▾  "


def _texte_nu(texte: str) -> str:
    return texte[len(FERME):] if texte.startswith((FERME, OUVERT)) else texte


def maj_marqueur(tv: ttk.Treeview, iid: str) -> None:
    if not MARQUEURS or not iid or not tv.exists(iid) or not tv.get_children(iid):
        return
    marque = OUVERT if tv.item(iid, "open") else FERME
    tv.item(iid, text=marque + _texte_nu(tv.item(iid, "text")))


def maj_marqueurs(tv: ttk.Treeview, parent: str = "") -> None:
    if not MARQUEURS:
        return
    for iid in tv.get_children(parent):
        if tv.get_children(iid):
            maj_marqueur(tv, iid)
            maj_marqueurs(tv, iid)


def activer_depliage(tv: ttk.Treeview) -> None:
    """Un clic sur le nom d'un groupe, d'une catégorie ou d'un article le déplie ou le replie."""
    def clic(event):
        if tv.identify_region(event.x, event.y) != "tree":
            return
        iid = tv.identify_row(event.y)
        if iid and tv.get_children(iid):
            tv.item(iid, open=not tv.item(iid, "open"))
            maj_marqueur(tv, iid)

    def double(event):
        iid = tv.identify_row(event.y)
        if iid and tv.get_children(iid):
            return "break"   # le simple clic suffit ; évite un double basculement

    tv.bind("<<TreeviewOpen>>", lambda e: tv.after_idle(lambda: maj_marqueur(tv, tv.focus())), add="+")
    tv.bind("<<TreeviewClose>>", lambda e: tv.after_idle(lambda: maj_marqueur(tv, tv.focus())), add="+")
    tv.bind("<ButtonRelease-1>", clic, add="+")
    tv.bind("<Double-1>", double, add="+")


def nom_article(a: Article) -> str:
    return ("[" + a.kit.capitalize() + "] " if a.kit else "") + a.nom


def configurer_tags(tv: ttk.Treeview) -> None:
    for statut, coul in COULEURS.items():
        tv.tag_configure(statut, background=coul)
    tv.tag_configure("stup", foreground="#b00020")
    tv.tag_configure("groupe", font=(POLICE, 10, "bold"), background="#d9e4f1", foreground=ACCENT)
    tv.tag_configure("groupe_hors", font=(POLICE, 10, "bold"), background=HORS_GROUPE[0], foreground=HORS_GROUPE[1])
    tv.tag_configure("categorie", font=(POLICE, 10, "bold"), background="#eef2f7")
    tv.tag_configure("categorie_alerte", font=(POLICE, 10, "bold"), background="#f9e7c4")
    tv.tag_configure("categorie_hors", font=(POLICE, 10, "bold"), background=HORS_CATEGORIE, foreground=HORS_GROUPE[1])
    tv.tag_configure("lot", background="#fbfbfb", foreground="#333")
    tv.tag_configure("lot_perime", background=LOT_PERIME, foreground="#333")
    tv.tag_configure("lot_expire", background=LOT_EXPIRE, foreground="#333")
    tv.tag_configure("ajout", background="#fbfbfb", foreground="#8a97a8", font=(POLICE, 9, "italic"))
    tv.tag_configure("cmd_ajout", background=CMD_AJOUT[0], foreground=CMD_AJOUT[1])
    tv.tag_configure("cmd_modif", background=CMD_MODIF[0], foreground=CMD_MODIF[1])
    tv.tag_configure("cmd_retire", background=CMD_RETIRE[0], foreground=CMD_RETIRE[1])


def noeuds_ouverts(tv: ttk.Treeview) -> Optional[set]:
    """Ensemble des nœuds dépliés, catégories et articles (None si l'arbre n'a jamais été rempli)."""
    if not tv.get_children():
        return None
    ouverts = set()
    for g in tv.get_children():
        for c in tv.get_children(g):
            if tv.item(c, "open"):
                ouverts.add(c)
            for a in tv.get_children(c):
                if tv.get_children(a) and tv.item(a, "open"):
                    ouverts.add(a)
    return ouverts


def deplier_tout(tv: ttk.Treeview, mode) -> None:
    """mode : "categories" (catégories ouvertes, articles fermés), "tout", "rien" ; True/False acceptés."""
    if mode is True:
        mode = "categories"
    elif mode is False:
        mode = "rien"
    for g in tv.get_children():
        tv.item(g, open=True)
        for c in tv.get_children(g):
            tv.item(c, open=mode != "rien")
            for a in tv.get_children(c):
                if tv.get_children(a):
                    tv.item(a, open=mode == "tout")
    maj_marqueurs(tv)


def remplir_arbre(tv: ttk.Treeview, lignes: List[LigneArbre], ouverts: Optional[set],
                  tout_ouvrir: bool = False, colonne_resume: Optional[int] = None) -> None:
    """Remplit ``tv`` en groupe > catégorie > article > boîtes ; ``colonne_resume`` = index de la colonne
    (dans values) où écrire le résumé de la catégorie (nombre d'articles, à commander)."""
    tv.delete(*tv.get_children())
    par_groupe: Dict[str, Dict[str, List[LigneArbre]]] = {}
    for l in lignes:
        par_groupe.setdefault(l.groupe, {}).setdefault(l.categorie, []).append(l)
    for groupe in sorted(par_groupe, key=lambda g: ORDRE_GROUPES.get(g, 9)):
        gid = f"grp:{groupe}"
        cats = par_groupe[groupe]
        total = sum(len(v) for v in cats.values())
        hors = groupe == "HORS"
        tv.insert("", "end", iid=gid, text=f"{GROUPES.get(groupe, groupe)}  ({total})", open=True,
                  tags=("groupe_hors",) if hors else ("groupe",))
        for cat in sorted(cats, key=_cle_cat):
            cid = f"cat:{groupe}:{cat}"
            items = cats[cat]
            n_alerte = sum(1 for l in items if l.alerte)
            n_cmd = sum(1 for l in items if l.a_commander)
            ouvert = tout_ouvrir or ouverts is None or cid in ouverts
            values = [""] * len(items[0].values)
            if colonne_resume is not None:
                n = len(items)
                if n_cmd:
                    resume = f"▲ {n_cmd}/{n} à commander"
                elif n_alerte:
                    resume = f"⚠ {n_alerte}/{n} à traiter"
                elif hors:
                    resume = f"{n} article{'s' if n > 1 else ''}"
                else:
                    resume = f"✓ {n}/{n} conformes"
                values[colonne_resume] = resume
            tag = "categorie_hors" if hors else ("categorie_alerte" if n_alerte else "categorie")
            tv.insert(gid, "end", iid=cid, text=cat, open=ouvert, values=values, tags=(tag,))
            for l in items:
                tv.insert(cid, "end", iid=l.iid, text=l.texte, values=l.values, tags=tuple(l.tags),
                          open=bool(ouverts and l.iid in ouverts))
                for enf in l.enfants:
                    tv.insert(l.iid, "end", iid=enf.iid, text=enf.texte, values=enf.values, tags=tuple(enf.tags))
    maj_marqueurs(tv)


class Dialogue(Toplevel):
    """Boîte de dialogue à champs. ``attendre()`` -> True / False / "supprimer".

    Chaque champ : (libellé, clé, valeur) pour une zone de texte, ou
    (libellé, clé, valeur, choix, modifiable) pour une liste déroulante.
    """

    def __init__(self, parent, titre: str):
        super().__init__(parent)
        self.title(titre)
        self.transient(parent)
        self.resizable(False, False)
        self.resultat = False
        self.vars: Dict[str, StringVar] = {}
        self.corps = ttk.Frame(self, padding=16)
        self.corps.pack(fill="both", expand=True)
        self.boutons = ttk.Frame(self, padding=(16, 0, 16, 16))
        self.boutons.pack(fill="x")
        self.bind("<Escape>", lambda *_: self._fermer(False))

    def champs(self, spec, bouton_supprimer: bool = False) -> Dict[str, StringVar]:
        for i, champ in enumerate(spec):
            lib, cle, val = champ[:3]
            ttk.Label(self.corps, text=lib).grid(row=i, column=0, sticky="w", pady=4, padx=(0, 12))
            v = StringVar(value=val)
            if len(champ) > 3:
                w = ttk.Combobox(self.corps, textvariable=v, values=list(champ[3]), width=42,
                                 state="normal" if (len(champ) < 5 or champ[4]) else "readonly")
            else:
                w = ttk.Entry(self.corps, textvariable=v, width=44)
            w.grid(row=i, column=1, sticky="ew", pady=4)
            if i == 0:
                w.focus_set()
                if isinstance(w, ttk.Entry):
                    w.select_range(0, "end")
            self.vars[cle] = v
        ttk.Button(self.boutons, text="Valider", style="Accent.TButton", command=lambda: self._fermer(True)).pack(side="right", padx=4)
        ttk.Button(self.boutons, text="Annuler", command=lambda: self._fermer(False)).pack(side="right")
        if bouton_supprimer:
            ttk.Button(self.boutons, text="Retirer la boîte", command=lambda: self._fermer("supprimer")).pack(side="left")
        self.bind("<Return>", lambda *_: self._fermer(True))
        return self.vars

    def note(self, texte: str, alerte: bool = False) -> None:
        """Ligne d'information sous les champs."""
        ligne = len(self.corps.grid_slaves(column=0)) + 1
        fixe(tk.Label(self.corps, text=texte, justify="left", wraplength=520, font=(POLICE, 9), padx=8, pady=5),
             bg="#fff4d6" if alerte else "#eef3f9", fg="#7a4b00" if alerte else "#33475b"
             ).grid(row=ligne, column=0, columnspan=2, sticky="ew", pady=(6, 0))

    def _fermer(self, res):
        self.resultat = res
        self.grab_release()
        self.destroy()

    def attendre(self):
        self.update_idletasks()
        px, py = self.master.winfo_rootx(), self.master.winfo_rooty()
        self.geometry(f"+{px + 260}+{py + 180}")
        self.grab_set()
        self.wait_window()
        return self.resultat


def afficher_fichier(parent, titre: str, chemin: Path) -> None:
    """Affiche un fichier texte du programme (LICENSE, NOTICE) dans une fenêtre modale, avec défilement.
    Ces fichiers n'ont pas d'extension : os.startfile ouvrirait le choix d'application de Windows."""
    try:
        texte = chemin.read_text(encoding="utf-8", errors="replace")
    except OSError:
        texte = (f"Fichier {chemin.name} introuvable à côté du programme.\n\n"
                 f"Il est consultable sur {URL_DEPOT}/blob/main/{chemin.name}")
    fen = Toplevel(parent)
    fen.title(titre)
    fen.transient(parent)
    cadre = ttk.Frame(fen, padding=(12, 12, 12, 0))
    cadre.pack(fill="both", expand=True)
    zone = fixe(tk.Text(cadre, wrap="word", width=124, height=32, font=("Consolas", 10), padx=10, pady=8,
                        relief="flat", bd=0), bg="white", fg="#222")
    sb = ttk.Scrollbar(cadre, orient="vertical", command=zone.yview)
    zone.configure(yscrollcommand=sb.set)
    zone.insert("1.0", texte)
    zone.configure(state="disabled")
    zone.pack(side="left", fill="both", expand=True)
    sb.pack(side="right", fill="y")
    bas = ttk.Frame(fen, padding=12)
    bas.pack(fill="x")

    def fermer(*_):
        fen.grab_release()
        fen.destroy()

    ttk.Button(bas, text="Fermer", style="Accent.TButton", command=fermer).pack(side="right")
    fen.bind("<Escape>", fermer)
    fen.protocol("WM_DELETE_WINDOW", fermer)
    fen.update_idletasks()
    fen.geometry(f"+{max(parent.winfo_rootx() - 120, 0)}+{max(parent.winfo_rooty() - 120, 0)}")
    fen.grab_set()
    zone.focus_set()
    fen.wait_window()
    try:
        parent.grab_set()   # la fenêtre « À propos » redevient modale
    except tk.TclError:
        pass


def lancer(chemin_db: Optional[str] = None):
    app = Application(Path(chemin_db) if chemin_db else DB_FILE)
    app.mainloop()
