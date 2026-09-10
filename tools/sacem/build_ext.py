#!/usr/bin/env python3
"""
Construit les peintures étendues (108 x 93 tuiles) de la map de test SACEM à partir des peintures
du campus (60 x 93), + les entrées du builder tmj (paint-sacem/).

Tout est cloné du campus : herbe, sable, sable immergé, rochers de l'anneau du plateau, arbres,
palmiers, buissons, fleurs, rochers ; l'eau est décrite par un masque de tuiles -> water.json (autotile
du tileset coolio_animated_water). Le bâtiment SACEM (calques Photoshop de David à l'échelle 0,72)
va dans walls (base) et roof (toit).

Sorties : tilesets/sacem-test/coolio_*.png, general shadow.png, God ray linear 45 tall.png
          paint-sacem/water.json, collisions.png, clears.json, areas.json
"""
import json, os, pickle, sys
import numpy as np
from PIL import Image, ImageFilter
from scipy import ndimage as ndi
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
from catalog import Campus, place, set_coll

R = rng(11)
campus = Campus()
P = {n: campus.p[n] for n in PAINTINGS + ["shadow"]}
m = campus.m
water_c = tile_layer(m, "animated_water")["data"]
water_campus = np.array([1 if g else 0 for g in water_c]).reshape(H, OLD_W).astype(bool)

# =====================================================================================
# 0. Catalogue d'objets clonables (extrait AVANT toute retouche du campus)
# =====================================================================================
SRC = {"arbre": (54, 11), "arbre2": (43, 81), "palmA": (39, 24), "palmC": (36, 82), "palmD": (7, 89), "palmE": (14, 84),
       "buisson": (52, 57), "fleur": (54, 56), "palmbush": (1, 68), "rocher": (24, 23),
       "_arbre_coupe": (50, 55), "_palm48": (50, 17), "_arbre13": (15, 54)}      # sources pour compléter les objets coupés au bord est
OBJ = {k: campus.extract(*v) for k, v in SRC.items()}
set_coll(OBJ["arbre"], [(54, 13), (54, 14)]); set_coll(OBJ["palmA"], [(39, 26)]); set_coll(OBJ["palmD"], [(8, 91)]); set_coll(OBJ["rocher"], [(24, 23), (25, 23)])

# =====================================================================================
# 1. Zone campus : objets coupés par l'ancien bord complétés ; retrait de l'arbre sur le tracé,
#    foyers/souches, ombre, tuiles à nettoyer
# =====================================================================================
clears = {"collisions": [], "layers": {}}      # nettoyages appliqués par build_map dans la zone campus
def comp_at(a, x, y):
    lab, n = ndi.label(a[..., 3] > 0); assert lab[y, x]; return lab == lab[y, x]
# objets de outer plant qui touchent x = 1920 : on cherche le dessin complet identique (éventuellement en miroir)
# et on le pose au même coin haut-gauche -> partie campus inchangée, le reste continue dans l'extension
COMPLETE = []
lab_op, _ = ndi.label(P["outer plant"][..., 3] > 0)
for cid in sorted(set(np.unique(lab_op[:, OLD_W * T - 2:])) - {0}):
    ys_, xs_ = np.where(lab_op == cid)
    if len(xs_) < 300: continue
    x0, y0, x1, y1 = xs_.min(), ys_.min(), xs_.max() + 1, ys_.max() + 1
    a = P["outer plant"][y0:y1, x0:x1].astype(int); ma = lab_op[y0:y1, x0:x1] == cid
    best = None
    for k, o in OBJ.items():
        s = o["layers"]["outer plant"]; sh_, sw_ = s.shape[:2]
        if abs(sh_ - (y1 - y0)) > 4: continue
        for flip in (False, True):
            s2 = s[:, ::-1] if flip else s
            h, w = min(sh_, y1 - y0), min(sw_, x1 - x0)
            d = np.abs(a[:h, :w] - s2[:h, :w].astype(int))[ma[:h, :w]].mean()
            if best is None or d < best[0]: best = (d, k, flip)
    if best and best[0] < 40:
        COMPLETE.append((cid, x0, y0, best[1], best[2]))
        print(f"objet coupé au bord ({x0/T:.1f},{y0/T:.1f}) {'complété avec' if best[0] < 5 else 'REMPLACÉ par'} {best[1]}{' (miroir)' if best[2] else ''} (écart {best[0]:.1f})")
crown = (int(50.5 * T), int(53.5 * T))
m_crown = comp_at(P["roof"], *crown); P["roof"][m_crown] = 0
m_ab = ndi.binary_dilation(m_crown, iterations=2) & (P["above"][..., 3] > 0); m_ab[:, int(53.2 * T):] = False
P["above"][m_ab] = 0
m_tree = comp_at(P["outer plant"], *crown); P["outer plant"][m_tree] = 0
band = P["shadow"][int(55.5 * T):60 * T, 45 * T:60 * T]
band[...] = 0
prof = P["shadow"][int(55.5 * T):60 * T, 40 * T:41 * T].copy()               # profil propre de l'ombre du ponton
for x in range(45 * T, 60 * T):                                               # ponton jusqu'à x≈54, puis fondu
    f = 1.0 if x < 54 * T else max(0.0, 1 - (x - 54 * T) / (2 * T))
    col = prof[:, x % T].copy(); col[:, 3] = (col[:, 3] * f).astype(np.uint8)
    P["shadow"][int(55.5 * T):60 * T, x] = col
lab, n = ndi.label(P["furniture"][..., 3] > 0)
ids = set(np.unique(lab[56*T:58*T, 45*T:60*T])) - {0}; P["furniture"][np.isin(lab, list(ids))] = 0
clears["collisions"] += [[50, 56], [49, 57], [50, 57], [56, 57], [46, 58]]            # tronc + 2 foyers
clears["layers"]["animated"] = [[x, y] for y in range(56, 59) for x in range(45, 58)]  # tuiles de feu animées
# ombre de l'ancienne couronne (arbre remplacé en haut à droite) qui dépasserait de la nouvelle : effacée
for cid, x0, y0, k, flip in COMPLETE:
    if k and k.startswith("_arbre_coupe"):
        P["shadow"][int(3.0 * T):int(7.6 * T), int(58.4 * T):OLD_W * T, 3] = 0
print("zone campus : arbre, foyers et souches retirés")

# =====================================================================================
# 2. Canevas étendus
# =====================================================================================
C = {n: np.zeros((H * T, NEW_W * T, 4), np.uint8) for n in PAINTINGS + ["shadow"]}
for n in C: C[n][:, :OLD_W * T] = P[n]
coll_px = np.zeros((H * T, NEW_W * T), np.uint8)
for cid, x0, y0, k, flip in COMPLETE:
    cut = lab_op == cid; cut_d = ndi.binary_dilation(cut, iterations=2)
    if k is None:                                   # miroir des `flip` derniers px de l'objet au-delà du bord
        miss = flip; ys_, xs_ = np.where(cut); y0_, y1_ = ys_.min(), ys_.max() + 1
        for n in ("outer plant", "above", "roof"):
            src = P[n][y0_:y1_, OLD_W * T - miss:OLD_W * T].copy()
            mm = (cut if n == "outer plant" else cut_d)[y0_:y1_, OLD_W * T - miss:OLD_W * T]
            src[~mm] = 0
            alpha_over(C[n], src[:, ::-1], OLD_W * T, y0_)
        continue
    for n in ("outer plant", "above", "roof"):
        mm = (cut if n == "outer plant" else cut_d) & (P[n][..., 3] > 0)
        C[n][:, :OLD_W * T][mm] = 0
    o = OBJ[k]
    for n, arr in o["layers"].items():
        alpha_over(C[n], arr[:, ::-1] if flip else arr, x0, y0)

# =====================================================================================
# 3. Terrain de l'extension (tuiles) : eau nord (bras de mer qui s'ouvre au NE), eau sud, plages
# =====================================================================================
water = np.zeros((H, NEW_W), bool); water[:, :OLD_W] = water_campus
def wobble(x, seed, amp=1):
    return int(round(amp * np.sin(x / 2.3 + seed) * np.sin(x / 5.1 + seed * 2)))
S_shore = {}; N_shore = {}
for x in range(OLD_W, NEW_W):
    t = min(max((x - 60) / 12, 0), 1); s = 38 - 16 * (t * t * (3 - 2 * t))            # 38 -> 22 (S lissé)
    S_shore[x] = int(round(s)) + (wobble(x, 1) if x >= 74 else 0)
    if x <= 64: N_shore[x] = 21
    else:
        t = min((x - 64) / 16, 1); N_shore[x] = int(round(21 - 21 * (t * t * (3 - 2 * t))))
    for y in range(N_shore[x], S_shore[x] + 1): water[y, x] = True
    ys = 83 + (1 if (x // 4) % 3 == 1 else 0)                                         # mer sud : bord 83/84
    water[ys:, x] = True

# =====================================================================================
# 4. Textures clonées : herbe, sable sec, sable immergé (blocs 4x4 tuiles du campus)
# =====================================================================================
fl = P["floor"][..., :3].astype(int)
def kind(x, y):
    t = fl[y*T:(y+1)*T, x*T:(x+1)*T]; r, g, b = t.mean(axis=(0, 1)); s = t.std(axis=(0, 1)).mean()
    if water_campus[y, x]: return "w"
    if g > r + 12 and g > b + 25: return "g"
    gv, gh = np.abs(np.diff(t, axis=0)).mean(), np.abs(np.diff(t, axis=1)).mean()
    if 150 < r < 200 and r - b >= 50 and b < 125 and g > 0.78 * r and s < 18 and gv <= 4 and gh <= 4: return "s"   # sable beige (plages sud/est)
    if r > 200 and g > 165 and b < 120 and s < 16 and gv <= 5 and gh <= 5: return "y"                          # sable jaune (plateau)
    return "?"
K = np.array([[kind(x, y) for x in range(OLD_W)] for y in range(H)])
def blocks(k, n):
    return [(x, y) for y in range(H - n + 1) for x in range(OLD_W - n + 1) if (K[y:y+n, x:x+n] == k).all()]
NB = {"g": 4, "s": 2, "w": 4, "y": 2}
B = {}
for k in NB:
    while True:
        B[k] = blocks(k, NB[k])
        if len(B[k]) >= 30 or NB[k] == 1: break
        NB[k] //= 2
# herbe : on écarte les blocs de teinte atypique (médiane des blocs ± 10) pour éviter les carrés visibles
def block_mean(bx, by, n): return P["floor"][by*T:(by+n)*T, bx*T:(bx+n)*T, :3].reshape(-1, 3).mean(axis=0)
gm = np.array([block_mean(bx, by, NB["g"]) for bx, by in B["g"]]); med = np.median(gm, axis=0)
gs = np.array([P["floor"][by*T:(by+NB["g"])*T, bx*T:(bx+NB["g"])*T, :3].std(axis=(0, 1)).mean() for bx, by in B["g"]])
keep = (np.abs(gm - med).max(axis=1) < 10) & (gs <= np.percentile(gs, 65))          # teinte typique, peu de touffes
B["g"] = [b for b, k in zip(B["g"], keep) if k]
B_g, B_s, B_w, B_y = B["g"], B["s"], B["w"], B["y"]
print("blocs : herbe", len(B_g), "x", NB["g"], "; sable", len(B_s), "x", NB["s"], "; immergé", len(B_w), "x", NB["w"], "; jaune", len(B_y), "x", NB["y"])
def tone(x0, x1, y0, y1):                                                        # ton moyen des tuiles de sable pur d'une zone du campus
    vals = [fl[y*T:(y+1)*T, x*T:(x+1)*T].mean(axis=(0, 1)) for y in range(y0, y1) for x in range(x0, x1)]
    vals = [v for v in vals if v[0] - v[2] >= 45 and v[1] < v[0]]
    return np.mean(vals, axis=0).astype(np.float32)
TONE_S = tone(56, 60, 70, 83)                                                    # plage sud au bord du campus (~182,158,118)
TONE_Y = tone(57, 60, 8, 10)                                                     # sentier jaune au bord du campus (~215,184,99)
def texture(blocks_, n, seed, w_tiles=NEW_W - OLD_W, unify=False):
    """mosaïque de blocs n x n tuiles tirés du campus ; unify : chaque bloc ramené au ton donné (ou médian du lot)"""
    r = np.random.default_rng(seed); out = np.zeros((H * T, w_tiles * T, 4), np.uint8)
    med = None
    if unify is not False:
        means = np.array([P["floor"][by*T:(by+n)*T, bx*T:(bx+n)*T, :3].reshape(-1, 3).mean(axis=0) for bx, by in blocks_])
        med = np.median(means, axis=0) if unify is True else np.asarray(unify, np.float32)
    for ty in range(0, H, n):
        for tx in range(0, w_tiles, n):
            bx, by = blocks_[r.integers(len(blocks_))]
            blk = P["floor"][by*T:(by+n)*T, bx*T:(bx+n)*T].astype(np.float32)
            if med is not None: blk[..., :3] += med - blk[..., :3].reshape(-1, 3).mean(axis=0)
            h, w = min(n*T, out.shape[0] - ty*T), min(n*T, out.shape[1] - tx*T)
            out[ty*T:ty*T+h, tx*T:tx*T+w] = np.clip(blk[:h, :w], 0, 255)
    return out
TEX_G, TEX_S, TEX_W, TEX_Y = texture(B_g, NB["g"], 1), texture(B_s, NB["s"], 2, unify=TONE_S), texture(B_w, NB["w"], 3), texture(B_y, NB["y"], 8, unify=TONE_Y)
print("tons sable : beige", TONE_S.astype(int), "jaune", TONE_Y.astype(int))

# ---- masque sable (px) : distance à l'eau <= largeur de plage (+ bruit), + zones de continuité
EW = (NEW_W - OLD_W) * T
water_px = np.kron(water[:, OLD_W:], np.ones((T, T), bool))
dist = ndi.distance_transform_edt(~water_px)                      # px jusqu'à l'eau
beach_w = np.full(water_px.shape, 3.2 * T, np.float32)
xs_px = np.arange(EW)[None, :]; ys_px = np.arange(H * T)[:, None]
beach_w = beach_w + 0.8 * T * np.sin(xs_px / 97.0) * np.cos(ys_px / 71.0)
noise = value_noise(H * T, EW, 40, 5)
sand = dist <= beach_w + (noise - 0.5) * 1.2 * T
# continuité avec le bord du campus : sable est de Hans Zimmer (l. 39-46), plage sud (l. >= 70 au bord)
cont = np.zeros_like(sand)
for y in range(39 * T, 47 * T):
    lim = int((47 * T - y) / (8 * T) * 3.5 * T)                 # biseau 3,5 tuiles -> 0
    cont[y, :max(lim, 0)] = True
sand |= cont
# plage sud : bord haut de la plage, l. 70 au bord du campus -> l. 75-76 (ondulé) vers l'est
topS = np.array([70 * T + (5.5 * T) * min((x / T) / 8, 1) ** 0.8 + 6 * np.sin(x / 53.0) for x in range(EW)])
sand |= ys_px >= topS[None, :]
# pied du plateau : bande de sable l. 17-21 côté est (continuité), voir anneau plus bas
sand[int(16.6 * T):21 * T, :4 * T] = True
sand_soft = ndi.gaussian_filter(sand.astype(np.float32), 1.2)
ragged = np.clip((sand_soft - 0.5) * 6 + (noise - 0.5) * 2.2 + 0.5, 0, 1)
ragged = (ragged > 0.5).astype(np.float32)
ragged = ndi.gaussian_filter(ragged, 0.7)[..., None]
# ton du sable : jaune au nord du bras de mer (plateau, rive nord-est), beige au sud (rive Hans Zimmer, plage sud)
Sline = np.array([S_shore[OLD_W + x // T] * T for x in range(EW)])
yellow = (ys_px < Sline[None, :] - T) & (ys_px < 40 * T)
TEX_SAND = np.where(yellow[..., None], TEX_Y, TEX_S)
ext_floor = (TEX_SAND.astype(np.float32) * ragged + TEX_G.astype(np.float32) * (1 - ragged))
ext_floor = np.where(water_px[..., None], TEX_W.astype(np.float32), ext_floor)
C["floor"][:, OLD_W * T:] = np.clip(ext_floor, 0, 255).astype(np.uint8)
C["floor"][:, OLD_W * T:, 3] = 255
# raccord : les 4 dernières colonnes du campus (herbe/sable seulement à cet endroit) sont prolongées en miroir
# et fondues dans la texture de l'extension avec un bord bruité -> pas de ligne verticale à x = 60
BW = 4 * T
mirror = C["floor"][:, OLD_W * T - BW:OLD_W * T][:, ::-1].astype(np.float32)
fade = np.clip(1 - (np.arange(BW) / BW), 0, 1)[None, :] ** 0.8
nz2 = value_noise(H * T, BW, 48, 21)
alpha_m = np.clip(fade + (nz2 - 0.5) * 0.5, 0, 1)
alpha_m[np.kron(water[:, OLD_W:OLD_W + 4], np.ones((T, T), bool))] = 0          # pas sous l'eau
alpha_m = alpha_m[..., None]
reg = C["floor"][:, OLD_W * T:OLD_W * T + BW].astype(np.float32)
C["floor"][:, OLD_W * T:OLD_W * T + BW, :3] = np.clip(reg[..., :3] * (1 - alpha_m) + mirror[..., :3] * alpha_m, 0, 255).astype(np.uint8)
shm = C["shadow"][:, OLD_W * T - BW:OLD_W * T][:, ::-1].astype(np.float32)
shm[..., 3] *= alpha_m[..., 0]
alpha_over(C["shadow"], shm.astype(np.uint8), OLD_W * T, 0)

# =====================================================================================
# 5. Anneau rocheux du plateau : fermeture à l'est (chunks du campus, floor + ombre)
#    (58-60, 11-13) descend vers le SE ; la falaise sud (56-60, 16-19) monte vers le NE :
#    elles se rejoignent juste au-delà de x=60.
# =====================================================================================
def copy_chunk(src_tiles, dst_tile, px_w=None, px_x0=0, layers=("floor", "shadow")):
    sx0, sy0, sx1, sy1 = src_tiles; dx, dy = dst_tile
    for n in layers:
        blk = P[n][sy0*T:sy1*T, sx0*T + px_x0:sx1*T]
        if px_w: blk = blk[:, :px_w]
        if n == "floor": C[n][dy*T:dy*T + blk.shape[0], dx*T:dx*T + blk.shape[1]] = blk
        else: alpha_over(C[n], blk, dx * T, dy * T)
RING = json.load(open(os.path.join(PAINT, "ring.json"))) if os.path.exists(os.path.join(PAINT, "ring.json")) else []
for item in RING: copy_chunk(tuple(item[0]), tuple(item[1]), item[2] if len(item) > 2 else None, item[3] if len(item) > 3 else 0)
for item in RING:                                                 # collisions des rochers copiés
    (sx0, sy0, sx1, sy1), (dx, dy) = item[0], item[1]
    for yy in range(sy1 - sy0):
        for xx in range(sx1 - sx0):
            if campus.coll[sy0 + yy, sx0 + xx]: coll_px[(dy+yy)*T:(dy+yy+1)*T, (dx+xx)*T:(dx+xx+1)*T] = 255

# =====================================================================================
# 6. Chemins : (a) chemin courbe terre battue -> parvis ; (b) sentier de sable du plateau
# =====================================================================================
def path_band(x_from, x_to, centre_fn, half=T - 3, amp=5.0, seed=3):
    """masque (px, pleine largeur) d'une bande autour de centre_fn(x) (px), bords ondulés fondus"""
    w = NEW_W * T; xs = np.arange(w); cy = np.array([centre_fn(x) for x in xs])
    top = cy - half + amp * np.sin(xs / 37.0 + seed) + 0.6 * amp * np.sin(xs / 11.0 + 1)
    bot = cy + half + amp * np.sin(xs / 41.0 + 2 + seed) + 0.6 * amp * np.sin(xs / 13.0)
    yy = np.arange(H * T)[:, None]
    mk = ((yy >= top[None, :]) & (yy <= bot[None, :]) & (xs[None, :] >= x_from) & (xs[None, :] <= x_to)).astype(np.float32)
    return ndi.gaussian_filter(mk, 2.5)
PATH_PTS = [(44.3, 57.0), (50, 57.0), (56, 57.6), (61, 59.5), (66, 62.5), (71, 66.5), (76, 68.3), (80, 68.3), (83, 66.5), (84, 64.5), (84, 62.0)]
def catmull(pts, n=40):
    P_ = [pts[0]] + list(pts) + [pts[-1]]; out = []
    for i in range(1, len(P_) - 2):
        p0, p1, p2, p3 = (np.array(P_[j], np.float32) for j in (i - 1, i, i + 1, i + 2))
        for k in range(n):
            t = k / n
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
    out.append(np.array(pts[-1], np.float32)); return out
def spline_mask(pts_tiles, half_px, noise_amp=8.0, seed=13):
    w, h = NEW_W * T, H * T; yy, xx = np.mgrid[0:h, 0:w]
    pts = [p * T for p in catmull(pts_tiles)]
    d = np.full((h, w), 1e9, np.float32)
    for a, b_ in zip(pts, pts[1:]):
        ax, ay = a; bx, by = b_; vx, vy = bx - ax, by - ay; L2 = max(vx * vx + vy * vy, 1e-6)
        t = np.clip(((xx - ax) * vx + (yy - ay) * vy) / L2, 0, 1)
        d = np.minimum(d, np.sqrt((xx - (ax + t * vx)) ** 2 + (yy - (ay + t * vy)) ** 2))
    nz = value_noise(h, w, 34, seed)
    return ndi.gaussian_filter(((d + (nz - 0.5) * noise_amp * 2) <= half_px).astype(np.float32), 2.0)
BEIGE = np.array([198, 176, 132], np.float32)
def sand_tex_full(target=None, seed=4, pool=None, n=None):
    out = texture(pool or B_s, n or NB["s"], seed, NEW_W, unify=(TONE_Y if pool is B_y else TONE_S))[..., :3].astype(np.float32)
    if target is not None:
        for ty in range(0, H * T, T):
            for tx in range(0, NEW_W * T, T):
                blk = out[ty:ty+T, tx:tx+T]; blk += target - blk.reshape(-1, 3).mean(axis=0)
    return np.clip(ndi.gaussian_filter(out, (0.6, 0.6, 0)), 0, 255)
mk = spline_mask(PATH_PTS, T - 2)[..., None]
C["floor"][..., :3] = np.clip(C["floor"][..., :3] * (1 - mk) + sand_tex_full(BEIGE) * mk, 0, 255).astype(np.uint8)
# sentier du plateau : de (60, 9) vers le SE, le long de l'extérieur de l'anneau, jusqu'à la plage
def trail_centre(x):
    pts = [(59.5 * T, 9.3 * T), (62 * T, 11.5 * T), (64 * T, 14.5 * T), (65 * T, 18 * T), (65.5 * T, 21 * T)]
    if x <= pts[0][0]: return pts[0][1]
    for (xa, ya), (xb, yb) in zip(pts, pts[1:]):
        if xa <= x <= xb: t = (x - xa) / (xb - xa); return ya + (yb - ya) * t
    return pts[-1][1]
# le sentier est raide : on le dessine par colonnes ET par lignes (masque = union) pour éviter les trous
def trail_mask():
    w, h = NEW_W * T, H * T; yy, xx = np.mgrid[0:h, 0:w]
    pts = [(59.5, 9.3), (62, 11.5), (64, 14.5), (65, 18), (65.5, 21.2)]
    d = np.full((h, w), 1e9, np.float32)
    for (xa, ya), (xb, yb) in zip(pts, pts[1:]):
        ax, ay, bx, by = xa*T, ya*T, xb*T, yb*T
        vx, vy = bx - ax, by - ay; L2 = vx*vx + vy*vy
        t = np.clip(((xx - ax) * vx + (yy - ay) * vy) / L2, 0, 1)
        dd = np.sqrt((xx - (ax + t*vx))**2 + (yy - (ay + t*vy))**2); d = np.minimum(d, dd)
    nz = value_noise(h, w, 30, 9)
    return ndi.gaussian_filter(((d + (nz - 0.5) * 10) <= T - 2).astype(np.float32), 2.0)
mk2 = trail_mask()[..., None]; mk2[:, :OLD_W * T + 2] = 0                     # ne touche pas au campus
C["floor"][..., :3] = np.clip(C["floor"][..., :3] * (1 - mk2) + sand_tex_full(None, 6, B_y, NB["y"]) * mk2, 0, 255).astype(np.uint8)

# =====================================================================================
# 7. Décor cloné (arbres, palmiers, buissons, fleurs, rochers) — positions en tuiles (coin haut-gauche)
# =====================================================================================
PROPS = json.load(open(os.path.join(PAINT, "props.json"))) if os.path.exists(os.path.join(PAINT, "props.json")) else []
for name, tx, ty in PROPS:                      # (tx, ty) = tuile où atterrit la tuile haut-gauche de l'objet
    o = OBJ[name]; x0, y0 = o["box"][:2]
    place(o, C, coll_px, tx * T + x0 % T, ty * T + y0 % T)
print("décor :", len(PROPS), "objets")

# =====================================================================================
# 8. Bâtiment SACEM : base -> walls, toit -> roof, collisions enveloppe, porte
# =====================================================================================
PX, PY = 68 * T, 31 * T                     # porte colonne 84 (16 + 68) ; bas du parvis ligne 62,8 comme à 0,83
base = load_rgba(os.path.join(SACEM, "ps_base.png")); roof = load_rgba(os.path.join(SACEM, "ps_toit.png"))
alpha_over(C["walls"], base, PX, PY); alpha_over(C["roof"], roof, PX, PY)
Wt, Ht = base.shape[1] // T, base.shape[0] // T
Bf = base.astype(int); ext = np.asarray(Image.alpha_composite(Image.fromarray(base), Image.fromarray(roof))).astype(int)
S_, OFF = 0.72, (21, 0)
sample = Bf[int(1000*S_)+OFF[1]:int(1040*S_)+OFF[1], int(560*S_)+OFF[0]:int(620*S_)+OFF[0], :3].reshape(-1, 3)
floor_c = np.median(sample, axis=0); dist_f = np.abs(Bf[..., :3] - floor_c).sum(axis=2)
floorm = (dist_f < 40) & (Bf[..., 3] > 127)
r_, g_, b_ = Bf[..., 0], Bf[..., 1], Bf[..., 2]
rug = (Bf[..., 3] > 127) & (((r_ > 150) & (g_ < 80) & (b_ < 90)) | ((abs(r_ - 100) < 30) & (abs(g_ - 122) < 30) & (abs(b_ - 150) < 30)))
cx0, cy0 = int(780*S_)+OFF[0], int(730*S_)+OFF[1]
lab, n = ndi.label(rug); keep = set(np.unique(lab[cy0-60:cy0+60, cx0-120:cx0+120])) - {0}; rug = np.isin(lab, list(keep))
mat = (Bf[..., 3] > 127) & (r_ < 110) & (g_ < 110) & (b_ < 130) & (abs(r_ - g_) < 15)
lab, n = ndi.label(mat); yy_, xx_ = int(1280*S_)+OFF[1], int(704*S_)+OFF[0]; mat = (lab == lab[yy_, xx_]) if lab[yy_, xx_] else np.zeros_like(mat)
# Règle (demande de David) : on marche sur le SOL du hall (open space libre) ; tout le reste du bâtiment bloque :
# murs, faces intérieures des murs (sinon on « grimpe » sur le mur du fond), bibliothèques, présentoir.
# Derrière le bâtiment, seule l'emprise de la BASE bloque (pas celle du toit) -> on peut passer juste derrière le mur.
opaque = Bf[..., 3] > 127
rf_ = np.maximum(r_, 1)
floorc = opaque & (r_ > 196) & (np.abs(g_ / rf_ - 0.87) < 0.05) & (b_ / rf_ < 0.765) & (b_ / rf_ > 0.66)   # beige du sol (r >= 203 partout) ; les faces des murs sont plus sombres (r ~ 170) ou plus grises (b/r ~ 0,79)
wall = opaque & (((r_ > 175) & (g_ > 175) & (b_ > 175) & (np.abs(r_ - b_) < 40))            # murs blancs / gris clair
                 | ((b_ > r_ + 30) & (b_ > 60) & (r_ < 90)))                                  # bandeaux bleu marine
wall = ndi.binary_closing(wall, iterations=2)
hall_seed = (int(730 * S_) + OFF[1], int(780 * S_) + OFF[0])                                  # centre du hall
lab, n = ndi.label(ndi.binary_closing(floorc, iterations=2)); hall_px = lab == lab[hall_seed]
apron_seed = (int(1300 * S_) + OFF[1], int(704 * S_) + OFF[0])                                # paillasson / parvis
lab, n = ndi.label(opaque & ~wall); apron_px = ((lab == lab[apron_seed]) if lab[apron_seed] else np.zeros_like(hall_px)) & ~hall_px
# le parvis ne dépasse pas l'auvent (y >= 1000 source) ni +/- 130 px autour de l'axe de la porte (sinon, sans auvent
# dans la base, la composante remonte le long des faces intérieures des murs)
yy_g, xx_g = np.mgrid[0:Ht * T, 0:Wt * T]
apron_px &= (yy_g >= int(1000 * S_) + OFF[1]) & (np.abs(xx_g - (704 * S_ + OFF[0])) <= 130)
# Présentoir (tableau SACEM) : franchissable (demande de David) -> compté comme sol ; la face du mur derrière reste bloquée
pb = (slice(int(630 * S_) + OFF[1], int(785 * S_) + OFF[1]), slice(int(415 * S_) + OFF[0], int(510 * S_) + OFF[0]))
wallface = (np.abs(g_ / rf_ - 0.887) < 0.04) & (b_ / rf_ > 0.76) & (b_ / rf_ < 0.83)
pres = np.zeros_like(hall_px); pres[pb] = opaque[pb] & ~hall_px[pb] & ~wallface[pb]
hall_px = hall_px | pres
walk_t = np.zeros((Ht, Wt), bool); opq_t = np.zeros((Ht, Wt), bool)
for ty in range(Ht):
    for tx in range(Wt):
        walk_t[ty, tx] = hall_px[ty*T:(ty+1)*T, tx*T:(tx+1)*T].mean() >= 0.5 or apron_px[ty*T:(ty+1)*T, tx*T:(tx+1)*T].mean() >= 0.1
        opq_t[ty, tx] = opaque[ty*T:(ty+1)*T, tx*T:(tx+1)*T].mean() >= 0.15
block = opq_t & ~walk_t
# Bibliothèques (bois) contre le mur du fond : bloquées elles aussi (seuls meubles conservés par David dans le hall vide)
wood = opaque & (r_ > 100) & (r_ > g_ + 25) & (g_ > b_ + 10) & (b_ < 110) & (r_ < 230)
lab, n = ndi.label(wood); sizes = ndi.sum(wood, lab, range(1, n + 1))
shelf = ndi.binary_fill_holes(ndi.binary_closing(np.isin(lab, [i + 1 for i, s_ in enumerate(sizes) if s_ >= 2500]), iterations=3))
n_shelf = 0
for ty in range(Ht):
    for tx in range(Wt):
        if shelf[ty*T:(ty+1)*T, tx*T:(tx+1)*T].mean() >= 0.25 and not block[ty, tx]: block[ty, tx] = True; n_shelf += 1
print("bibliothèques :", n_shelf, "tuiles bloquées")
door_col = (int(704*S_)+OFF[0]) // T; door_rows = range((int(1000*S_)+OFF[1]) // T, Ht)   # de l'auvent au bas du parvis
for ty in door_rows:
    for tx in (door_col - 1, door_col, door_col + 1): block[ty, tx] = False
print("hall praticable :", int(walk_t.sum()), "tuiles ; entrée libre colonnes", (PX // T) + door_col - 1, "à", (PX // T) + door_col + 1, "lignes", (PY // T) + door_rows[0], "à", (PY // T) + Ht - 1)
for ty in range(Ht):
    for tx in range(Wt):
        if block[ty, tx]: coll_px[PY + ty*T:PY + (ty+1)*T, PX + tx*T:PX + (tx+1)*T] = 255
print("bâtiment : collisions", int(block.sum()), "tuiles ; porte colonne", (PX // T) + door_col)
# Profondeur (demande de David, 10/09) : les parties du bâtiment situées DEVANT le sol à l'écran (mur avant, moitié basse des
# murs latéraux, encadrement de la porte) passent dans la peinture `above` (dessinée par-dessus le woka) ; celles situées
# derrière (mur du fond, bibliothèques) restent dans `walls`. Règle : pour chaque pixel opaque hors sol, le pixel de sol
# le plus proche est-il au-dessus (=> devant) ou au-dessous (=> derrière) ?
ground = hall_px | apron_px
dist, (iy_, ix_) = ndi.distance_transform_edt(~hall_px, return_indices=True)     # référence : le sol du hall seulement
yy_b = np.arange(Ht * T)[:, None]                                                  # (le parvis, au même niveau que le mur avant, fausserait le test)
# Tout le bâtiment passe devant le woka (il ne peut chevaucher que ce que ses collisions l'autorisent à approcher : bande
# basse des murs avant/latéraux, face intérieure du mur du fond depuis l'extérieur), SAUF la bande de 40 px des éléments
# posés juste au-dessus du sol (pied du mur du fond, bas des bibliothèques) : là, un woka sur le sol est devant eux.
near_floor_below = (iy_ > yy_b) & (dist <= 40)
front = opaque & ~ground & (dist < 400) & ~near_floor_below
front = ndi.binary_opening(front, iterations=1)                         # sans miettes isolées
fb = base.copy(); fb[~front] = 0                                        # pixels « devant »
wb = base.copy(); wb[front] = 0                                         # pixels « derrière » + sol
C["walls"][PY:PY + Ht * T, PX:PX + Wt * T] = 0
alpha_over(C["walls"], wb, PX, PY); alpha_over(C["above"], fb, PX, PY)
print("profondeur : ", int(front.sum()), "px de murs avant passés dans above")
# aire roof_sacem = cadre du bâtiment (base)
ys, xs = np.where(base[..., 3] > 0)
areas = [{"name": "roof_sacem", "x": PX + int(xs.min()), "y": PY + int(ys.min()), "width": int(xs.max() - xs.min() + 1), "height": int(ys.max() - ys.min() + 1)}]

# =====================================================================================
# 9. Eau : collisions sur toutes les tuiles d'eau de l'extension ; water.json (autotile) pour x >= 57
# =====================================================================================
for y in range(H):
    for x in range(OLD_W, NEW_W):
        if water[y, x]: coll_px[y*T:(y+1)*T, x*T:(x+1)*T] = 255
def W_(x, y): return water[y, x] if 0 <= x < NEW_W and 0 <= y < H else True
INTERIOR = [14, 25, 26, 27, 38]
def autotile(x, y):
    N, S, Wn, E = W_(x, y-1), W_(x, y+1), W_(x-1, y), W_(x+1, y)
    NW, NE, SW, SE = W_(x-1, y-1), W_(x+1, y-1), W_(x-1, y+1), W_(x+1, y+1)
    if not N and not Wn: return 1
    if not N and not E: return 3
    if not S and not Wn: return 49
    if not S and not E: return 40
    if not N: return 2
    if not S: return 50
    if not Wn: return 24
    if not E: return 28
    if not NW: return 13
    if not NE: return 15
    if not SW: return 37
    if not SE: return 39
    return INTERIOR[R.integers(len(INTERIOR))]
wj = {"tileset": "coolio_animated_water", "tiles": {}}          # x >= 57 : les tuiles du bord du campus sont recalculées aussi
for y in range(H):
    for x in range(57, NEW_W):
        if water[y, x]: wj["tiles"][f"{x},{y}"] = autotile(x, y)
print("eau :", len(wj["tiles"]), "tuiles (x >= 57)")

# =====================================================================================
# 10. Godray étendu (rayons à 45° : continuité le long de la diagonale)
# =====================================================================================
gr = load_rgba(os.path.join(REPO, "tilesets", "God ray linear 45 tall.png"))
GW, GH = gr.shape[1], gr.shape[0]; NGW = (NEW_W + 2) * T
g2 = np.zeros((GH, NGW, 4), np.uint8); g2[:, :GW] = gr
yy, xx = np.mgrid[0:GH, GW:NGW]
d = np.minimum(yy, xx - (GW - 1)); sx, sy = xx - d, yy - d
top = sy <= 0
cidx = xx - yy; cidx = np.where(cidx >= GW, 2 * GW - 1 - cidx, cidx); cidx = np.clip(cidx, 0, GW - 1)
vals = np.where(top[..., None], gr[0][cidx], gr[np.clip(sy, 0, GH - 1), np.clip(sx, 0, GW - 1)])
g2[:, GW:] = vals

# =====================================================================================
# 11. Sorties
# =====================================================================================
os.makedirs(OUT_TS, exist_ok=True); os.makedirs(PAINT, exist_ok=True)
for n in PAINTINGS: save_rgba(C[n], os.path.join(OUT_TS, f"coolio_{n}.png"))
save_rgba(C["shadow"], os.path.join(OUT_TS, "general shadow.png"))
save_rgba(g2, os.path.join(OUT_TS, "God ray linear 45 tall.png"))
coll_img = np.zeros((H * T, NEW_W * T, 4), np.uint8); coll_img[coll_px > 0] = (255, 0, 0, 255)
save_rgba(coll_img, os.path.join(PAINT, "collisions.png"))
json.dump(wj, open(os.path.join(PAINT, "water.json"), "w"))
json.dump(clears, open(os.path.join(PAINT, "clears.json"), "w"))
json.dump(areas, open(os.path.join(PAINT, "areas.json"), "w"))
print("peintures écrites dans", OUT_TS)
