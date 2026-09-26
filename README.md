# Pharma Bord – gestion du stock médical du bord

Programme local (Python, sans serveur, sans connexion internet) pour gérer le stock de
médicaments et de matériel médical d'un navire sous pavillon français, au regard
de la dotation réglementaire de la **Division 217** (règlement annexé à l'arrêté du
23 novembre 1987), annexes 217-3.A.1 à 217-3.A.4 dans leur rédaction issue de
l'arrêté du 30 septembre 2021 (JORF du 16 octobre 2021).

Le programme fait de la **gestion de stock** : il ne remplace pas les registres
tenus à bord (registre papier des stupéfiants notamment) et ne conserve aucune
donnée patient.

## Ce que fait le programme

* connaît les dotations réglementaires selon la zone de navigation choisie :
  **A**, **B**, **B restreinte**, **C**, **C restreinte**, **5e catégorie**,
  compléments passagers **P1 à P4**, **sac médical d'urgence**, **trousse
  plongée** ; applique les règles annexes (coefficient d'effectif de la dotation A,
  antipaludéens en zone à risque, trousses de premiers secours selon équipage et
  passagers, DAE, dessertes courtes, navires de pêche…) ;
* gère l'inventaire avec **plusieurs boîtes par article**, chacune avec sa
  quantité, sa péremption, son n° de lot, sa spécialité et son emplacement ;
* suit des **articles hors dotation** (antidotes, consignes de l'armement…)
  rangés par sous-catégorie ;
* calcule, pour un **délai ou une date de fin de traversée**, ce qu'il faut
  **commander à la prochaine escale** : quantité réglementaire − stock encore
  valide à cette date (plus une marge de sécurité) ;
* imprime le **bon de commande officiel** (modèle de l'annexe 217-3.A.5), prêt à
  signer et tamponner ;
* garde l'**historique des mouvements** : entrées, distributions, débarquements
  pour péremption, casse, corrections.

## Installation

Python 3.10 ou plus récent, avec tkinter (inclus dans l'installateur Windows).

```bash
pip install -r requirements.txt
```

`sv-ttk` donne l'aspect Windows 11 ; `openpyxl` sert à l'export Excel de
l'inventaire. Sans eux, le programme fonctionne avec le thème Windows standard et
sans export Excel.

Lancement :

```bash
python main.py
```

Sous Windows, double-cliquer sur `Pharma_Bord.bat`. Un fichier de base
`pharma_bord.db` est créé à côté du programme (un fichier = un navire ;
`python main.py --db autre.db` pour un autre navire).

## Utilisation

1. **Navire & dotation** : navire, armement, pharmacie, effectif, dotation de base,
   complément passagers et options, puis *Enregistrer et recalculer*.
2. **Inventaire** : arbre Médicaments / Matériel / Hors dotation → catégories de la
   réglementation → articles → boîtes. Un clic sur un nom déplie ou replie.
   * **Saisie directe** : un clic sur une case d'une boîte (quantité, péremption,
     n° de lot, spécialité, emplacement) ouvre la saisie ; **Tab** passe à la case
     suivante, **Entrée** valide, **Échap** annule. La ligne « + Ajouter une
     boîte » crée une nouvelle boîte dès que la quantité est saisie. La péremption
     accepte `JJ/MM/AAAA` ou `MM/AAAA` (fin de mois).
   * **Sortie** : distribution à bord, débarquement pour péremption, casse ou perte.
     Aucune donnée patient n'est demandée ni conservée. Pour un stupéfiant, le
     programme rappelle de reporter le mouvement dans le registre papier.
   * **Hors dotation** : bouton *Nouvel article hors dotation*, avec une
     sous-catégorie et, si besoin, une quantité à détenir. Clic droit sur l'article
     pour le modifier ou le supprimer.
   * Survoler une ligne affiche le détail : origine de la quantité exigée, stock
     valide, boîtes à remplacer. La légende sous l'arbre explique les couleurs.
3. **Commande escale** : délai (jours) ou date de fin de traversée, marge sur les
   péremptions, puis *Calculer*. Un clic sur « À commander » ajuste une quantité à
   la main. Les couleurs distinguent les quantités calculées, les articles commandés
   à la main alors que le calcul ne demande rien, les quantités modifiées et les
   lignes retirées ; l'info-bulle explique chaque cas. *Imprimer le bon de commande
   officiel* ouvre le bon dans le navigateur, cases modifiables avant impression.
4. **Historique** : tous les mouvements du stock, export CSV.
5. **Réglementation** : consultation des dotations transcrites.

## Le référentiel réglementaire

Le dossier `referentiel/` contient un fichier JSON par dotation
(`Dotation_A.json`, `Complement_P2.json`, `Sac_medical_urgence.json`…). C'est une
transcription de la Division 217 : il n'est **pas destiné à être modifié** par
l'utilisateur. En cas de nouveau texte, un développeur met à jour le fichier concerné
(format décrit en tête de `pharma_bord/referentiel.py`) ; un article est identifié
par son type, sa dénomination et sa forme, qu'il faut garder identiques d'une
dotation à l'autre.

**Vérification** : le 24/09/2026, chaque annexe a été comparée ligne à ligne à la
version en vigueur sur Légifrance (annexes 217-3.A.1, A.2, A.4 et A.7, toutes en
vigueur depuis le 17/10/2021, sans modification depuis). Aucun écart de quantité,
aucun article manquant ou en trop.

**Écarts volontaires avec le texte publié** : le texte contient des coquilles ou des
libellés différents d'une dotation à l'autre pour un même produit. Le référentiel les
harmonise, pour qu'un même produit soit reconnu dans toutes les dotations :

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

## Règles de calcul appliquées

* **Dotation A** : quantités pour 25 marins ; +50 % par multiple entier de 25
  (deux dotations au maximum), −50 % si l'effectif est inférieur à 13 ; arrondi à
  l'entier supérieur ; les articles en exemplaire unique ne sont pas modifiés
  (annexe 217-3.A.7, note 1). Un coefficient manuel peut être imposé.
* Dotations B, C, 5e catégorie et compléments : quantités fixes, additionnées à la
  dotation de base.
* **Sac médical d'urgence** : ses articles peuvent être prélevés sur la dotation du
  bord ; seul le complément manquant est exigé.
* **Horizon** : une boîte est valide si elle n'est pas périmée à la date de fin de
  traversée + marge ; à commander = exigé − stock valide.

## Tests

```bash
python -m unittest discover -s tests -v
```

## Limites

* Le référentiel suit l'arrêté du 30 septembre 2021, version en vigueur vérifiée sur
  Légifrance le 24/09/2026. Tout texte postérieur doit être reporté dans les fichiers
  du dossier `referentiel/`.
* Non couverts : le nécessaire de première urgence des radeaux et embarcations
  (annexe 333-1.A.1) et la liste des antidotes du GSMU (à suivre en hors dotation).
* Le programme est une aide à la gestion ; il ne remplace ni les registres
  officiels ni le contrôle annuel de la dotation, ni l'avis d'un médecin ou d'un
  pharmacien. Il est fourni sans aucune garantie : vérifiez toujours les quantités
  exigées au regard du texte officiel.

## Données

Aucune donnée de navire n'est fournie dans ce dépôt. La base `pharma_bord.db` est
créée au premier lancement et reste sur votre poste ; elle est exclue du suivi git,
comme les exports (bons de commande, inventaires).

## Licence

Code distribué sous licence GNU GPL v3 (voir `LICENSE`). Les textes réglementaires
transcrits dans `referentiel/` sont des textes officiels publiés au Journal officiel.
