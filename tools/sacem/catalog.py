"""Catalogue d'objets clonables du campus (arbres, palmiers, buissons, rochers, fleurs...).
Un objet = composante connexe d'une peinture (outer plant par défaut, ou above pour les rochers gris),
+ ses pixels dans les autres peintures (mêmes pixels de couronne dans above), + son ombre (general shadow),
+ ses tuiles de collision (celles du campus qui portent l'objet)."""
import numpy as np
from scipy import ndimage as ndi
from common import *

class Campus:
    def __init__(self):
        self.p = {n: load_rgba(src_painting(n)) for n in PAINTINGS + ["shadow"]}
        m = load_map(); self.m = m
        col = tile_layer(m, "collisions")["data"]
        self.coll = np.array([1 if g else 0 for g in col]).reshape(H, OLD_W)
        self.labels = {}

    def label(self, name):
        if name not in self.labels:
            self.labels[name] = ndi.label(self.p[name][..., 3] > 0)[0]
        return self.labels[name]

    def extract(self, tx, ty, layer="outer plant", shadow_margin=(4, 4, 28, 28), extra_layers=("above",), cover=0.2):
        """Objet contenant le pixel central de la tuile (tx, ty) dans `layer`."""
        lab = self.label(layer)
        px, py = tx * T + T // 2, ty * T + T // 2
        lid = lab[py, px]
        if not lid:  # cherche dans la tuile
            sub = lab[ty * T:(ty + 1) * T, tx * T:(tx + 1) * T]; ids = sub[sub > 0]
            assert ids.size, f"aucun objet en ({tx},{ty}) dans {layer}"
            lid = np.bincount(ids).argmax()
        mask = lab == lid
        ys, xs = np.where(mask); y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
        obj = {"layer": layer, "box": (x0, y0, x1, y1), "layers": {}}
        m_dil = ndi.binary_dilation(mask[y0:y1, x0:x1], iterations=2)
        a = self.p[layer][y0:y1, x0:x1].copy(); a[~mask[y0:y1, x0:x1]] = 0; obj["layers"][layer] = a
        for n in extra_layers:
            b = self.p[n][y0:y1, x0:x1].copy(); b[~m_dil] = 0
            if (b[..., 3] > 0).any(): obj["layers"][n] = b
        ml, mt, mr, mb = shadow_margin
        sx0, sy0, sx1, sy1 = max(x0 - ml, 0), max(y0 - mt, 0), min(x1 + mr, OLD_W * T), min(y1 + mb, H * T)
        sh = self.p["shadow"][sy0:sy1, sx0:sx1].copy()
        # ombre ambiante du voisinage (bâtiments) retirée : on ne garde que l'excès par rapport au bord du cadre
        border = np.concatenate([sh[0, :, 3], sh[-1, :, 3], sh[:, 0, 3], sh[:, -1, 3]]); base = int(np.median(border))
        if base: sh[..., 3] = np.clip(sh[..., 3].astype(int) - base, 0, 255).astype(np.uint8)
        # et on ne garde que l'ombre au voisinage de l'objet (dilatation + décalage vers le bas-droite)
        full = mask[sy0:sy1, sx0:sx1]
        near = ndi.binary_dilation(full, iterations=18)
        shifted = np.zeros_like(full); shifted[20:, 20:] = full[:-20, :-20]
        near |= ndi.binary_dilation(shifted, iterations=14)
        sh[~near] = 0
        obj["shadow"] = sh; obj["shadow_off"] = (sx0 - x0, sy0 - y0)
        # collisions : par défaut, tuiles bien couvertes par l'objet dans sa partie basse (tronc) ;
        # affinées à la main par `coll` (liste de (col, ligne) relatives à la tuile haut-gauche du cadre)
        cols = []
        for yy in range(y0 // T, (y1 - 1) // T + 1):
            for xx in range(x0 // T, (x1 - 1) // T + 1):
                c = mask[yy * T:(yy + 1) * T, xx * T:(xx + 1) * T].mean()
                if c >= 0.5 and (yy + 1) * T > y1 - 2.5 * T: cols.append((xx * T - x0, yy * T - y0))
        obj["coll"] = cols
        obj["tile0"] = (x0 // T, y0 // T)
        return obj

def set_coll(obj, tiles):
    """tiles : liste de (col, ligne) en tuiles absolues du campus -> collisions de l'objet."""
    x0, y0 = obj["box"][:2]
    obj["coll"] = [(tx * T - x0, ty * T - y0) for tx, ty in tiles]

def place(obj, canvases, coll_mask, x, y, shadow=True):
    """Pose l'objet avec son coin haut-gauche (px) en (x, y) sur les canevas (dict name->RGBA), met à jour coll_mask (px)."""
    if shadow:
        ox, oy = obj["shadow_off"]; alpha_over(canvases["shadow"], obj["shadow"], x + ox, y + oy)
    for n, a in obj["layers"].items():
        alpha_over(canvases[n], a, x, y)
    for cx, cy in obj["coll"]:
        X, Y = x + cx, y + cy
        coll_mask[Y:Y + T, X:X + T] = 255
