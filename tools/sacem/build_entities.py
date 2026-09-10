#!/usr/bin/env python3
"""
Collection d'entités SACEM pour l'éditeur de map WorkAdventure, à partir des détourages Photoshop de David
(échelle master 1500 px). Réduction à 0,72 (LANCZOS, comme le bâtiment), canevas arrondis au multiple de 32
(objet centré, calé en bas), grille de collision sur la bande de base de l'objet (pieds / socle), depthOffset.
Usage : python3 tools/sacem/build_entities.py [dossier des exports] [dossier de sortie] [planche de contrôle]
Sorties : <out>/<fichier>.png, <out>/sacem.json, planche de contrôle
"""
from PIL import Image, ImageDraw, ImageFont
import numpy as np, json, os, sys, unicodedata
S, T = 0.72, 32
FAM = {"siege": 0.65, "plante": 0.65, "sol": 0.65}      # réduction supplémentaire (David, 10/09 : 65 % pour tout ; le mobilier du PSD est à l'échelle de l'architecture, pas du woka)
HERE = os.path.dirname(os.path.abspath(__file__))
SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser("~/Downloads/Objets séparés")          # exports Photoshop de David (SACEM-Umani_0001s_00NN_<nom>.png)
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "..", "..", "public", "entities", "sacem")
SHEET = sys.argv[3] if len(sys.argv) > 3 else os.path.join(OUT, "_controle.png")
os.makedirs(OUT, exist_ok=True)

# (fichier source, nom affiché, direction, tags, collision, depth)
#   collision : "base" = ligne de base par colonne ; "socle" = bande au-dessus du point le plus bas ; "none" = franchissable
#   depth : "sol" (sous les wokas), "assise" (le woka qui s'y tient passe devant : sièges, table basse), "base" (tri sur le bas de l'image), "ligne" (tri sur la ligne moyenne de la base, cloisons en diagonale)
OBJ = [
    ("0000_open-space", "Cloison vitrée", "Down", ["sacem", "cloison", "vitre"], "base", "ligne"),
    ("0001_table", "Table basse", "Down", ["sacem", "table"], "none", "assise"),
    ("0002_point-info", "Point info (accueil)", "Down", ["sacem", "accueil", "comptoir"], "base", "base"),
    ("0003_tapis", "Tapis rond", "Down", ["sacem", "tapis"], "none", "sol"),
    ("0004_bureau", "Bureau", "Down", ["sacem", "bureau"], "base", "base"),
    ("0005_canapé", "Canapé", "Right", ["sacem", "canapé", "salon"], "none", "assise"),
    ("0008_fauteuil-3", "Fauteuil", "Down", ["sacem", "fauteuil", "salon"], "none", "assise"),
    ("0006_fauteuil-5", "Fauteuil", "Right", ["sacem", "fauteuil", "salon"], "none", "assise"),
    ("0007_fauteuil-4", "Fauteuil", "Left", ["sacem", "fauteuil", "salon"], "none", "assise"),
    ("0009_fauteuil-2", "Fauteuil (bis)", "Down", ["sacem", "fauteuil", "salon"], "none", "assise"),
    ("0010_fauteuil-1", "Fauteuil (bis)", "Left", ["sacem", "fauteuil", "salon"], "none", "assise"),
    ("0017_plante-1", "Plante 1", "Down", ["sacem", "plante"], "socle", "base"),
    ("0016_plante-2", "Plante 2", "Down", ["sacem", "plante"], "socle", "base"),
    ("0015_plante-3", "Plante 3", "Down", ["sacem", "plante"], "socle", "base"),
    ("0014_plante-4", "Plante 4", "Down", ["sacem", "plante"], "socle", "base"),
    ("0013_plante-5", "Plante 5", "Down", ["sacem", "plante"], "socle", "base"),
    ("0012_plante-6", "Plante 6", "Down", ["sacem", "plante"], "socle", "base"),
    ("0011_plante-7", "Plante 7", "Down", ["sacem", "plante"], "socle", "base"),
    ("0018_machine-café", "Machine à café", "Down", ["sacem", "machine", "café"], "socle", "base"),
]
BAND = 20            # bande de base : 20 px au-dessus du bas de chaque colonne (≈ 0,6 tuile)
COV_BAND = 0.10      # tuile bloquée si la bande couvre >= 10 % de la tuile

def slug(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return "".join(c if c.isalnum() else "-" for c in s.lower()).strip("-").replace("--", "-")

coll = []; cells = []
font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 11)
for src, name, direction, tags, collision, depth in OBJ:
    path = [p for p in os.listdir(SRC) if src in p][0]
    im = Image.open(os.path.join(SRC, path)).convert("RGBA")
    fam = "plante" if any(t in ("plante", "machine") for t in tags) else ("sol" if any(t in ("tapis", "cloison") for t in tags) else "siege")
    k = S * FAM[fam]
    im = im.resize((max(1, round(im.width * k)), max(1, round(im.height * k))), Image.LANCZOS)
    # nettoyage : pixels quasi transparents -> transparents (évite les halos)
    a = np.asarray(im).copy(); a[a[..., 3] < 8] = 0; im = Image.fromarray(a)
    cw = -(-im.width // T) * T; ch = -(-im.height // T) * T
    rows, cols = ch // T, cw // T
    def make(ox):
        canvas = Image.new("RGBA", (cw, ch), (0, 0, 0, 0)); canvas.alpha_composite(im, (ox, ch - im.height))   # calé en bas
        A = np.asarray(canvas)[..., 3] > 40
        grid = None
        if collision in ("base", "socle"):
            band = np.zeros_like(A)
            if collision == "socle":                       # objet à un seul socle (plante, machine) : bande au-dessus du point le plus bas
                yb = np.where(A.any(axis=1))[0].max(); band[max(0, yb - BAND + 1):yb + 1] = A[max(0, yb - BAND + 1):yb + 1]
            else:                                          # ligne de base par colonne (cloison en diagonale, bureau + chaise, comptoir)
                for x in range(cw):
                    ys = np.where(A[:, x])[0]
                    if len(ys): band[max(0, ys.max() - BAND + 1):ys.max() + 1, x] = True
            grid = [[1 if band[r*T:(r+1)*T, c*T:(c+1)*T].mean() >= COV_BAND else 0 for c in range(cols)] for r in range(rows)]
        return canvas, A, grid
    # position horizontale : celle qui bloque le moins de tuiles (à égalité, la plus centrée)
    mid = (cw - im.width) // 2
    cands = sorted(range(0, cw - im.width + 1), key=lambda o: abs(o - mid))
    best = None
    for o in cands:
        canvas, A, grid = make(o)
        n = sum(map(sum, grid)) if grid is not None else 0
        if best is None or n < best[0]: best = (n, o, canvas, A, grid)
        if grid is None: break
    n, ox, canvas, A, grid = best
    if depth == "sol": dz = -(ch + 32)
    elif depth == "assise": dz = -ch                     # tri sur le haut du canevas : un woka dont les pieds sont dans le siège est dessiné dessus
    elif depth == "ligne":
        yb = [np.where(A[:, x])[0].max() for x in range(cw) if A[:, x].any()]
        dz = -int(round(ch - float(np.mean(yb))))
    else: dz = 0
    fname = f"{slug(name)}-{direction.lower()}.png"
    canvas.save(os.path.join(OUT, fname))
    e = {"name": name, "tags": tags, "imagePath": fname, "direction": direction, "color": "brown" if "(bis)" not in name else "sienna"}
    if grid is not None: e["collisionGrid"] = grid
    if dz: e["depthOffset"] = dz
    coll.append(e)
    print(f"{name:22s} {direction:5s} x{k:.2f} {im.width}x{im.height} -> canevas {cw}x{ch} ({cols}x{rows} tuiles) ; collision {'aucune' if grid is None else sum(map(sum, grid))} tuiles ; depthOffset {dz}")
    # cellule de contrôle : damier, objet, grille, tuiles bloquées en rouge, ligne de tri en bleu
    bg = Image.new("RGBA", (cw, ch), (0, 0, 0, 0)); d = ImageDraw.Draw(bg)
    for r in range(rows):
        for c in range(cols): d.rectangle((c*T, r*T, c*T+T-1, r*T+T-1), fill=(236, 236, 236, 255) if (r + c) % 2 == 0 else (204, 204, 204, 255))
    bg.alpha_composite(canvas)
    ov = Image.new("RGBA", (cw, ch), (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
    if grid is not None:
        for r in range(rows):
            for c in range(cols):
                if grid[r][c]: d.rectangle((c*T, r*T, c*T+T-1, r*T+T-1), fill=(255, 0, 0, 80), outline=(255, 0, 0, 200))
    d.line((0, ch + dz - 1, cw, ch + dz - 1), fill=(0, 90, 255, 220), width=2)
    bg.alpha_composite(ov)
    lab = Image.new("RGBA", (max(cw, 120), ch + 18), (255, 255, 255, 255)); lab.alpha_composite(bg, (0, 0))
    ImageDraw.Draw(lab).text((2, ch + 3), f"{name} {direction} {cw}x{ch}", font=font, fill=(0, 0, 0, 255))
    cells.append(lab)

json.dump({"collectionName": "SACEM", "tags": ["sacem"], "collection": coll}, open(os.path.join(OUT, "sacem.json"), "w"), ensure_ascii=False, indent=1)
rows_, row, w = [], [], 0
for c in cells:
    if w + c.width > 1400 and row: rows_.append(row); row, w = [], 0
    row.append(c); w += c.width + 10
rows_.append(row)
sh = Image.new("RGB", (max(sum(c.width + 10 for c in r) for r in rows_), sum(max(c.height for c in r) + 10 for r in rows_)), (255, 255, 255)); y = 0
for r in rows_:
    x = 0
    for c in r: sh.paste(c.convert("RGB"), (x, y)); x += c.width + 10
    y += max(c.height for c in r) + 10
sh.save(SHEET); print("planche", sh.size, "; collection :", len(coll), "entités ->", OUT)
