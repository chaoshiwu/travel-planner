#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""路书生成器 · 一条命令产出「单文件交互路书 + KML」。

用法：
    python build.py <行程目录或 trip.json> [-o 输出目录] [--no-kml]

输入（同目录下）：
    trip.json      行程数据（天数 / 点位 / 提醒），人写
    sections.json  文案区块（天气 / 交通 / 住宿 / 预算 / 避坑…），人写
    routes.json    路网几何（可选，机器生成；缺省则页面用虚线连点位）

输出：
    <title>.html   单文件交互路书（Leaflet 已内联，零外网依赖）
    <kmlFile>      KML（WGS-84，奥维 / 两步路 / 高德网页版可导入）
"""
import argparse
import json
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(os.path.dirname(HERE), "assets")


# ============================================================ 坐标：GCJ-02 → WGS-84
# 与页面 JS 的 gcjToWgs 逐行对应（单步反算），保证两边数值一致
_A = 6378245.0
_EE = 0.00669342162296594623


def _t_lat(x, y):
    r = -100 + 2 * x + 3 * y + .2 * y * y + .1 * x * y + .2 * math.sqrt(abs(x))
    r += (20 * math.sin(6 * x * math.pi) + 20 * math.sin(2 * x * math.pi)) * .6667
    r += (20 * math.sin(y * math.pi) + 40 * math.sin(y / 3 * math.pi)) * .6667
    r += (160 * math.sin(y / 12 * math.pi) + 320 * math.sin(y * math.pi / 30)) * .6667
    return r


def _t_lng(x, y):
    r = 300 + x + 2 * y + .1 * x * x + .1 * x * y + .1 * math.sqrt(abs(x))
    r += (20 * math.sin(6 * x * math.pi) + 20 * math.sin(2 * x * math.pi)) * .6667
    r += (20 * math.sin(x * math.pi) + 40 * math.sin(x / 3 * math.pi)) * .6667
    r += (150 * math.sin(x / 12 * math.pi) + 300 * math.sin(x / 30 * math.pi)) * .6667
    return r


def gcj_to_wgs(lng, lat):
    dlat = _t_lat(lng - 105, lat - 35)
    dlng = _t_lng(lng - 105, lat - 35)
    rl = lat / 180 * math.pi
    magic = 1 - _EE * math.sin(rl) ** 2
    sq = math.sqrt(magic)
    dlat = (dlat * 180) / ((_A * (1 - _EE)) / (magic * sq) * math.pi)
    dlng = (dlng * 180) / (_A / sq * math.cos(rl) * math.pi)
    return lng - dlng, lat - dlat


# ============================================================ 小工具
def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def load(path, default=None):
    if not os.path.exists(path):
        if default is not None:
            return default
        raise SystemExit("缺少文件：%s" % path)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def legend_label(day):
    """'Day 1 · 去程：进城早餐 → …' → 'Day 1 去程'"""
    m = re.match(r"^(Day\s*\d+)\s*[·:：]\s*([^：:·]+)", day.get("name", ""))
    if m:
        return "%s %s" % (m.group(1), m.group(2).strip())
    return day.get("name", "").split("：")[0].strip()


def total_km(days):
    v = 0.0
    for d in days:
        m = re.search(r"(\d+(?:\.\d+)?)\s*km", d.get("km", "") or "")
        if m:
            v += float(m.group(1))
    return v


# ============================================================ 区块渲染
def render_map(trip):
    """地图卡片：结构固定，图例按天数自动生成"""
    lines = [
        '<div class="map-card">',
        '  <div class="map-head">',
        '    <h2>🗺 交互地图（点气泡可导航）</h2>',
        '    <button class="kml-btn" onclick="downloadKML()">⬇ 下载 KML 导入手机地图</button>',
        '  </div>',
        '  <div class="maptabs" id="mapTabs"></div>',
        '  <div id="map"></div>',
        '  <div class="legend">',
    ]
    for d in trip["days"]:
        if d.get("noLine"):
            continue
        lines.append('    <span><i style="background:%s"></i>%s</span>'
                     % (d.get("color", "#8B6914"), legend_label(d)))
    if trip.get("legendTail"):
        lines.append('    <span><i style="background:#8E959B"></i>%s</span>'
                     % trip["legendTail"])
    lines.append("  </div>")
    tip = (trip.get("mapTip") or "").strip()
    if tip:
        lines.append('  <div class="map-tip">%s</div>' % tip)
    lines.append("</div>")
    return "\n".join(lines)


DEFAULT_MAPTIP = (
    "行车线为 OSRM 实路几何（不是直连虚线）；底图为高德路网 GCJ-02，坐标已纠偏。<br>\n"
    "  用高德导航：直接点气泡里的「<b>高德导航</b>」——但<b>微信 / QQ 里打开时须先"
    "「在浏览器中打开」</b>，否则调不起高德 App（高德官方限制）。<br>\n"
    "  想把整条路线导进高德看，走 KML：入口见右上角导出面板；微信里下载会被拦，"
    "点「复制全部内容」即可。同目录另附 <b>{{KML_FILE}}</b>，内容完全一致。"
)


# ============================================================ KML
def build_kml(trip):
    """结构与页面 downloadKML() 完全一致（点 → 线，WGS-84）"""
    out = ['<?xml version="1.0" encoding="UTF-8"?>'
           '<kml xmlns="http://www.opengis.net/kml/2.2"><Document>']

    def coord(lng, lat):
        w = gcj_to_wgs(lng, lat)
        return "%.6f,%.6f,0" % (w[0], w[1])

    for di, d in enumerate(trip["days"]):
        sid = "s%d" % di
        out.append('<Style id="%s"><LineStyle><color>ff40a8d4</color>'
                   '<width>3</width></LineStyle></Style>' % sid)

        for i, p in enumerate(d["places"]):
            out.append('<Placemark><name>%s</name><description>%s</description>\n'
                       '        <Point><coordinates>%s</coordinates></Point></Placemark>'
                       % (esc("%d. %s" % (i + 1, p["name"])),
                          esc(p["time"] + " · " + p["ticket"]),
                          coord(p["lng"], p["lat"])))

        gs = list(d.get("routes") or []) + list(d.get("altRoutes") or [])
        for ri, r in enumerate(gs):
            if not r.get("pts"):
                continue
            coords = " ".join(coord(pt[1], pt[0]) for pt in r["pts"])
            nm = d["name"] + " 行车线" + ((" %d" % (ri + 1)) if len(gs) > 1 else "")
            out.append('<Placemark><name>%s</name><styleUrl>#%s</styleUrl>\n'
                       '        <LineString><coordinates>%s</coordinates></LineString></Placemark>'
                       % (esc(nm), sid, coords))

        if not d.get("noLine") and not [r for r in gs if r.get("pts")]:
            coords = " ".join(coord(p["lng"], p["lat"]) for p in d["places"])
            out.append('<Placemark><name>%s</name><styleUrl>#%s</styleUrl>'
                       '<LineString><coordinates>%s</coordinates></LineString></Placemark>'
                       % (esc(d["name"]), sid, coords))

    out.append("</Document></kml>")
    return "".join(out)


# ============================================================ 主流程
def build(src, outdir=None, make_kml=True):
    src = os.path.abspath(src)
    base = os.path.dirname(src) if os.path.isfile(src) else src
    trip_path = src if os.path.isfile(src) else os.path.join(src, "trip.json")

    trip = load(trip_path)
    sections = load(os.path.join(base, "sections.json"))
    routes = load(os.path.join(base, "routes.json"), default={})

    # 几何回填（routes.json 缺失则该段走虚线兜底）
    def attach(lst):
        for i, r in enumerate(lst or []):
            if not r.get("pts") and r.get("id") in routes:
                new = {"pts": routes[r["id"]]}          # pts 固定放首位，输出稳定
                new.update({k: v for k, v in r.items() if k != "id"})
                lst[i] = new

    for d in trip["days"]:
        attach(d.get("routes"))
        attach(d.get("altRoutes"))

    # 点位坐标自检：必须是 GCJ-02 且在中国境内量级
    bad = []
    for di, d in enumerate(trip["days"]):
        for p in d["places"]:
            if "lng" not in p or "lat" not in p:
                bad.append("Day%d / %s 缺 lng/lat" % (di + 1, p.get("name")))
            elif not (70 < p["lng"] < 140 and 3 < p["lat"] < 55):
                bad.append("Day%d / %s 坐标越界 (%s,%s)"
                           % (di + 1, p.get("name"), p.get("lng"), p.get("lat")))
    if bad:
        raise SystemExit("坐标有误，先修好再生成：\n  " + "\n  ".join(bad))

    n_places = sum(len(d["places"]) for d in trip["days"])
    n_route_pts = sum(len(r.get("pts") or []) for d in trip["days"]
                      for r in (d.get("routes") or []) + (d.get("altRoutes") or []))

    kml_file = trip.get("kmlFile") or (trip["title"] + ".kml")
    trip["kmlFile"] = kml_file

    # 占位替换表
    variables = {
        "{{TITLE}}": trip.get("pageTitle") or trip["title"],
        "{{KML_FILE}}": kml_file,
        "{{N_PLACES}}": str(n_places),
        "{{N_DAYS}}": str(len(trip["days"])),
        "{{TOTAL_KM}}": ("%.0f" % total_km(trip["days"])) if total_km(trip["days"]) else "",
    }

    def fill(text):
        for k, v in variables.items():
            text = text.replace(k, v)
        return text

    trip["mapTip"] = fill(sections.get("mapTip") or trip.get("mapTip") or DEFAULT_MAPTIP)

    blocks = {
        "HERO": sections.get("hero", ""),
        "WEATHER": sections.get("weather", ""),
        "MAP": render_map(trip),
        "OVERVIEW": sections.get("overview", ""),
        "RESERVE": sections.get("reserve", ""),
        "ADVICE": sections.get("advice", ""),
        "BUDGET": sections.get("budget", ""),
        "PITFALLS": sections.get("pitfalls", ""),
        "CHECKLIST": sections.get("checklist", ""),
        "TREE": sections.get("tree", ""),
        "FOOTER": sections.get("footer", trip.get("footer", "")),
    }

    tpl = open(os.path.join(ASSETS, "template.html"), encoding="utf-8").read()
    html = tpl
    for k, v in blocks.items():
        html = html.replace("{{%s}}" % k, fill(v))
    html = fill(html)      # head 里的 {{TITLE}} 等全局变量

    # 引擎与资产（注意顺序：先塞 app.js 再塞叶子模板，避免误替换 app 里的占位符）
    app_js = open(os.path.join(ASSETS, "app.js"), encoding="utf-8").read()
    # 只注入页面真正消费的字段，元数据（pageTitle/kmlFile…）不进运行期
    payload = json.loads(json.dumps(
        {k: trip[k] for k in ("title", "kmlName", "days") if k in trip}))
    for d in payload.get("days", []):
        for r in (d.get("routes") or []) + (d.get("altRoutes") or []):
            r.pop("id", None)
    app_js = app_js.replace("__TRIPDATA__",
                            json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    app_js = app_js.replace("__OVERVIEW__",
                            json.dumps(trip.get("overview", []), ensure_ascii=False))

    html = html.replace("{{LEAFLET_CSS}}",
                        open(os.path.join(ASSETS, "leaflet.css"), encoding="utf-8").read())
    html = html.replace("{{LEAFLET_JS}}",
                        open(os.path.join(ASSETS, "leaflet.js"), encoding="utf-8").read())
    html = html.replace("{{PAGE_CSS}}",
                        open(os.path.join(ASSETS, "page.css"), encoding="utf-8").read())
    html = html.replace("{{APP_JS}}", app_js)

    left = re.findall(r"\{\{[A-Z_]+\}\}", html)
    if left:
        raise SystemExit("模板占位符未替换：%s" % sorted(set(left)))

    outdir = os.path.abspath(outdir or base)
    os.makedirs(outdir, exist_ok=True)
    html_path = os.path.join(outdir, (trip.get("pageTitle") or trip["title"]) + ".html")
    with open(html_path, "w", encoding="utf-8", newline="") as f:
        f.write(html)

    kml_path = None
    if make_kml:
        kml = build_kml(trip)
        kml_path = os.path.join(outdir, kml_file)
        with open(kml_path, "w", encoding="utf-8", newline="") as f:
            f.write(kml)

    # ---------------------------------------------------------- 自检
    n_ok = html.count("<script>") >= 2 and "window.L" in html
    checks = [
        ("Leaflet 已内联", n_ok),
        ("无 CDN 依赖", "unpkg.com" not in html and "cdn." not in html),
        ("KML 导出兜底面板", 'id="kmlMask"' in html and "kmlCopy" in html),
        ("地图容器", 'id="map"' in html),
        ("点位全部上图", html.count("const tripData") == 1),
        ("天数一致", str(len(trip["days"])) in html),
    ]
    print("=" * 56)
    print("  %s" % os.path.basename(html_path))
    print("  页面 %.1f KB · 纯页面 %.1f KB"
          % (os.path.getsize(html_path) / 1024,
             (len(html.encode()) - len(open(os.path.join(ASSETS, "leaflet.js"), "rb").read())
              - len(open(os.path.join(ASSETS, "leaflet.css"), "rb").read())) / 1024))
    print("  %d 天 · %d 个点位 · %d 个路网几何点" % (len(trip["days"]), n_places, n_route_pts))
    if kml_path:
        kml = open(kml_path, encoding="utf-8").read()
        print("  %s %.1f KB · Placemark %d · Point %d · LineString %d"
              % (os.path.basename(kml_path), os.path.getsize(kml_path) / 1024,
                 kml.count("<Placemark>"), kml.count("<Point>"), kml.count("<LineString>")))
        checks.append(("KML 点位数 == 行程点位数", kml.count("<Point>") == n_places))
    print("-" * 56)
    for name, ok in checks:
        print("  %s %s" % ("✓" if ok else "✗", name))
    print("=" * 56)
    if not all(ok for _, ok in checks):
        raise SystemExit("自检未通过，见上面标 ✗ 的项")

    return html_path, kml_path


def main():
    ap = argparse.ArgumentParser(description="生成单文件交互路书 + KML")
    ap.add_argument("src", help="trip.json 或包含 trip.json 的目录")
    ap.add_argument("-o", "--outdir", help="输出目录（默认为输入目录）")
    ap.add_argument("--no-kml", action="store_true", help="不生成 KML")
    a = ap.parse_args()
    build(a.src, a.outdir, not a.no_kml)


if __name__ == "__main__":
    main()
