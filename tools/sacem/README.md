# Map de test SACEM (`sacem-test.tmj`)

Copie de test du campus, étendue de 60 à 108 tuiles de large, avec le bâtiment SACEM.
`map.tmj` (le campus en ligne) n'est pas touché : la map de test a ses propres copies de
tilesets dans `tilesets/sacem-test/` et son propre script `sacem-test.js`.

## Fichiers

| Fichier | Rôle |
|---|---|
| `sacem-test.tmj` | la map de test (générée, ne pas éditer à la main sauf collisions dans Tiled) |
| `sacem-test.js` | `script.js` + `"sacem"` dans `roofLayers` (le toit s'efface dans l'aire `roof_sacem`) |
| `tilesets/sacem-test/*.png` | les 7 peintures étendues (108×93 tuiles) + godray étendu |
| `paint-sacem/` | entrées du builder : `water.json` (eau animée), `collisions.png` (zone d'extension), `clears.json` (tuiles vidées dans le campus : arbre, foyers), `areas.json` (aire `roof_sacem`), `ring.json` / `props.json` (rochers et décor clonés, positions en tuiles) |
| `tools/build_map.py` | génère un .tmj à partir de `map.tmj` + peintures étendues (gère l'extension en largeur) |
| `tools/sacem/build_ext.py` | construit les peintures étendues (herbe/sable/mer/rochers/décor clonés du campus, chemin, bâtiment) |
| `tools/sacem/assets/ps_base.png`, `ps_toit.png` | calques Photoshop de David (hall vide = base, toit) à l'échelle map (0,72, décalage 21 px pour caler la porte sur une tuile) |

## Régénérer

```
python3 tools/sacem/build_ext.py
python3 tools/build_map.py --src map.tmj --paintings tilesets/sacem-test --paint paint-sacem --out sacem-test.tmj --script sacem-test.js --name "UMANI Town (test SACEM)"
```

Dépendances Python : Pillow, numpy, scipy.

## Tester en ligne

1. Commit + push (le workflow GitHub construit `dist/sacem-test.tmj`).
2. Dashboard WorkAdventure → nouvelle room `sacem-test`, Map URL : `https://goldeymusic.github.io/Umani.town/sacem-test.tmj`.
3. Le campus (`/@/campus`) continue de charger `map.tmj`, inchangé.

## Passage en production (plus tard, sur validation)

Remplacer `map.tmj` par la map générée (`--out map.tmj --script script.js --name "UMANI Town"`),
ajouter `"sacem"` à `roofLayers` dans `script.js`, et remplacer les tilesets du campus par les
peintures étendues (ou garder le dossier `tilesets/sacem-test/` comme tilesets de la map).

## Ajuster

- Collisions du bâtiment : ouvrir `sacem-test.tmj` dans Tiled, calque `collisions` (tuile « collides »).
  Le bâtiment a 336 tuiles bloquées : tout ce qui n'est pas le sol du hall (murs et leurs faces intérieures, bibliothèques, plantes de l'entrée ; le présentoir est franchissable) ; l'open space, l'entrée et le parvis sont libres ; seule l'emprise de la base bloque derrière, on passe juste derrière le mur (caché par le toit).
- Décor : `paint-sacem/props.json` = liste `[objet, colonne, ligne]` (objets : `arbre`, `arbre2`, `palmA`,
  `palmC`, `palmD`, `palmE`, `buisson`, `fleur`, `palmbush`, `rocher`), puis régénérer.
- Position du bâtiment : `PX, PY` dans `build_ext.py` (actuellement colonne 68, ligne 31 ; porte colonne 84, bas du parvis ligne 62,8). Échelle `S_`/`OFF` (0,72 / 21 px) : à changer avec les calques `assets/`.
