# **Journal des additions / modifications du code**


## SEMAINE 1 : (16 Février)

- Préparation du github en commun, premiers commits
- Mise en place des environments de code


## SEMAINE 2: (23 Février)

- Compréhension du code de base fourni pour le projet (`gameview.py`, `main.py` et `constants.py`)
- Création d'une fenêtre du jeu de la bonne taille
- Dimensions de monde qui dépendent du nombre de tuiles (grids) au lieu des pixels
- Chargement du fichier assets, mise en place des premières textures simples dans le fichier `textures.py`
- Création des premiers Sprites: player, bush et ground, ainsi que les Spritelists qui les contiennent
- Peuplement d'une map (coordonnees tapées à la main dans le init de GameView) avec les 3 types de Sprites crées à l'aide de la méthode on_draw() de GameView


## SEMAINE 3: (2 Mars)

- Implémentation du déplacement du joueur (creation des methodes on_update(), on_key_press(), on_key_release() dans GameView)
- Utilisation du PhysicsEngineSimple d'Arcade pour gérér les collisions avec les obstacles (les buissons)
- Addition de la touche Echap dans la méthode on_key_press() pour réinitialiser le jeu
- Implémentation d'une texture animée pour le player (avec l'aide du code fourni pour `textures.py`)
- Ajout des cristaux, avec leur texture animée
- Mise en place de la méchanique pour ramasser les cristaux avec le joueur (avec la fonction d'Arcade check_for_collision_with_list())
- Création du dossier tests, avec le fichier `conftest.py` fourni et nos premières fonctions de test basiques
- Création de la classe GridCell et de la classe Map contenant des GridCells (nouveau fichier `map.py`)
- Refactoring de gameview: il accepte une Map pour peupler les sprites au lieu de tout faire individuellement


## SEMAINE 4: (9 Mars)

- Codage de méthodes statiques dans la classe Map pour parser un fichier texte en Map (dictionnaire symbol_to_gridcell pour "traduire" un fichier .txt)
- Changement d'architecture: Map construite à partir de tuples plutôt que des listes
- Utilisation de sets pour mieux gérér le mouvement du joueur + animation qui change en fonction de l'orientation et du mouvement dans `player.py`
- Mise en place des restrictions du bords de la map pour la caméra dans la méthode on_update() dand `gameview.py`
- Ajout de l'effet sonore quand un cristal est ramassé
- Additions pour perfectionner le mouvement du joueur (quand deux touches opposées sont appuyées en même temps ou quand le joueur longe un mur)
- Création des sprites Spinneur horizontal et Spinneur vertical (capables de tuer le joueur mais immobiles pour le moment) dans `monsters.py`
- Création du sprite Trou (visible, mais pas encore fonctionel)
- Création du fichier `player.py` qui gère l'entièreté du mouvement et de l'animation du joueur (GameView moins désordonné)


## SEMAINE 5: (16 Mars)

- Refactoring du mouvement du joueur à l'aide du dictionnaire DIRECTION_DATA
- Création du fichier `monsters.py` qui contient le code pour les classes SpinneurHorizontal et SpinneurVertical qui héritent de la classe Spinneur
- Addition de la méthode compute_spinner_bounds dans la classe Map et implémentation du mouvement des spinneurs (limités par les obstacles)
- Création du fichier `camera.py` pour gérér la position d'affichage (et simplifier GameView) et réécriture du code pour restreindre la vue aux bords de la map
- Ajout d'une deuxième caméra pour gérér le UI et implémentation d'un compteur pour les cristaux ramassés affiché sur celle-ci
- Écriture de handle_hole_collision() pour tuer le joueur s'il est à une distance 1/2tuile du centre
- Refactoring de GameView avec sa méthode handle_player_death() qui est appéllée dans tout les scénarios de mort du joueur
- Création du fichier `boomerang.py` et du sprite animé Boomerang
- Implémentation du lancer du boomerang dans une direction fixe (toujours vers la droite)
- Implémentation du lancer du boomerang pour toute les directions


## SEMAINE 6: (23 Mars)

- Refactoring: création du fichier `spritegroups.py` et de la classe SpriteGroups, qui contient toute les SpriteLists du jeu
- Réécriture de code plus clair pour la classe Boomerang, utilisations de dictionnaires (similaires à ceux du mouvement du joueur)
- Remplacement du fichier `boomerang.py` par le fichier `arme.py`, et rédaction partielle du code pour la classe Epee et la classe Arme (parent de Boomerang et Epee)
- Ajout des tests pour la classe Map
- Changement d'architecture: création du fichier `world_builder.py` qui gère l'initialisation du monde à partir d'une Map avec la classe WorldBuilder et qui stocke toute les infos du monde avec la classe LoadedWorld (simplification de GameView)
- Gestion des imports: chaque fichier importe uniquement ce dont il a besoin
- Réécriture de la classe Map pour une meilleure utilisation par WorldBuilder et une meilleure gestion de maps erronées + déplacement du code de calcul des bornes de Spinneur vers WorldBuilder
- Réécriture du fichier `camera.py`, classe Game_Camera et UI_Camera (qui gère tout l'affichage UI à la place de GameView)
- Ajout des tests pour la classe Boomerang


## SEMAINE 7: (30 Mars)

- Création du fichier DESIGN.md, explication de l'architecture du code
- Addition de la classe Bat dans le fichier `monsters.py`, et ses méthodes, notamment handle_direction_change() qui gère le mouvement aléaitoire et borné
- Ajout du code pour faire apparaitre les hitboxs dans `gameview.py``
- Factorisation en plus de constantes pour pouvoir modifier plus facilement les caractéristiques de gameplay
- Meilleure écriture du mouvement aléatoire des bats (utilisation de gaussienne pour réduire les changements extremes de direction)
- Fonctions de test pour `monsters.py` et réécriture de la classe parent Monster


## SEMAINE 8: (6 Avril)

- Aucune modifications (Vacances)


## SEMAINE 9: (13 Avril)

- Réécriture de la classe Bat pour d'avantage de flexibilité
- Addition de la classe Blob dans le fichier `monsters.py` (visble, mobile et mortel, mais ne poursuit pas encore le player)
- Factorisation du fichier `monsters.py`, classe parent Monster pour tout les sprites ennemis
- Réécriture de `DESIGN.md`, présentation plus claire et à jour


## SEMAINE 10: (20 Avril)

- Aucune modification (Midterm)


## SEMAINE 11: (27 Avril)

- Meilleur gestion des caméras: classe parent qui ne prend pas en attribut l'entièreté du world
- Ajout de l'icone (sprite) du cristal dans la UI_Camera
- Meilleure gestion des hitboxs pour l'épée dans `arme.py`(le joueur peut se faire tuer si l'épée n'est pas dans la direction de l'ennemi)
- Réglage d'un bug d'affichage dans `camera.py`qui arrivait quand une dimension de map est plus petite que la dimension max de la fenêtre
- Implémentation du comportement de poursuite du Blob quand il voit le player en ligne de vue
- Petites modifications au Gameview pour une meilleure gestion de donnéés
- Factorisation et meilleur typage dans le fichier `arme.py`


## SEMAINE 12: (4 Mai)

- Affichage des FPS dans la caméra UI (`camera.py`)
- Réécriture des calculs du navmesh pour réduire la complexité de calcul
- Ajout des leviers et des portails, création de `portail.py` et de la logique entourant ces deux objects
- Réécriture du parsing de la map avec Yaml safe load pour la première section du fichier .txt (section config)
- Déplacement du parsing de la config simple dans `map_config`, prêt pour implémenter la logique des portails et leviers
- Simplification du fichier `world_builder.py` avec moins d'importations d'autres fichiers


## SEMAINE 13: (11 Mai)

- Récriture légère de `arme.py` pour un meilleur comportement avec les leviers (Boomerang qui revient quand il est en contact avec un levier et Épée qui change le levier d'état que une fois par attaque, pas à chaque frame)
- Meilleure ecriture de `portail.py` ainsi que la méthode pour évaluer un arbre à conditions
- Ajout des sections de parsing pour levers et gates dans `map_config.py` ainsi qu'une gestion d'erreurs potentiels dans le fichier .txt
- Ecriture de la méthode UniqueKeyLoader qui surcharge la méthode de creation de dict de yaml afin de pouvoir raise les erreurs de clés doubles (`map_config.py`)
- Nouvelle classe parent pour couvrir les points communs des monstres et leviers (hittable)
- Meilleur typage dans le processing du yaml
- Implémentation de la barre de santé dans la caméra_Ui de `camera.py` qui permet le joueur de prendre des dégats sans mourir
- Finalisation de `map_config.py` qui gère toute les erreurs potentielles dans le chargement d'une map.txt
- Meilleure gestion du déplacement de portails fermés dans le physics engine dans `gameview.py`
- Mise en place de code pour pouvoir modifier la vitesse de passage des frames (vitesse de jeu)


## SEMAINE 14: (18 Mai)

- Aucune modification (Final)

## SEMAINE 15: (25 Mai)

- Implémentation du passage à une map suivante (systeme de niveaux), intégration dans la section config
- Optimisation et factorisation de `map_config.py` (parsage simplifié, utilisation de sets pour détecter les doublons)
- Ajout des random seed pour que les tests de Bats et Blob fonctionnent toujours
- Dernières fonctions tests
- Mise à jour du fichier `DESIGN.md`
- Écriture intégrale du `README.md`
