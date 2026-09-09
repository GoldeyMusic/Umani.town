"""Constantes et utilitaires partagés pour la construction de la map de test SACEM."""
import json, os
import numpy as np
from PIL import Image

T = 32
OLD_W, H, NEW_W = 60, 93, 108
HERE = os.path.dirname(os.path.abspath(__file__))           # <repo>/tools/sacem
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))      # racine du repo de la map
SACEM = os.path.join(HERE, "assets")                        # calques Photoshop de David à l'échelle map (ps_base/ps_toit)
OUT_TS = os.path.join(REPO, "tilesets", "sacem-test")      # copies de tilesets propres à la map de test
PAINT = os.path.join(REPO, "paint-sacem")                  # entrées non-image du builder (eau, collisions, aires, nettoyages)
PAINTINGS = ["floor", "walls", "furniture", "outer plant", "above", "roof"]

def src_painting(name):
    if name == "shadow":
        return os.path.join(REPO, "shadowing", "general shadow.png")
    return os.path.join(REPO, "tilesets", "Coolio", f"coolio_{name}.png")

def load_rgba(path):
    return np.asarray(Image.open(path).convert("RGBA")).copy()

def save_rgba(a, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    Image.fromarray(a.astype(np.uint8), "RGBA").save(path)

def load_map():
    return json.load(open(os.path.join(REPO, "map.tmj"), encoding="utf-8"))

def walk(layers):
    for l in layers:
        if l["type"] == "group":
            yield from walk(l["layers"])
        else:
            yield l

def tile_layer(m, name):
    return next(l for l in walk(m["layers"]) if l["type"] == "tilelayer" and l["name"] == name)

def tileset(m, name):
    return next(t for t in m["tilesets"] if t["name"] == name)

def rng(seed=7):
    return np.random.default_rng(seed)

def value_noise(h, w, scale, seed, octaves=2):
    """Bruit de valeur lisse dans [0,1], (h, w) px, période ~scale px."""
    r = np.random.default_rng(seed)
    out = np.zeros((h, w), np.float32); amp, tot = 1.0, 0.0
    for o in range(octaves):
        s = max(2, int(scale / (2 ** o)))
        gh, gw = h // s + 2, w // s + 2
        g = r.random((gh, gw)).astype(np.float32)
        ys = np.arange(h) / s; xs = np.arange(w) / s
        y0 = np.floor(ys).astype(int); x0 = np.floor(xs).astype(int)
        fy = (ys - y0)[:, None]; fx = (xs - x0)[None, :]
        fy = fy * fy * (3 - 2 * fy); fx = fx * fx * (3 - 2 * fx)
        a = g[y0][:, x0]; b = g[y0][:, x0 + 1]; c = g[y0 + 1][:, x0]; d = g[y0 + 1][:, x0 + 1]
        v = a * (1 - fx) * (1 - fy) + b * fx * (1 - fy) + c * (1 - fx) * fy + d * fx * fy
        out += amp * v; tot += amp; amp *= 0.5
    return out / tot

def alpha_over(dst, src, x, y):
    """Compose src (RGBA) sur dst (RGBA) en (x, y), avec découpe aux bords."""
    h, w = src.shape[:2]
    x0, y0 = max(x, 0), max(y, 0); x1, y1 = min(x + w, dst.shape[1]), min(y + h, dst.shape[0])
    if x1 <= x0 or y1 <= y0: return
    s = src[y0 - y:y1 - y, x0 - x:x1 - x].astype(np.float32); d = dst[y0:y1, x0:x1].astype(np.float32)
    sa = s[..., 3:4] / 255; da = d[..., 3:4] / 255
    oa = sa + da * (1 - sa)
    rgb = np.where(oa > 0, (s[..., :3] * sa + d[..., :3] * da * (1 - sa)) / np.maximum(oa, 1e-6), 0)
    dst[y0:y1, x0:x1, :3] = np.clip(rgb, 0, 255); dst[y0:y1, x0:x1, 3] = np.clip(oa[..., 0] * 255, 0, 255)
