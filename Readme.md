# Mandelbulb

Générateur de fractales **Mandelbulb 3D** pour Blender 5.1.

Cette extension permet de créer et d'explorer des fractales Mandelbulb et Julia directement dans Blender. La géométrie est générée à partir d'un **Signed Distance Field (SDF)** évalué avec NumPy puis converti en maillage grâce à un algorithme **Surface Nets**.

---

## Fonctionnalités

* Génération de fractales Mandelbulb 3D
* Support du mode Julia
* Paramètre de puissance entièrement animable
* Distorsions par décalage et torsion
* Extraction de surface via Surface Nets
* Mise à jour automatique lors de la modification des paramètres
* Support de l'animation par images clés
* Compatible Blender 5.1+

---

## Utilisation

### Création d'un Mandelbulb

1. Ouvrir l'onglet **Mandelbulb** dans la Vue 3D.
2. Cliquer sur **Ajouter Mandelbulb**.
3. Ajuster les paramètres selon le résultat souhaité.

Le maillage est automatiquement régénéré lorsque les paramètres changent.

---

## Paramètres

### Grille SDF

#### Résolution

Nombre de voxels utilisés pour évaluer la fractale.

Valeurs recommandées :

* 32 : aperçu rapide
* 64 : qualité moyenne
* 128 : haute qualité
* 256 : très haute qualité

Une résolution plus élevée produit davantage de détails mais augmente fortement le temps de calcul.

#### Taille grille

Détermine la zone de l'espace explorée autour de l'origine.

---

### Formule Mandelbulb

#### Puissance

Exposant de la formule White-Nylander.

Exemples :

* 2 : formes proches du Mandelbrot tridimensionnel
* 8 : Mandelbulb classique
* valeurs non entières : formes expérimentales

#### Itérations max

Nombre maximal d'itérations utilisées pour tester l'appartenance à l'ensemble.

Des valeurs plus élevées permettent de révéler davantage de détails.

#### Rayon d'échappement

Distance à partir de laquelle un point est considéré comme divergent.

La valeur classique est :

* 2.0

---

### Mode Julia

Permet de générer une fractale de Julia 3D.

Lorsque le mode Julia est activé :

* la constante **c** devient fixe ;
* la valeur **Julia C** contrôle la forme de la fractale.

---

### Distorsion

#### Décalage

Translate les coordonnées évaluées avant le calcul de la fractale.

Permet d'explorer différentes régions de l'espace fractal.

#### Torsion

Ajoute une rotation progressive à chaque itération.

Peut produire des formes hélicoïdales ou torsadées.

---

### Surface Nets

#### Normales lissées

Active le lissage des faces du maillage généré.

#### Niveau iso

Détermine le niveau d'extraction de l'isosurface.

* 0.0 : surface théorique
* valeur positive : surface dilatée
* valeur négative : surface contractée

---

## Animation

Tous les paramètres peuvent être animés à l'aide d'images clés Blender.

Exemples :

* animation de la puissance
* transition entre différentes fractales Julia
* variation progressive du niveau iso
* effets de torsion dynamiques

L'extension régénère automatiquement les objets Mandelbulb à chaque changement de frame.

---

## Fonctionnement interne

Le pipeline de génération est le suivant :

1. Création d'une grille volumique régulière.
2. Évaluation vectorisée de la distance signée (SDF) avec NumPy.
3. Calcul de la fractale Mandelbulb à l'aide de la formule de White-Nylander.
4. Estimation de distance selon la méthode de Hubbard-Douady.
5. Extraction de l'isosurface via Surface Nets.
6. Génération du maillage Blender.

Cette approche produit des surfaces plus lisses et plus précises qu'une simple voxelisation.

---

## Dépendances

* Blender 5.1 ou supérieur
* NumPy (fourni avec Blender)

Aucune dépendance externe supplémentaire n'est requise.

---

## Licence

Distribué sous licence GPL 3.0 ou ultérieure.
