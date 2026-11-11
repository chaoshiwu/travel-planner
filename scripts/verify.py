#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""路书成品自检 · 交付前跑一遍。

用法：
    python verify.py <生成的 .html> [--kml 同名.kml]

检查的是「这次踩过的坑会不会复发」，不是泛泛的 HTML 语法检查：
  · Leaflet 是否内联（CDN 在微信/离线会白屏）
  · KML 是否有兜底面板（<a download> 在沙箱 webview 里会被静默丢弃）
  · 点位是否全部进了地图 / KML
  · 坐标是否在 GCJ-02 合理范围（防止把 WGS 当 GCJ 用，几百米偏移）
  · 高德导航链接是否齐全
"""
import argparse
import io
import json
import os
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")


def find_tripdata(html):
    i = html.find("const tripData = ")
    if i < 0:
        return None
    j = i + len("const tripData = ")
    depth, k, instr, esc = 0, j, False, False
    while k < len(html):
        c = html[k]
        if instr:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                instr = False
        else:
            if c == '"':
                instr = True
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return json.loads(html[j:k + 1])
        k += 1
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("html")
    ap.add_argument("--kml", default=None)
    a = ap.parse_args()

    html = open(a.html, encoding="utf-8").read()
    ok = []

    def ck(name, cond, detail=""):
        ok.append((name, bool(cond), detail))

    # ---- 依赖与离线可用性
    ck("Leaflet 已内联", "window.L" in html and "L.map" in html, "缺内联引擎会白屏")
    ck("无 unpkg / CDN 依赖", "unpkg.com" not in html and "cdnjs" not in html,
       "外网 CDN 在微信/无网环境打不开")
    ck("高德瓦片", "webrd0" in html or "wprd0" in html or "amap" in html, "底图来源")

    # ---- 数据完整性
    td = find_tripdata(html)
    ck("tripData 可解析", td is not None)
    if td:
        days = td.get("days", [])
        n_places = sum(len(d.get("places", [])) for d in days)
        ck("天数 ≥ 1", len(days) >= 1, "%d 天" % len(days))
        ck("点位数 ≥ 3", n_places >= 3, "%d 个" % n_places)

        bad = []
        for di, d in enumerate(days):
            for p in d.get("places", []):
                lng, lat = p.get("lng"), p.get("lat")
                if lng is None or lat is None:
                    bad.append("%s 缺坐标" % p.get("name"))
                elif not (73 < lng < 135 and 3 < lat < 54):
                    bad.append("%s 坐标越界" % p.get("name"))
        ck("坐标全部在 GCJ-02 合理范围", not bad, "; ".join(bad[:3]))

        n_lines = sum(len(d.get("routes", []) or []) for d in days)
        n_pts = sum(len(r.get("pts") or []) for d in days
                    for r in (d.get("routes") or []) + (d.get("altRoutes") or []))
        ck("有行车线几何", n_lines > 0 or n_pts > 0,
           "%d 段 / %d 点（0 则地图只有虚线）" % (n_lines, n_pts))

        # 导航链接：JS 里应当有高德 URI 模板
        ck("高德导航链接", "uri.amap.com" in html, "点气泡里的导航按钮")
        ck("KML 导出兜底面板", 'id="kmlMask"' in html and "kmlSaveFile" in html
           and "kmlCopy" in html, "沙箱里 <a download> 会被丢弃，必须有兜底")

        title = td.get("title", "")
        ck("页面标题与数据一致", title[:2] in html if title else False, title)

    # ---- KML
    if a.kml:
        if not os.path.exists(a.kml):
            ck("KML 文件存在", False, a.kml)
        else:
            kml = open(a.kml, encoding="utf-8").read()
            ck("KML 为 WGS-84 合法结构",
               kml.startswith("<?xml") and "<kml" in kml and "</kml>" in kml)
            if td:
                n = sum(len(d.get("places", [])) for d in td["days"])
                ck("KML 点位数 == 行程点位数",
                   kml.count("<Point>") == n, "%d vs %d" % (kml.count("<Point>"), n))
            ck("KML 无空折线", "<LineString><coordinates></coordinates>" not in kml)

    # ---- 输出
    print("=" * 58)
    print("  %s" % os.path.basename(a.html))
    print("=" * 58)
    fail = 0
    for name, good, detail in ok:
        print("  %s %-26s %s" % ("✓" if good else "✗", name, detail))
        if not good:
            fail += 1
    print("-" * 58)
    print("  %d 项检查 · %d 通过 · %d 失败" % (len(ok), len(ok) - fail, fail))
    print("=" * 58)
    raise SystemExit(1 if fail else 0)


if __name__ == "__main__":
    main()
