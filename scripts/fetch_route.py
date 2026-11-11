#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""按途经点抓真实路网几何（OSRM），写入 routes.json。

用法：
    python fetch_route.py <行程目录>

前置：trip.json 里每条 route 写 via（GCJ-02 途经点，含起终点）：
    {"id": "d1_1", "name": "D1 去程", "color": "#C99A2E",
     "via": [["六分地村", 119.4685, 42.4756], ["赤峰城区", 118.8977, 42.2562],
             ["桦木沟", 117.3822, 42.6043]]}

产出：routes.json  {"d1_1": [[lat,lng], ...]}   ← 已转回 GCJ-02，页面直接画

为什么不用高德/腾讯接口：都要 key。OSRM 免费、无 key，几何够准；
国内偏远点位偶尔「路网未连通」，那种情况会明确报出来，改用虚线兜底。
"""
import argparse
import io
import json
import math
import os
import sys
import time
import urllib.request

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

_A = 6378245.0
_EE = 0.00669342162296594323


def _tl(x, y):
    r = -100 + 2 * x + 3 * y + .2 * y * y + .1 * x * y + .2 * math.sqrt(abs(x))
    r += (20 * math.sin(6 * x * math.pi) + 20 * math.sin(2 * x * math.pi)) * 2 / 3
    r += (20 * math.sin(y * math.pi) + 40 * math.sin(y / 3 * math.pi)) * 2 / 3
    r += (160 * math.sin(y / 12 * math.pi) + 320 * math.sin(y * math.pi / 30)) * 2 / 3
    return r


def _tn(x, y):
    r = 300 + x + 2 * y + .1 * x * x + .1 * x * y + .1 * math.sqrt(abs(x))
    r += (20 * math.sin(6 * x * math.pi) + 20 * math.sin(2 * x * math.pi)) * 2 / 3
    r += (20 * math.sin(x * math.pi) + 40 * math.sin(x / 3 * math.pi)) * 2 / 3
    r += (150 * math.sin(x / 12 * math.pi) + 300 * math.sin(x / 30 * math.pi)) * 2 / 3
    return r


def wgs2gcj(lon, lat):
    dlat, dlon = _tl(lon - 105, lat - 35), _tn(lon - 105, lat - 35)
    rad = math.radians(lat)
    m = 1 - _EE * math.sin(rad) ** 2
    sq = math.sqrt(m)
    dlat = (dlat * 180) / ((_A * (1 - _EE)) / (m * sq) * math.pi)
    dlon = (dlon * 180) / (_A / sq * math.cos(rad) * math.pi)
    return lon + dlon, lat + dlat


def gcj2wgs(lon, lat):
    glon, glat = lon, lat
    for _ in range(4):                 # 迭代反算，比单步准（单步差 1~3 m）
        clon, clat = wgs2gcj(glon, glat)
        glon -= clon - lon
        glat -= clat - lat
    return glon, glat


OSRM = ("https://router.project-osrm.org/route/v1/driving/{c}"
        "?overview=full&geometries=geojson&steps=false")
SIMPLIFY = 0.003                        # ≈ 300 m，和手工产物同口径


def fetch(via):
    """via: [(name, lng, lat) GCJ] → (pts[[lat,lng] GCJ], km, min, segs)"""
    w = [gcj2wgs(p[1], p[2]) for p in via]
    url = OSRM.format(c=";".join("%.5f,%.5f" % (x, y) for x, y in w))
    with urllib.request.urlopen(url, timeout=45) as r:
        d = json.load(r)
    if d.get("code") != "Ok" or not d.get("routes"):
        raise RuntimeError("OSRM 未返回路线：%s" % d.get("code"))
    rt = d["routes"][0]
    geo = [(p[0], p[1]) for p in rt["geometry"]["coordinates"]]
    pts = [wgs2gcj(x, y) for x, y in geo]

    simp = [pts[0]]
    for p in pts[1:-1]:
        if abs(p[0] - simp[-1][0]) + abs(p[1] - simp[-1][1]) >= SIMPLIFY:
            simp.append(p)
    simp.append(pts[-1])

    legs = rt.get("legs", [])
    segs = [{"from": via[i][0], "to": via[i + 1][0],
             "km": round(l["distance"] / 1000, 1),
             "min": round(l["duration"] / 60)} for i, l in enumerate(legs)]
    return ([[round(y, 5), round(x, 5)] for x, y in simp],
            round(rt["distance"] / 1000, 1), round(rt["duration"] / 60), segs)


def main():
    ap = argparse.ArgumentParser(description="按 trip.json 里的 route.via 抓真实路网几何，写入 routes.json")
    ap.add_argument("src", nargs="?", default=".", help="行程目录，或直接给 trip.json 路径")
    ap.add_argument("--delay", type=float, default=1.0,
                    help="相邻两次请求的间隔秒数，对公共 OSRM 客气点（默认 1.0）")
    args = ap.parse_args()
    src = args.src
    base = os.path.abspath(src)
    if not os.path.exists(base):
        ap.error("路径不存在：%s" % base)
    trip_path = base if base.endswith(".json") else os.path.join(base, "trip.json")
    base = os.path.dirname(trip_path)
    trip = json.load(open(trip_path, encoding="utf-8"))
    rp = os.path.join(base, "routes.json")
    routes = json.load(open(rp, encoding="utf-8")) if os.path.exists(rp) else {}

    targets = []
    for d in trip["days"]:
        for r in (d.get("routes") or []) + (d.get("altRoutes") or []):
            if r.get("via") and len(r["via"]) >= 2:
                targets.append((d, r))

    if not targets:
        print("trip.json 里没有带 via 的路线，跳过。")
        print("（route 里加 \"via\": [[\"起点\", lng, lat], …]，坐标用 GCJ-02）")
        return

    print("=" * 60)
    for i, (d, r) in enumerate(targets):
        if i and args.delay > 0:
            time.sleep(args.delay)
        rid = r.get("id") or "%s_%d" % (d["name"][:6], len(routes) + 1)
        r["id"] = rid
        tag = "%-12s %s" % (rid, r.get("name", "")[:34])
        try:
            pts, km, mn, segs = fetch([tuple(x) for x in r["via"]])
        except Exception as e:
            print("  ✗ %s  %s" % (tag, e))
            print("    → 该段将用虚线连点位（不影响导航按钮）")
            continue
        routes[rid] = pts
        print("  ✓ %-52s %6.1f km  %4d min  %4d 点"
              % (tag, km, mn, len(pts)))
        for s in segs:
            print("      %s → %s  %5.1f km  %2d min" % (s["from"], s["to"], s["km"], s["min"]))

    with open(rp, "w", encoding="utf-8") as f:
        json.dump(routes, f, ensure_ascii=False, separators=(",", ":"))
    # 把 id 回写到 trip.json，build 时才能对上
    with open(trip_path, "w", encoding="utf-8") as f:
        json.dump(trip, f, ensure_ascii=False, indent=1)
    print("=" * 60)
    print("写入 %s · %d 条路线" % (rp, len(routes)))


if __name__ == "__main__":
    main()
