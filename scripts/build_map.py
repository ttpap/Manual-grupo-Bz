import json, math, sys
src, out = sys.argv[1], sys.argv[2]
d = json.load(open(src))
W = 800.0
lat0 = math.radians(-15)
def proj(lon, lat): return (lon * math.cos(lat0), -lat)
def dp(pts, eps):
    if len(pts) < 3: return pts
    a, b = pts[0], pts[-1]
    dx, dy = b[0]-a[0], b[1]-a[1]; L = math.hypot(dx, dy) or 1e-12
    imax, dmax = 0, 0
    for i in range(1, len(pts)-1):
        p = pts[i]
        dd = abs(dy*p[0] - dx*p[1] + b[0]*a[1] - b[1]*a[0]) / L
        if dd > dmax: imax, dmax = i, dd
    if dmax > eps:
        return dp(pts[:imax+1], eps)[:-1] + dp(pts[imax:], eps)
    return [a, b]
polys = {}
for f in d["features"]:
    g = f["geometry"]; uf = f["properties"]["sigla"].lower()
    rings = g["coordinates"] if g["type"] == "Polygon" else [r for p in g["coordinates"] for r in p]
    polys[uf] = (f["properties"]["name"], [[proj(*c[:2]) for c in r] for r in rings])
xs = [p[0] for _, rs in polys.values() for r in rs for p in r]; ys = [p[1] for _, rs in polys.values() for r in rs for p in r]
minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
k = W / (maxx - minx); H = (maxy - miny) * k
res = {}
for uf, (nome, rings) in polys.items():
    parts, best = [], None
    for r in rings:
        pr = [((x-minx)*k, (y-miny)*k) for x, y in r]
        area = 0.5 * sum(pr[i][0]*pr[i-1][1] - pr[i-1][0]*pr[i][1] for i in range(len(pr)))
        if abs(area) < 4: continue  # ilhas minúsculas
        h = len(pr) // 2
        s = dp(pr[:h+1], 0.6)[:-1] + dp(pr[h:], 0.6)
        if len(s) < 4: continue
        parts.append("M" + "L".join(f"{x:.1f} {y:.1f}" for x, y in s) + "Z")
        if best is None or abs(area) > abs(best[0]): best = (area, pr)
    # centróide do maior anel
    if best is None: print("SEM ANEL", uf, [len(r) for r in rings][:5]); continue
    _, pr = best; cx = cy = A = 0
    for i in range(len(pr)):
        x0, y0 = pr[i-1]; x1, y1 = pr[i]; c = x0*y1 - x1*y0; A += c; cx += (x0+x1)*c; cy += (y0+y1)*c
    cx /= (3*A); cy /= (3*A)
    res[uf] = {"n": nome, "d": "".join(parts), "x": round(cx, 1), "y": round(cy, 1)}
js = "// Malha dos estados: codeforamerica/click_that_hood brazil-states.geojson (MIT), simplificada.\nwindow.BR_UFS = " + json.dumps({"w": W, "h": round(H, 1), "p": {"minx": minx, "miny": miny, "k": k, "c": math.cos(lat0)}, "ufs": res}, ensure_ascii=False, separators=(",", ":")) + ";\n"
open(out, "w").write(js)
print(len(js), "bytes", round(H,1))
