<div align="center">

# Pharma Bord — managing the ship's medical stock

**The stock of medicines and medical equipment of a French-flagged ship, tracked against the regulatory allowance of Division 217.**

![Version](https://img.shields.io/badge/version-1.1.0-2ea44f)
![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)
![tkinter](https://img.shields.io/badge/interface-tkinter-3776AB)
![SQLite](https://img.shields.io/badge/SQLite-local%20database-003B57?logo=sqlite&logoColor=white)
![Platform](https://img.shields.io/badge/platform-Windows-0078D6?logo=windows&logoColor=white)
![License](https://img.shields.io/badge/license-GPL--3.0--or--later-blue)

</div>

[Français](README.md) · **English**

> The program's interface is in French; its labels are quoted below as they appear on screen.

---

> [!WARNING]
> **A management aid, provided without any warranty.** Pharma Bord does not replace the official registers kept
> on board (in particular the paper controlled-drugs register), the annual inspection of the allowance, or the advice
> of a doctor or a pharmacist. Always check the required quantities against the official text: the reference data
> follows the order of 30 September 2021, in the version in force as checked on Légifrance on 24 September 2026.
> The program neither asks for nor stores any patient data.

Pharma Bord is a local program (Python, no server, no internet connection) for managing the stock of medicines and
medical equipment of a French-flagged ship against the regulatory allowance of **Division 217** (regulation annexed
to the order of 23 November 1987), annexes 217-3.A.1 to 217-3.A.4 as worded by the order of 30 September 2021
(JORF of 16 October 2021).

**Who it is for.** The master and the person in charge of medical care on board, who keep the ship's medical
allowance and prepare the replenishment order for the port call. The program does **stock management**: it does not
replace the registers kept on board (in particular the paper controlled-drugs register) and stores no patient data.

Current version: 1.1.0 — the release history is on the
[published releases](https://github.com/theptitprince/Pharma-bord/releases) page.

## Contents
- [1. Installation](#1-installation)
- [2. Files](#2-files)
- [3. Running the program](#3-running-the-program)
- [4. Data](#4-data)
- [5. What the program does](#5-what-the-program-does)
- [6. Usage](#6-usage)
- [7. The regulatory reference data](#7-the-regulatory-reference-data)
- [8. Calculation rules applied](#8-calculation-rules-applied)
- [9. Limitations](#9-limitations)
- [10. License](#10-license)

---

## 1. Installation

### Python

You need **Python 3.10 or later**, with **tkinter** (included in the Windows installer).

### Getting the program

Either:

- the green **Code → Download ZIP** button on the repository's GitHub page, then unzip the archive into a folder;
- or, if you have git:

```powershell
git clone https://github.com/theptitprince/Pharma-bord.git
```

### Libraries

In the program folder:

```powershell
pip install -r requirements.txt
```

`sv-ttk` gives the Windows 11 look; `openpyxl` is used for the Excel export of the inventory. Without them, the
program works with the standard Windows theme and without Excel export.

The `Pharma_Bord.bat` launcher (section 3) does this installation by itself if either of the two libraries is missing.

## 2. Files

| File | Role |
|---|---|
| `main.py` | entry point: opens the graphical interface; `--db` option to choose the database file, `--version` to show the version and the license |
| `Pharma_Bord.bat` | Windows launcher: installs the libraries if needed, then starts the program without a console window |
| `requirements.txt` | optional libraries: `openpyxl` (3.1 or later) and `sv-ttk` (2.6 or later) |
| `pharma_bord/gui.py` | the interface (tkinter) |
| `pharma_bord/moteur.py` | the calculation: required allowance, stock status, order to place |
| `pharma_bord/db.py` | local storage (SQLite): ship configuration, boxes in stock, movement history |
| `pharma_bord/referentiel.py` | loading of the reference data; the documentation at the top of the file describes the format of the JSON files |
| `pharma_bord/export.py` | the exports: official order form (HTML), order (CSV), inventory (CSV, Excel), history (CSV) |
| `pharma_bord/__init__.py` | the program's version number, the author notice and the texts of the « À propos » (about) window |
| `referentiel/` | one JSON file per allowance, a transcription of Division 217 (section 7) |
| `LICENSE` | the text of the GNU GPL v3 license (section 10) |
| `NOTICE` | the additional license terms (section 7): the notice to keep |

## 3. Running the program

In the program folder:

```powershell
python main.py
```

On Windows, you can also double-click `Pharma_Bord.bat`. A database file `pharma_bord.db` is created next to the
program (one file = one ship). For another ship:

```powershell
python main.py --db autre.db
```

The path of the open database is shown in the *Navire & dotation* (ship & allowance) tab, next to the
*Enregistrer et recalculer la dotation exigée* (save and recalculate the required allowance) button.

`python main.py --version` shows the version, the author notice and the license, without opening the window.

## 4. Data

No ship data is provided in this repository. The `pharma_bord.db` database is created at first launch and stays on
your computer; it is excluded from git tracking, as are the exports (order forms, inventories).

The order form opened by *Imprimer le bon de commande officiel* (print the official order form) is written to the
Windows temporary folder (`%TEMP%\pharma_bord\`); the other exports are saved wherever you choose.

## 5. What the program does

* it knows the regulatory allowances for the chosen navigation area: **A**, **B**, **B restreinte** (B restricted),
  **C**, **C restreinte** (C restricted), **5e catégorie** (5th category), passenger supplements **P1 to P4**,
  **sac médical d'urgence** (emergency medical bag), **trousse plongée** (diving kit); it applies the additional
  rules (crew-size coefficient of allowance A, antimalarials in a risk area, first-aid kits according to crew and
  passengers, AED, short routes, fishing vessels…);
* it manages the inventory with **several boxes per item**, each with its own quantity, expiry date, batch number,
  brand name and storage location;
* it tracks **hors dotation** items (outside the allowance: antidotes, shipowner's instructions…), sorted by
  subcategory;
* it calculates, for a **number of days or an end-of-voyage date**, what needs to be **ordered at the next port
  call**: regulatory quantity − stock still valid on that date (plus a safety margin);
* it prints the **official order form** (template from annex 217-3.A.5), ready to be signed and stamped;
* it keeps the **movement history**: receipts, dispensing, offloading of expired stock, breakage, corrections.

## 6. Usage

The window is organized in five tabs, below a header banner that sums up the ship, the allowance, the coverage
horizon and the state of the stock. The banner also carries the *À propos…* (about) button and the notice
"Pharma Bord, par ETDEL — https://github.com/theptitprince/Pharma-bord".

### Navire & dotation (ship & allowance)

Fill in the ship, the shipowner, the pharmacy, the crew size, the base allowance, the passenger supplement and the
options, then click *Enregistrer et recalculer la dotation exigée*.

### Inventaire (inventory)

The tree sorts the items into Médicaments / Matériel / Hors dotation (medicines / equipment / outside the allowance)
→ categories of the regulations → items → boxes. Clicking a name expands or collapses it.

* **Direct entry**: clicking a cell of a box (quantity, expiry date, batch number, brand name, location) opens it
  for editing; **Tab** moves to the next cell (**Shift+Tab** goes back to the previous one), **Enter** confirms,
  **Esc** cancels. The "+ Ajouter une boîte" (add a box) row creates a new box as soon as the quantity is entered.
  The expiry date accepts `JJ/MM/AAAA` (day/month/year) or `MM/AAAA` (end of month).
* **Sortie** (removal from stock): dispensing on board, offloading because expired, breakage or loss. No patient data is
  requested or stored. For a controlled drug, the program reminds you to record the movement in the paper register.
* **Hors dotation**: *Nouvel article hors dotation* (new item outside the allowance) button, with a subcategory and,
  if needed, a quantity to hold. Right-click the item to edit or delete it.
* Hovering over a row shows the details: origin of the required quantity, valid stock, boxes to replace. The legend
  below the tree explains the colors.

### Commande escale (port-call order)

Enter the number of days or the end-of-voyage date, and the margin on expiry dates (by default 90 days and a
30-day margin), then click *Calculer la commande* (calculate the order).

Clicking the "À commander" (to order) cell adjusts a quantity by hand (0 removes the row). The colors distinguish
calculated quantities, items ordered by hand although the calculation requires none, modified quantities and removed
rows; the tooltip explains each case. Right-clicking a row also lets you change the quantity, go back to the
calculated quantity or remove the row; *Annuler tous les ajustements manuels* (cancel all manual adjustments)
returns the whole order to the calculated values.

Below the order, an alerts frame lists the boxes that are expired or will expire before the horizon, and the items
to check.

*Imprimer le bon de commande officiel* opens the form in the browser, with fields you can edit before printing. The
other buttons save the form as HTML, the order as CSV and the inventory as Excel or CSV;
*Bon complet (toute la dotation)* (complete form, whole allowance) also includes the items with no quantity to order.
The help banner at the top of the form, shown on screen only, gives the version and the author notice; it is not
printed, and the printed form stays true to the official model.

### Historique (history)

All stock movements, from the most recent to the oldest (the latest 5,000 at most), with a search and a CSV export.

### Réglementation (regulations)

Browsing the transcribed allowances (read-only).

### « À propos » (about) window

The banner's *À propos…* button, or the **F1** key, opens the « À propos » window: program version, author notice,
copyright, license (GPL v3 or later, with additional terms) and absence of warranty. The *Lire la licence* (read the
license) and *Lire NOTICE* (read NOTICE) buttons show the text of the `LICENSE` and `NOTICE` files.

## 7. The regulatory reference data

The `referentiel/` folder contains one JSON file per allowance: `Dotation_A.json`, `Dotation_B.json`,
`Dotation_B_restreinte.json`, `Dotation_C.json`, `Dotation_C_restreinte.json`, `Dotation_5e_categorie.json`,
`Complement_P1.json` to `Complement_P4.json`, `Sac_medical_urgence.json` and `Trousse_plongee.json`.

It is a transcription of Division 217: it is **not meant to be modified** by the user. When a new text is published,
a developer updates the file concerned (format described at the top of `pharma_bord/referentiel.py`); an item is
identified by its type, its name and its form, which must be kept identical from one allowance to another.

### Verification

On 24 September 2026, each annex was compared line by line with the version in force on Légifrance (annexes
217-3.A.1, A.2, A.4 and A.7, all in force since 17 October 2021, unchanged since). No difference in quantity, no
missing or extra item.

### Deliberate differences from the published text

The text contains typos, or wordings that differ from one allowance to another for the same product. The reference
data harmonizes them, so that the same product is recognized in every allowance:

| Published text | Reference data | Reason |
|---|---|---|
| P2: metopimazine oral lyophilisate 4.5 mg | 7.5 mg | the only strength that exists, 7.5 mg everywhere else |
| Normal saline "NaCl 9%" | 0.9% | typo |
| Hexamidine-chlorhexidine-chlorocresol "0.5 ml" (B, BR, C, P2) | 0.5 mg | typo, 0.5 mg in allowance A |
| Dexamethasone-oxytetracycline "1.333 mg" (A) | 1.335 mg | 1.335 mg in B and on the allowance A order form |
| Boric acid "12 mg/100 ml" (P2, CR) | 12 mg/ml | wording of the other allowances |
| Mupirocin "cream" (B) | ointment | wording of allowance A |
| Amylocaine-levomenthol "0.80 mg/0.4 ml" (B) | 4 ml bottle | wording of allowance A |
| Chlorine tablets "5 gr/l" (BR) | 5 mg/l | typo, see note 5 of annex A.7 |
| Schedule (*liste*) of prolonged-release ketoprofen (B, BR: I), injectable terbutaline (B: blank), diazepam tablets (C: blank) | II, I, I | values of the other allowances and of the order forms |

## 8. Calculation rules applied

* **Allowance A**: quantities for 25 seafarers; +50% per whole multiple of 25 beyond the first, two allowances at
  most (coefficient 1.5 from 50 to 74 seafarers, 2 from 75); −50% if the crew is fewer than 13; rounded up to the
  next whole number; items held as a single unit are not changed (annex 217-3.A.7, note 1), nor are the contents of
  kits (first-aid kit…). A manual coefficient can be imposed.
* **Allowances B, C (and their restricted versions), 5e catégorie and supplements**: fixed quantities, added to the
  base allowance.
* **Sac médical d'urgence**: its items may be taken from the ship's allowance; only the missing balance is required.
* **Horizon**: a box is valid if it is not expired on the end-of-voyage date + margin; to order = required − valid
  stock.

## 9. Limitations

* The reference data follows the order of 30 September 2021, in the version in force as checked on Légifrance on
  24 September 2026. Any later text must be carried over into the files of the `referentiel/` folder.
* Not covered: the emergency first-aid kit of liferafts and lifeboats (annex 333-1.A.1) and the GSMU list of
  antidotes (to be tracked as hors dotation items).
* The program is a management aid; it does not replace the official registers, the annual inspection of the
  allowance, or the advice of a doctor or a pharmacist. It is provided without any warranty: always check the
  required quantities against the official text.

## 10. License

Pharma Bord is **free software**, distributed under the **GNU General Public License, version 3 or later**
(GPL-3.0-or-later).

Copyright © 2026 ETDEL.

In practical terms, you may use the program freely, study it, modify it and redistribute it — provided that any
redistributed version, modified or not, remains under the same license, with its source code and the copyright
notice. The program is provided **without any warranty**: it is an aid to managing the stock, which does not replace
the official registers, the annual inspection of the allowance, or the advice of a doctor or a pharmacist.

### Additional terms (section 7)

The GPL v3 lets the author add a few terms (section 7). Pharma Bord's are in the
[`NOTICE`](NOTICE) file, in French and in English:

- **Attribution**: every copy or modified version must keep, visible to the user (an "About"
  window or equivalent) and in its documentation, the notice:

  > Pharma Bord, par ETDEL — https://github.com/theptitprince/Pharma-bord

  A modified version may prefix it with "D'après" (or "Based on") and add its own credits,
  but may neither remove nor hide it.
- **Origin**: a modified version must state clearly that it has been modified, and must not
  present itself as the original or as endorsed by ETDEL.

In Pharma Bord, this notice is shown in the header banner and in the « À propos » (about) window (banner button or
F1 key).

The full text of the license is in the repository's `LICENSE` file and at
<https://www.gnu.org/licenses/gpl-3.0.html>. Each source file (`main.py`, the modules in `pharma_bord/` and the
`Pharma_Bord.bat` launcher) carries a header that points to `LICENSE` and `NOTICE`.

The license covers the program's code. The regulatory texts transcribed in the `referentiel/` folder are official
texts published in the French Official Journal (Journal officiel), and the printed order form follows the official
model of annex 217-3.A.5: the additional terms do not apply to them.

---

*Pharma Bord — ETDEL 2026 — GPL-3.0-or-later*
