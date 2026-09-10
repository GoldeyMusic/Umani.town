#!/usr/bin/env python3
"""
Génère une map WorkAdventure (.tmj) à partir de map.tmj et de peintures pleine taille étendues.

Principe de la map UMANI Town : les tilesets custom (coolio_floor/walls/furniture/outer plant/above/roof
et general shadow) sont des images de la taille exacte de la map, découpées en tuiles de 32 px avec
correspondance 1:1. Pour étendre la map, on agrandit ces images (droite et/ou bas), on peint, puis ce
script produit un nouveau .tmj : dimensions, tilesets (chemins des nouvelles images), calques identité
(index recalculés — l'extension en LARGEUR change l'index des tuiles existantes), gids décalés pour les
autres tilesets, collisions, eau animée, aires, script.

Usage :
    python3 tools/build_map.py --src map.tmj --paintings tilesets/sacem-test --paint paint-sacem \
                               --out sacem-test.tmj --script sacem-test.js [--name "UMANI Town (test SACEM)"]

Dossier --paintings : coolio_floor.png, coolio_walls.png, coolio_furniture.png, coolio_outer plant.png,
    coolio_above.png, coolio_roof.png, general shadow.png, et optionnellement God ray linear 45 tall.png
Dossier --paint (entrées optionnelles) :
    collisions.png   tout pixel non transparent = tuile bloquée (zone d'extension uniquement)
    water.json       {"tileset": ..., "tiles": {"x,y": id_local}} tuiles d'eau (posées partout où listées)
    clears.json      {"collisions": [[x,y],...], "layers": {"nom calque": [[x,y],...]}} tuiles à vider (zone campus)
    areas.json       [{"name": "roof_sacem", "x":..,"y":..,"width":..,"height":..}] aires à ajouter (px)
La zone campus (ancienne taille) garde ses données d'origine ; les tuiles identité dont la peinture
est devenue transparente sont vidées. La zone d'extension est régénérée depuis les peintures.
"""
import argparse, json, os, sys
from PIL import Image

TILE = 32
PAINTINGS = {"coolio_floor": ["floor1"], "coolio_walls": ["walls1"], "coolio_furniture": ["furniture1"],
             "coolio_outer plant": ["outer plant"], "coolio_above": ["above"], "coolio_roof": [],
             "general shadow": ["shadow"]}
FILES = {"coolio_floor": "coolio_floor.png", "coolio_walls": "coolio_walls.png", "coolio_furniture": "coolio_furniture.png",
         "coolio_outer plant": "coolio_outer plant.png", "coolio_above": "coolio_above.png", "coolio_roof": "coolio_roof.png",
         "general shadow": "general shadow.png"}
GODRAY = "God ray linear 45 tall"
ROOF_LAYERS = ("lowerLeft", "lowerRight", "upperLeft", "upperRight")
COLLIDE_GID = 3
FLIP_MASK = 0xF0000000

def walk(layers):
    for l in layers:
        if l["type"] == "group":
            yield from walk(l["layers"])
        else:
            yield l

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="map.tmj"); ap.add_argument("--paintings", required=True)
    ap.add_argument("--paint", default=None); ap.add_argument("--out", required=True)
    ap.add_argument("--script", default=None); ap.add_argument("--name", default=None)
    ap.add_argument("--keep-collisions", default=None, metavar="TMJ",
                    help="reprend tel quel le calque collisions de ce .tmj (retouches faites dans Tiled) au lieu de le recalculer")
    a = ap.parse_args()
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); os.chdir(root)
    m = json.load(open(a.src, encoding="utf-8"))
    oldW, oldH = m["width"], m["height"]
    ts_by_name = {t["name"]: t for t in m["tilesets"]}

    # 1. taille cible
    imgs = {}
    for name, f in FILES.items():
        p = os.path.join(a.paintings, f)
        if not os.path.exists(p): sys.exit(f"peinture manquante : {p}")
        imgs[name] = Image.open(p).convert("RGBA"); ts_by_name[name]["image"] = p.replace(os.sep, "/")
    sizes = {im.size for im in imgs.values()}
    if len(sizes) != 1: sys.exit(f"peintures de tailles différentes : {sizes}")
    (pw, ph), = sizes
    if pw % TILE or ph % TILE: sys.exit("dimensions non multiples de 32")
    W, H = pw // TILE, ph // TILE
    if W < oldW or H < oldH: sys.exit("réduction non gérée")
    print(f"map {oldW}x{oldH} -> {W}x{H} tuiles")
    def in_ext(x, y): return x >= oldW or y >= oldH

    # godray étendu (optionnel)
    gr = ts_by_name[GODRAY]; gr_old_cols = gr["columns"]
    gp = os.path.join(a.paintings, GODRAY + ".png")
    if os.path.exists(gp):
        gi = Image.open(gp); gr["image"] = gp.replace(os.sep, "/")
        gr["imagewidth"], gr["imageheight"] = gi.size
        gr["columns"] = gi.size[0] // TILE; gr["tilecount"] = gr["columns"] * (gi.size[1] // TILE)
        print(f"godray : {gr_old_cols} -> {gr['columns']} colonnes")

    # 2. nouveaux firstgid
    old_first = {t["name"]: t["firstgid"] for t in m["tilesets"]}
    old_cols = {t["name"]: t["columns"] for t in m["tilesets"]}; old_cols[GODRAY] = gr_old_cols
    gid, new_first = 1, {}
    for t in sorted(m["tilesets"], key=lambda t: t["firstgid"]):
        new_first[t["name"]] = gid
        if t["name"] in PAINTINGS:
            t["columns"], t["imagewidth"], t["imageheight"], t["tilecount"] = W, pw, ph, W * H
        gid += t["tilecount"]
    for t in m["tilesets"]: t["firstgid"] = new_first[t["name"]]
    order = sorted(old_first.items(), key=lambda kv: kv[1])
    resized = set(PAINTINGS) | ({GODRAY} if gr["columns"] != gr_old_cols else set())

    def remap(g):
        if not g: return 0
        flags, local = g & FLIP_MASK, g & ~FLIP_MASK
        name = None
        for n, f in order:
            if local >= f: name = n
        idx = local - old_first[name]
        if name in resized:                       # l'image a changé de largeur : (x, y) -> nouvel index
            x, y = idx % old_cols[name], idx // old_cols[name]
            idx = y * ts_by_name[name]["columns"] + x
        return flags | (new_first[name] + idx)

    def regrid(data):
        out = [0] * (W * H)
        for i, g in enumerate(data):
            if g:
                x, y = i % oldW, i // oldW
                out[y * W + x] = remap(g)
        return out

    paint = a.paint or ""
    def load_json(f):
        p = os.path.join(paint, f)
        return json.load(open(p)) if paint and os.path.exists(p) else None
    clears = load_json("clears.json") or {"collisions": [], "layers": {}}
    water = load_json("water.json"); areas = load_json("areas.json") or []
    coll_mask = None
    if paint and os.path.exists(os.path.join(paint, "collisions.png")):
        coll_mask = Image.open(os.path.join(paint, "collisions.png")).convert("RGBA").split()[3]

    alphas = {name: im.split()[3] for name, im in imgs.items()}
    def has_pixels(name, x, y):
        return alphas[name].crop((x * TILE, y * TILE, (x + 1) * TILE, (y + 1) * TILE)).getbbox() is not None

    paint_layers = {ln: name for name, lns in PAINTINGS.items() for ln in lns}
    for l in walk(m["layers"]):
        if l["type"] != "tilelayer": continue
        l["width"], l["height"] = W, H
        data = regrid(l["data"])
        small = l["name"] == "above" and sum(1 for g in l["data"] if g) < 100
        if l["name"] in paint_layers and not small:
            name = paint_layers[l["name"]]; first = new_first[name]
            for i in range(W * H):
                x, y = i % W, i // W
                if in_ext(x, y): data[i] = first + i if has_pixels(name, x, y) else 0
                elif data[i]:
                    loc = (data[i] & ~FLIP_MASK) - first
                    if 0 <= loc < W * H and not has_pixels(name, loc % W, loc // W):
                        data[i] = 0                                             # tuile de peinture vidée (ex. arbre retiré)
        elif l["name"] in ROOF_LAYERS:
            pass
        elif l["name"] == "collisions" and a.keep_collisions:
            k = json.load(open(a.keep_collisions, encoding="utf-8"))
            kl = [x for x in k["layers"] if x.get("name") == "collisions"][0]
            if (k["width"], k["height"]) != (W, H): sys.exit(f"--keep-collisions : taille {k['width']}x{k['height']} != {W}x{H}")
            l["data"] = [COLLIDE_GID if g else 0 for g in kl["data"]]
            side = load_json("walls-side.json") or []                      # murs latéraux du bâtiment : toujours bloqués
            for x, y in side: l["data"][y * W + x] = COLLIDE_GID
            print("collisions reprises de", a.keep_collisions, ":", sum(1 for g in l["data"] if g), "tuiles (dont", len(side), "de murs latéraux imposées)")
            continue
        elif l["name"] == "collisions":
            if coll_mask is not None:
                for i in range(W * H):
                    x, y = i % W, i // W
                    hit = coll_mask.crop((x * TILE, y * TILE, (x + 1) * TILE, (y + 1) * TILE)).getbbox() is not None
                    if in_ext(x, y): data[i] = COLLIDE_GID if hit else 0
                    elif hit: data[i] = COLLIDE_GID                      # zone campus : le masque ajoute (objets clonés), ne retire jamais
            for x, y in clears.get("collisions", []): data[y * W + x] = 0
        elif l["name"] == "animated_water" and water:
            first = new_first[water["tileset"]]
            for k, t in water["tiles"].items():
                x, y = map(int, k.split(",")); data[y * W + x] = first + t
        elif l["name"] == "godray":
            first, cols = new_first[GODRAY], gr["columns"]
            for i in range(W * H):
                x, y = i % W, i // W
                if in_ext(x, y) and x + 1 < cols: data[i] = first + y * cols + x + 1     # décalage (1,0) comme le campus
        for x, y in clears.get("layers", {}).get(l["name"], []): data[y * W + x] = 0
        l["data"] = data

    # toit de l'extension -> calque roofs/sacem
    roofs_group = next(g for g in m["layers"] if g["type"] == "group" and g["name"] == "roofs")
    sacem = next((l for l in roofs_group["layers"] if l["name"] == "sacem"), None)
    if sacem is None:
        sacem = {"data": [0] * (W * H), "height": H, "id": m["nextlayerid"], "name": "sacem", "opacity": 1,
                 "type": "tilelayer", "visible": True, "width": W, "x": 0, "y": 0}
        m["nextlayerid"] += 1; roofs_group["layers"].append(sacem)
    first = new_first["coolio_roof"]
    sacem["data"] = [first + i if in_ext(i % W, i // W) and has_pixels("coolio_roof", i % W, i // W) else 0 for i in range(W * H)]
    print("toit sacem :", sum(1 for g in sacem["data"] if g), "tuiles")

    # aires
    fl = next(l for l in m["layers"] if l["type"] == "objectgroup" and l["name"] == "floorLayer")
    # aires "intérieur" : rectangles couvrant les tuiles atteignables depuis un point intérieur mais PAS depuis l'extérieur
    # sans passer par la porte (le toit ne se découvre qu'en franchissant l'entrée)
    coll_l = next(l for l in walk(m["layers"]) if l.get("name") == "collisions")
    blocked = [bool(g) for g in coll_l["data"]]
    def reach(start, forbid):
        seen = [False] * (W * H); q = [start]; seen[start[1] * W + start[0]] = True
        while q:
            x, y = q.pop()
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = x + dx, y + dy
                if 0 <= nx < W and 0 <= ny < H and not seen[ny * W + nx] and not blocked[ny * W + nx] and not forbid(nx, ny):
                    seen[ny * W + nx] = True; q.append((nx, ny))
        return seen
    expanded = []
    for ar in areas:
        if "interior" not in ar: expanded.append(ar); continue
        it = ar["interior"]; (dx0, dy0), (dx1, dy1) = it["door"]
        door = lambda x, y: dx0 <= x <= dx1 and dy0 <= y <= dy1
        inside = reach(tuple(it["seed"]), door); outside = reach(tuple(it["outside"]), door)
        bx0, by0 = ar["x"] // TILE, ar["y"] // TILE; bx1, by1 = (ar["x"] + ar["width"]) // TILE - 1, (ar["y"] + ar["height"]) // TILE - 1
        # cellules = tout le cadre sauf les tuiles atteignables de l'extérieur sans la porte (les murs, jamais foulés, comptent :
        # ça donne des rectangles bien plus gros)
        cells = {(x, y) for y in range(by0, by1 + 1) for x in range(bx0, bx1 + 1) if not outside[y * W + x]}
        cells |= {(x, y) for x in range(dx0, dx1 + 1) for y in range(dy0, it.get("door_inside_to", dy1) + 1)}
        cells -= {(x, y) for (x, y) in cells if outside[y * W + x]}
        rects = []; left = set(cells)
        while left:
            x0, y0 = min(left, key=lambda c: (c[1], c[0])); x1 = x0
            while (x1 + 1, y0) in left: x1 += 1
            y1 = y0
            while all((x, y1 + 1) in left for x in range(x0, x1 + 1)): y1 += 1
            rects.append((x0, y0, x1, y1)); left -= {(x, y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)}
        for i, (x0, y0, x1, y1) in enumerate(rects):
            expanded.append({"name": ar["name"] + ("" if i == 0 else f"_{i + 1}"), "x": x0 * TILE, "y": y0 * TILE, "width": (x1 - x0 + 1) * TILE, "height": (y1 - y0 + 1) * TILE})
        print("aires intérieures", ar["name"], ":", len(rects), "rectangles,", len(cells), "tuiles ->", [r["name"] for r in expanded if r["name"].startswith(ar["name"])])
    areas = expanded
    for ar in areas:
        if any(o.get("name") == ar["name"] for o in fl["objects"]): continue
        fl["objects"].append({"height": ar["height"], "id": m["nextobjectid"], "name": ar["name"], "rotation": 0,
                              "type": "area", "visible": True, "width": ar["width"], "x": ar["x"], "y": ar["y"]})
        m["nextobjectid"] += 1
    m["width"], m["height"] = W, H
    props = {p["name"]: p for p in m.setdefault("properties", [])}
    if a.script: props["script"]["value"] = a.script
    if a.name: props["mapName"]["value"] = a.name
    json.dump(m, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("écrit :", a.out)

if __name__ == "__main__":
    main()
