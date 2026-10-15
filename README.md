<div align="center">

# Pharma Bord — gestion du stock médical du bord

**Le stock de médicaments et de matériel médical d'un navire sous pavillon français, suivi au regard de la dotation réglementaire de la Division 217.**

![Version](https://img.shields.io/badge/version-1.1.0-2ea44f)
![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)
![tkinter](https://img.shields.io/badge/interface-tkinter-3776AB)
![SQLite](https://img.shields.io/badge/SQLite-base%20locale-003B57?logo=sqlite&logoColor=white)
![Plateforme](https://img.shields.io/badge/plateforme-Windows-0078D6?logo=windows&logoColor=white)
![Licence](https://img.shields.io/badge/licence-GPL--3.0--or--later-blue)

</div>

**Français** · [English](README.en.md)

---

> [!WARNING]
> **Une aide à la gestion, fournie sans aucune garantie.** Pharma Bord ne remplace ni les registres officiels
> tenus à bord (registre papier des stupéfiants notamment), ni le contrôle annuel de la dotation, ni l'avis d'un
> médecin ou d'un pharmacien. Vérifiez toujours les quantités exigées au regard du texte officiel : le référentiel
> suit l'arrêté du 30 septembre 2021, dans sa version en vigueur vérifiée sur Légifrance le 24/09/2026.
> Le programme ne demande ni ne conserve aucune donnée patient.

Pharma Bord est un programme local (Python, sans serveur, sans connexion internet) pour gérer le stock de
médicaments et de matériel médical d'un navire sous pavillon français, au regard de la dotation réglementaire de la
**Division 217** (règlement annexé à l'arrêté du 23 novembre 1987), annexes 217-3.A.1 à 217-3.A.4 dans leur
rédaction issue de l'arrêté du 30 septembre 2021 (JORF du 16 octobre 2021).

**À qui ça sert.** Au capitaine et au responsable des soins à bord, qui tiennent la dotation médicale du navire et
préparent la commande de renouvellement à l'escale. Le programme fait de la **gestion de stock** : il ne remplace
pas les registres tenus à bord (registre papier des stupéfiants notamment) et ne conserve aucune donnée patient.

Version actuelle : 1.1.0 — l'historique des livraisons est sur la page des
[versions publiées](https://github.com/theptitprince/Pharma-bord/releases).

## Sommaire
- [1. Installation](#1-installation)
- [2. Les fichiers](#2-les-fichiers)
- [3. Lancement](#3-lancement)
- [4. Données](#4-données)
- [5. Ce que fait le programme](#5-ce-que-fait-le-programme)
- [6. Utilisation](#6-utilisation)
- [7. Le référentiel réglementaire](#7-le-référentiel-réglementaire)
- [8. Règles de calcul appliquées](#8-règles-de-calcul-appliquées)
- [9. Limites](#9-limites)
- [10. Licence](#10-licence)

---

## 1. Installation

### Python

Il faut **Python 3.10 ou plus récent**, avec **tkinter** (inclus dans l'installateur Windows).

### Récupérer le programme

Au choix :

- bouton vert **Code → Download ZIP** sur la page GitHub du dépôt, puis décompressez l'archive dans un dossier ;
- ou, si vous avez git :

```powershell
git clone https://github.com/theptitprince/Pharma-bord.git
```

### Les bibliothèques

Dans le dossier du programme :

```powershell
pip install -r requirements.txt
```

`sv-ttk` donne l'aspect Windows 11 ; `openpyxl` sert à l'export Excel de l'inventaire. Sans eux, le programme
fonctionne avec le thème Windows standard et sans export Excel.

Le lanceur `Pharma_Bord.bat` (section 3) fait cette installation tout seul si l'une des deux bibliothèques manque.

## 2. Les fichiers

| Fichier | Rôle |
|---|---|
| `main.py` | point d'entrée : ouvre l'interface graphique ; option `--db` pour choisir le fichier de base, `--version` pour afficher la version et la licence |
| `Pharma_Bord.bat` | lanceur Windows : installe les bibliothèques si besoin, puis lance le programme sans fenêtre de console |
| `requirements.txt` | bibliothèques facultatives : `openpyxl` (3.1 ou plus) et `sv-ttk` (2.6 ou plus) |
| `pharma_bord/gui.py` | l'interface (tkinter) |
| `pharma_bord/moteur.py` | le calcul : dotation exigée, état du stock, commande à passer |
| `pharma_bord/db.py` | le stockage local (SQLite) : configuration du navire, boîtes en stock, historique des mouvements |
| `pharma_bord/referentiel.py` | le chargement du référentiel ; la documentation en tête du fichier décrit le format des fichiers JSON |
| `pharma_bord/export.py` | les exports : bon de commande officiel (HTML), commande (CSV), inventaire (CSV, Excel), historique (CSV) |
| `pharma_bord/__init__.py` | le numéro de version du programme, la mention d'auteur et les textes de la fenêtre « À propos » |
| `referentiel/` | un fichier JSON par dotation, transcription de la Division 217 (section 7) |
| `LICENSE` | le texte de la licence GNU GPL v3 (section 10) |
| `NOTICE` | les conditions additionnelles de la licence (article 7) : la mention à conserver |

## 3. Lancement

Dans le dossier du programme :

```powershell
python main.py
```

Sous Windows, vous pouvez aussi double-cliquer sur `Pharma_Bord.bat`. Un fichier de base `pharma_bord.db` est créé
à côté du programme (un fichier = un navire). Pour un autre navire :

```powershell
python main.py --db autre.db
```

Le chemin de la base ouverte est affiché dans l'onglet *Navire & dotation*, à côté du bouton *Enregistrer et
recalculer la dotation exigée*.

`python main.py --version` affiche la version, la mention d'auteur et la licence, sans ouvrir la fenêtre.

## 4. Données

Aucune donnée de navire n'est fournie dans ce dépôt. La base `pharma_bord.db` est créée au premier lancement et
reste sur votre poste ; elle est exclue du suivi git, comme les exports (bons de commande, inventaires).

Le bon de commande ouvert par *Imprimer le bon de commande officiel* est écrit dans le dossier temporaire de Windows
(`%TEMP%\pharma_bord\`) ; les autres exports sont enregistrés à l'endroit que vous choisissez.

## 5. Ce que fait le programme

* il connaît les dotations réglementaires selon la zone de navigation choisie : **A**, **B**, **B restreinte**,
  **C**, **C restreinte**, **5e catégorie**, compléments passagers **P1 à P4**, **sac médical d'urgence**,
  **trousse plongée** ; il applique les règles annexes (coefficient d'effectif de la dotation A, antipaludéens en
  zone à risque, trousses de premiers secours selon équipage et passagers, DAE, dessertes courtes, navires de
  pêche…) ;
* il gère l'inventaire avec **plusieurs boîtes par article**, chacune avec sa quantité, sa péremption, son n° de
  lot, sa spécialité et son emplacement ;
* il suit des **articles hors dotation** (antidotes, consignes de l'armement…) rangés par sous-catégorie ;
* il calcule, pour un **délai ou une date de fin de traversée**, ce qu'il faut **commander à la prochaine escale** :
  quantité réglementaire − stock encore valide à cette date (plus une marge de sécurité) ;
* il imprime le **bon de commande officiel** (modèle de l'annexe 217-3.A.5), prêt à signer et tamponner ;
* il garde l'**historique des mouvements** : entrées, distributions, débarquements pour péremption, casse,
  corrections.

## 6. Utilisation

La fenêtre est organisée en cinq onglets, sous un bandeau d'en-tête qui résume le navire, la dotation, l'horizon de
couverture et l'état du stock. Le bandeau porte aussi le bouton *À propos…* et la mention
« Pharma Bord, par ETDEL — https://github.com/theptitprince/Pharma-bord ».

### Navire & dotation

Renseignez le navire, l'armement, la pharmacie, l'effectif, la dotation de base, le complément passagers et les
options, puis cliquez sur *Enregistrer et recalculer la dotation exigée*.

### Inventaire

L'arbre range les articles en Médicaments / Matériel / Hors dotation → catégories de la réglementation → articles →
boîtes. Un clic sur un nom déplie ou replie.

* **Saisie directe** : un clic sur une case d'une boîte (quantité, péremption, n° de lot, spécialité, emplacement)
  ouvre la saisie ; **Tab** passe à la case suivante (**Maj+Tab** revient à la précédente), **Entrée** valide,
  **Échap** annule. La ligne « + Ajouter une boîte » crée une nouvelle boîte dès que la quantité est saisie. La
  péremption accepte `JJ/MM/AAAA` ou `MM/AAAA` (fin de mois).
* **Sortie** : distribution à bord, débarquement pour péremption, casse ou perte. Aucune donnée patient n'est
  demandée ni conservée. Pour un stupéfiant, le programme rappelle de reporter le mouvement dans le registre papier.
* **Hors dotation** : bouton *Nouvel article hors dotation*, avec une sous-catégorie et, si besoin, une quantité à
  détenir. Clic droit sur l'article pour le modifier ou le supprimer.
* Survoler une ligne affiche le détail : origine de la quantité exigée, stock valide, boîtes à remplacer. La légende
  sous l'arbre explique les couleurs.

### Commande escale

Indiquez le délai (en jours) ou la date de fin de traversée, et la marge sur les péremptions (par défaut 90 jours et
30 jours de marge), puis cliquez sur *Calculer la commande*.

Un clic sur la case « À commander » ajuste une quantité à la main (0 retire la ligne). Les couleurs distinguent les
quantités calculées, les articles commandés à la main alors que le calcul ne demande rien, les quantités modifiées
et les lignes retirées ; l'info-bulle explique chaque cas. Un clic droit sur une ligne permet aussi de modifier la
quantité, de revenir à la quantité calculée ou de retirer la ligne ; *Annuler tous les ajustements manuels* revient
au calcul pour toute la commande.

Sous la commande, un cadre d'alertes liste les boîtes périmées ou qui expireront avant l'horizon, et les articles à
vérifier.

*Imprimer le bon de commande officiel* ouvre le bon dans le navigateur, cases modifiables avant impression. Les
autres boutons enregistrent le bon en HTML (*Bon complet (toute la dotation)* reprend aussi les articles sans
quantité à commander), la commande en CSV et l'inventaire en Excel ou en CSV. Le bandeau d'aide en haut du bon,
affiché à l'écran seulement, indique la version et la mention d'auteur ; il n'est pas imprimé, et le bon imprimé
reste conforme au modèle officiel.

### Historique

Tous les mouvements du stock, du plus récent au plus ancien (les 5 000 derniers au plus), avec une recherche et un
export CSV.

### Réglementation

Consultation des dotations transcrites (lecture seule).

### Fenêtre « À propos »

Le bouton *À propos…* du bandeau, ou la touche **F1**, ouvre la fenêtre « À propos » : version du programme, mention
d'auteur, copyright, licence (GPL v3 ou ultérieure, avec conditions additionnelles) et absence de garantie. Les
boutons *Lire la licence* et *Lire NOTICE* affichent le texte des fichiers `LICENSE` et `NOTICE`.

## 7. Le référentiel réglementaire

Le dossier `referentiel/` contient un fichier JSON par dotation : `Dotation_A.json`, `Dotation_B.json`,
`Dotation_B_restreinte.json`, `Dotation_C.json`, `Dotation_C_restreinte.json`, `Dotation_5e_categorie.json`,
`Complement_P1.json` à `Complement_P4.json`, `Sac_medical_urgence.json` et `Trousse_plongee.json`.

C'est une transcription de la Division 217 : il n'est **pas destiné à être modifié** par l'utilisateur. En cas de
nouveau texte, un développeur met à jour le fichier concerné (format décrit en tête de `pharma_bord/referentiel.py`) ;
un article est identifié par son type, sa dénomination et sa forme, qu'il faut garder identiques d'une dotation à
l'autre.

### Vérification

Le 24/09/2026, chaque annexe a été comparée ligne à ligne à la version en vigueur sur Légifrance (annexes
217-3.A.1, A.2, A.4 et A.7, toutes en vigueur depuis le 17/10/2021, sans modification depuis). Aucun écart de
quantité, aucun article manquant ou en trop.

### Écarts volontaires avec le texte publié

Le texte contient des coquilles ou des libellés différents d'une dotation à l'autre pour un même produit. Le
référentiel les harmonise, pour qu'un même produit soit reconnu dans toutes les dotations :

| Texte publié | Référentiel | Raison |
|---|---|---|
| P2 : métopimazine lyophilisat oral 4,5 mg | 7,5 mg | seul dosage existant, 7,5 mg partout ailleurs |
| Sérum physiologique « NaCl 9 % » | 0,9 % | coquille |
| Hexamidine-chlorhexidine-chlorocrésol « 0,5 ml » (B, BR, C, P2) | 0,5 mg | coquille, 0,5 mg en dotation A |
| Dexaméthasone-oxytétracycline « 1,333 mg » (A) | 1,335 mg | 1,335 mg en B et sur le bon de commande A |
| Acide borique « 12 mg/100 ml » (P2, CR) | 12 mg/ml | libellé des autres dotations |
| Mupirocine « crème » (B) | pommade | libellé de la dotation A |
| Amyléine-lévomenthol « 0,80 mg/0,4 ml » (B) | flacon 4 ml | libellé de la dotation A |
| Comprimés chlorés « 5 gr/l » (BR) | 5 mg/l | coquille, voir note 5 de l'annexe A.7 |
| Liste du kétoprofène LP (B, BR : I), de la terbutaline injectable (B : vide), du diazépam comprimé (C : vide) | II, I, I | valeurs des autres dotations et des bons de commande |

## 8. Règles de calcul appliquées

* **Dotation A** : quantités pour 25 marins ; +50 % par multiple entier de 25 au-delà du premier, deux dotations au
  maximum (coefficient 1,5 de 50 à 74 marins, 2 à partir de 75) ; −50 % si l'effectif est inférieur à 13 ; arrondi à
  l'entier supérieur ; les articles en exemplaire unique ne sont pas modifiés (annexe 217-3.A.7, note 1), ni le
  contenu des trousses (trousse de premiers secours…). Un coefficient manuel peut être imposé.
* **Dotations B, C (et leurs versions restreintes), 5e catégorie et compléments** : quantités fixes, additionnées à
  la dotation de base.
* **Sac médical d'urgence** : ses articles peuvent être prélevés sur la dotation du bord ; seul le complément
  manquant est exigé.
* **Horizon** : une boîte est valide si elle n'est pas périmée à la date de fin de traversée + marge ; à commander =
  exigé − stock valide.

## 9. Limites

* Le référentiel suit l'arrêté du 30 septembre 2021, version en vigueur vérifiée sur Légifrance le 24/09/2026. Tout
  texte postérieur doit être reporté dans les fichiers du dossier `referentiel/`.
* Non couverts : le nécessaire de première urgence des radeaux et embarcations (annexe 333-1.A.1) et la liste des
  antidotes du GSMU (à suivre en hors dotation).
* Le programme est une aide à la gestion ; il ne remplace ni les registres officiels ni le contrôle annuel de la
  dotation, ni l'avis d'un médecin ou d'un pharmacien. Il est fourni sans aucune garantie : vérifiez toujours les
  quantités exigées au regard du texte officiel.

## 10. Licence

Pharma Bord est un **logiciel libre**, distribué sous la licence **GNU General Public License, version 3 ou ultérieure**
(GPL-3.0-or-later).

Copyright © 2026 ETDEL.

Concrètement, vous pouvez utiliser le programme librement, l'étudier, le modifier et le redistribuer — à condition
que toute version redistribuée, modifiée ou non, reste sous la même licence, avec son code source et la mention de
copyright. Le programme est fourni **sans aucune garantie** : c'est une aide à la gestion du stock, qui ne remplace
ni les registres officiels, ni le contrôle annuel de la dotation, ni l'avis d'un médecin ou d'un pharmacien.

### Conditions additionnelles (article 7)

La GPL v3 permet à l'auteur d'ajouter quelques conditions (article 7). Celles de Pharma Bord sont dans
le fichier [`NOTICE`](NOTICE), en français et en anglais :

- **Attribution** : toute copie ou version modifiée doit garder, visible pour l'utilisateur
  (fenêtre « À propos » ou équivalent) et dans sa documentation, la mention :

  > Pharma Bord, par ETDEL — https://github.com/theptitprince/Pharma-bord

  Une version modifiée peut la faire précéder de « D'après » et ajouter ses propres crédits,
  sans la retirer ni la masquer.
- **Origine** : une version modifiée doit dire clairement qu'elle est modifiée, et ne doit se
  présenter ni comme l'original, ni comme approuvée par ETDEL.

Dans Pharma Bord, cette mention s'affiche dans le bandeau d'en-tête et dans la fenêtre « À propos » (bouton du
bandeau ou touche F1).

Le texte intégral de la licence est dans le fichier `LICENSE` du dépôt et sur
<https://www.gnu.org/licenses/gpl-3.0.html>. Chaque fichier source (`main.py`, les modules de `pharma_bord/` et le
lanceur `Pharma_Bord.bat`) porte un en-tête qui renvoie à `LICENSE` et `NOTICE`.

La licence porte sur le code du programme. Les textes réglementaires transcrits dans le dossier `referentiel/` sont
des textes officiels publiés au Journal officiel, et le bon de commande imprimé suit le modèle officiel de l'annexe
217-3.A.5 : les conditions additionnelles ne s'y appliquent pas.

---

*Pharma Bord — ETDEL 2026 — GPL-3.0-or-later*
