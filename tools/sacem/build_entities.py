#!/usr/bin/env python3
"""
Collection d'entités SACEM pour l'éditeur de map WorkAdventure, à partir des détourages Photoshop de David
(échelle master 1500 px). Chaque objet est rééchantillonné depuis l'export master (LANCZOS) : 0,72 comme le
bâtiment, puis 65 % (mobilier dessiné à l'échelle de l'architecture) ou une échelle propre (SCALE).
Canevas arrondis au multiple de 32 (objet calé en bas), grille de collision, depthOffset.
Usage : python3 tools/sacem/build_entities.py [dossier des exports] [dossier de sortie] [planche de contrôle]
Sorties : <out>/<fichier>.png, <out>/sacem.json, planche de contrôle
"""
from PIL import Image, ImageDraw, ImageFont
import numpy as np, json, os, sys, unicodedata
S, T = 0.72, 32
FAM = {"siege": 0.65, "plante": 0.65, "sol": 0.65}      # réduction supplémentaire (David, 10/09 : 65 % pour tout ; le mobilier du PSD est à l'échelle de l'architecture, pas du woka)
SCALE = {"Point info (accueil)": 0.75, "Tapis rond (grand)": 0.85}   # échelles propres (David, 10/09), à la place de FAM
HERE = os.path.dirname(os.path.abspath(__file__))
SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser("~/Downloads/Objets séparés")          # exports Photoshop de David (SACEM-Umani_0001s_00NN_<nom>.png)
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "..", "..", "public", "entities", "sacem")
SHEET = sys.argv[3] if len(sys.argv) > 3 else os.path.join(OUT, "_controle.png")
os.makedirs(OUT, exist_ok=True)

# (fichier source, nom affiché, direction, tags, collision, depth)
#   collision : "base" = ligne de base par colonne ; "socle" = bande au-dessus du point le plus bas ; "ligne" = polyligne LINE (pied d'une cloison) ; "none" = franchissable
#   depth : "sol" (sous les wokas), "assise" (le woka qui s'y tient passe devant : sièges), "base" (tri sur le bas de l'image)
OBJ = [
    ("0000_open-space", "Cloison vitrée", "Down", ["sacem", "cloison", "vitre"], "ligne", "base"),
    ("0001_table", "Table basse", "Down", ["sacem", "table"], "socle", "base"),
    ("0002_point-info", "Point info (accueil)", "Down", ["sacem", "accueil", "comptoir"], "base", "base"),
    ("0003_tapis", "Tapis rond", "Down", ["sacem", "tapis"], "none", "sol"),
    ("0003_tapis", "Tapis rond (grand)", "Down", ["sacem", "tapis"], "none", "sol"),
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
# pied des cloisons, en pixels de l'export master : la cloison vitrée est un chevron « < » (deux panneaux, sommet à gauche) ;
# la base du panneau du haut est cachée par le panneau du bas, d'où une polyligne explicite (mesurée sur le détourage)
LINE = {"Cloison vitrée": [(237, 106), (3, 327), (155, 456)]}
BAND = 20            # bande de base : 20 px au-dessus du bas de chaque colonne (≈ 0,6 tuile)
COV_BAND = 0.10      # tuile bloquée si la bande couvre >= 10 % de la tuile

def slug(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return "".join(c if c.isalnum() else "-" for c in s.lower()).strip("-").replace("--", "-")

def line_grid(pts, rows, cols):
    """Tuiles traversées par la polyligne (échantillonnage au pixel), rendues 4-connexes : pas de passage en diagonale."""
    g = [[0] * cols for _ in range(rows)]; prev = None
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        n = int(max(abs(x1 - x0), abs(y1 - y0))) * 2 + 2
        for t in np.linspace(0, 1, n):
            x, y = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t
            c, r = min(cols - 1, max(0, int(x // T))), min(rows - 1, max(0, int(y // T)))
            if prev and prev[0] != r and prev[1] != c: g[prev[0]][c] = 1
            g[r][c] = 1; prev = (r, c)
    return g

coll = []; cells = []
font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 11)
for src, name, direction, tags, collision, depth in OBJ:
    path = [p for p in os.listdir(SRC) if src in p][0]
    im0 = Image.open(os.path.join(SRC, path)).convert("RGBA")
    fam = "plante" if any(t in ("plante", "machine") for t in tags) else ("sol" if any(t in ("tapis", "cloison") for t in tags) else "siege")
    k = S * SCALE.get(name, FAM[fam])
    im = im0.resize((max(1, round(im0.width * k)), max(1, round(im0.height * k))), Image.LANCZOS)
    # nettoyage : pixels quasi transparents -> transparents (évite les halos)
    a = np.asarray(im).copy(); a[a[..., 3] < 8] = 0; im = Image.fromarray(a)
    cw = -(-im.width // T) * T; ch = -(-im.height // T) * T
    rows, cols = ch // T, cw // T
    def make(ox):
        oy = ch - im.height                                  # calé en bas
        canvas = Image.new("RGBA", (cw, ch), (0, 0, 0, 0)); canvas.alpha_composite(im, (ox, oy))
        A = np.asarray(canvas)[..., 3] > 40
        grid = None
        if collision in ("base", "socle"):
            band = np.zeros_like(A)
            if collision == "socle":                       # objet à un seul socle (plante, machine, table) : bande au-dessus du point le plus bas
                yb = np.where(A.any(axis=1))[0].max(); band[max(0, yb - BAND + 1):yb + 1] = A[max(0, yb - BAND + 1):yb + 1]
            else:                                          # ligne de base par colonne (bureau + chaise, comptoir)
                for x in range(cw):
                    ys = np.where(A[:, x])[0]
                    if len(ys): band[max(0, ys.max() - BAND + 1):ys.max() + 1, x] = True
            grid = [[1 if band[r*T:(r+1)*T, c*T:(c+1)*T].mean() >= COV_BAND else 0 for c in range(cols)] for r in range(rows)]
        elif collision == "ligne":
            grid = line_grid([(x * k + ox, y * k + oy) for x, y in LINE[name]], rows, cols)
        if grid is not None:                               # pas de passage en diagonale entre deux tuiles bloquées : on ajoute la voisine la plus couverte par l'objet
            cov = lambda r, c: A[r*T:(r+1)*T, c*T:(c+1)*T].mean()
            for r in range(rows - 1):
                for c in range(cols):
                    for dc in (-1, 1):
                        if 0 <= c + dc < cols and grid[r][c] and grid[r+1][c+dc] and not grid[r][c+dc] and not grid[r+1][c]:
                            if cov(r, c + dc) >= cov(r + 1, c): grid[r][c+dc] = 1
                            else: grid[r+1][c] = 1
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
    if name in LINE: d.line([(x * k + ox, y * k + ch - im.height) for x, y in LINE[name]], fill=(0, 200, 0, 220), width=2)
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
