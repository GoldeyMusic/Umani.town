#!/usr/bin/env node
// Rafraîchit la couverture des calques de peinture de la map de test SACEM avant le build (script "prebuild").
// Règle : la peinture fait foi. Pour chaque calque identité, une tuile existe si sa peinture a des pixels à cet endroit, sinon
// elle est vide. Les tuiles d'autres tilesets (statue animée) ou retournées sont conservées. Toits de l'extension (x >= campus) :
// dans le rectangle paint-sacem/roof-rect.json -> roofs/sacem (effacé par la porte), ailleurs -> roofs/ext (jamais effacé).
// Même règle que tools/build_map.py --paint-coverage. Ainsi une retouche Photoshop des PNG de tilesets/sacem-test/ suffit :
// commit + push, le build met le .tmj à jour tout seul.
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import sharp from "sharp";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const MAP = path.join(ROOT, "sacem-test.tmj");
const PAINT_DIR = path.join(ROOT, "tilesets", "sacem-test");
const ROOF_RECT = path.join(ROOT, "paint-sacem", "roof-rect.json");
const CAMPUS_W = 60;                       // largeur du campus d'origine en tuiles : à droite, c'est l'extension
const T = 32;
const FLIP = 0xF0000000;
// calque (chemin dans les groupes) -> tileset de peinture
const LAYERS = {
    "floor/floor1": "coolio_floor", "floor/shadow": "general shadow", "walls/walls1": "coolio_walls",
    "furniture/furniture1": "coolio_furniture", "outer plant/outer plant": "coolio_outer plant", "above/above": "coolio_above",
};
const ROOF_TS = "coolio_roof";

if (!fs.existsSync(MAP)) { console.log("refresh-coverage : pas de", MAP); process.exit(0); }
const m = JSON.parse(fs.readFileSync(MAP, "utf8"));
const W = m.width, H = m.height;
const tilesets = Object.fromEntries(m.tilesets.map((t) => [t.name, t]));

function findLayer(layers, parts) {
    for (const l of layers) {
        if (l.name !== parts[0]) continue;
        if (parts.length === 1) return l;
        if (l.layers) { const r = findLayer(l.layers, parts.slice(1)); if (r) return r; }
    }
    return null;
}
async function tileMask(tsName) {                                        // true si la tuile a au moins un pixel non transparent
    const ts = tilesets[tsName];
    const file = path.join(ROOT, ts.image);
    const { data, info } = await sharp(file).ensureAlpha().raw().toBuffer({ resolveWithObject: true });
    if (info.width !== W * T || info.height !== H * T)
        throw new Error(`${ts.image} : ${info.width}x${info.height}, attendu ${W * T}x${H * T}`);
    const mask = new Uint8Array(W * H);
    for (let y = 0; y < info.height; y++) {
        const row = y * info.width * 4, ty = (y / T) | 0;
        for (let x = 0; x < info.width; x++) if (data[row + x * 4 + 3] > 0) mask[ty * W + ((x / T) | 0)] = 1;
    }
    return { mask, data, info };
}
function sameTile(px, info, i, j) {
    const [xi, yi, xj, yj] = [(i % W) * T, ((i / W) | 0) * T, (j % W) * T, ((j / W) | 0) * T];
    for (let y = 0; y < T; y++) {
        const a = ((yi + y) * info.width + xi) * 4, b = ((yj + y) * info.width + xj) * 4;
        if (Buffer.compare(px.subarray(a, a + T * 4), px.subarray(b, b + T * 4)) !== 0) return false;
    }
    return true;
}

let changed = 0;
for (const [lpath, tsName] of Object.entries(LAYERS)) {
    const layer = findLayer(m.layers, lpath.split("/"));
    if (!layer) { console.warn("refresh-coverage : calque absent", lpath); continue; }
    const first = tilesets[tsName].firstgid;
    const { mask, data: px, info } = await tileMask(tsName);
    let n = 0;
    for (let i = 0; i < W * H; i++) {
        const g = layer.data[i]; let ng = g;
        if (!g || (g & ~FLIP) === first + i) ng = mask[i] ? first + i : 0;
        else if (!(g & FLIP) && g - first >= 0 && g - first < W * H && sameTile(px, info, g - first, i)) ng = mask[i] ? first + i : 0;
        if (ng !== g) { layer.data[i] = ng; n++; }
    }
    if (n) console.log(`refresh-coverage : ${lpath} : ${n} tuiles mises à jour`);
    changed += n;
}
// toits de l'extension
{
    const roofs = m.layers.find((l) => l.type === "group" && l.name === "roofs");
    const sacem = roofs.layers.find((l) => l.name === "sacem");
    let ext = roofs.layers.find((l) => l.name === "ext");
    if (sacem) {
        if (!ext) {
            ext = { data: new Array(W * H).fill(0), height: H, id: m.nextlayerid++, name: "ext", opacity: 1, type: "tilelayer", visible: true, width: W, x: 0, y: 0 };
            roofs.layers.splice(roofs.layers.indexOf(sacem), 0, ext); changed++;
        }
        const [rx0, ry0, rx1, ry1] = fs.existsSync(ROOF_RECT) ? JSON.parse(fs.readFileSync(ROOF_RECT, "utf8")) : [0, 0, W, H];
        const first = tilesets[ROOF_TS].firstgid;
        const { mask } = await tileMask(ROOF_TS);
        let n = 0;
        for (let i = 0; i < W * H; i++) {
            const x = i % W, y = (i / W) | 0;
            if (x < CAMPUS_W) continue;                                  // zone campus : les 4 calques de toits d'origine, inchangés
            const inRect = x >= rx0 && x <= rx1 && y >= ry0 && y <= ry1;
            const s = mask[i] && inRect ? first + i : 0, e = mask[i] && !inRect ? first + i : 0;
            if (sacem.data[i] !== s) { sacem.data[i] = s; n++; }
            if (ext.data[i] !== e) { ext.data[i] = e; n++; }
        }
        if (n) console.log(`refresh-coverage : toits de l'extension : ${n} tuiles mises à jour`);
        changed += n;
    }
}
if (changed) {
    fs.writeFileSync(MAP, JSON.stringify(m, null, 1), "utf8");          // même mise en forme que json.dump(indent=1)
    console.log(`refresh-coverage : ${MAP} mis à jour (${changed} changements)`);
} else console.log("refresh-coverage : à jour");
