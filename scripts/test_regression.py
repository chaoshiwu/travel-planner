#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""回归测试：改了模板/引擎之后，确认已验证的样例没被改坏。

用法：
    python scripts/test_regression.py

对 examples/ 下每个样例跑一遍 build，与 _baseline.json 里的 MD5 比对：
  · 一致   → 模板改动无副作用
  · 不一致 → 打印首个差异位置，确认是有意改的再把新 MD5 写回 baseline
"""
import glob
import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
BASE = json.load(open(os.path.join(HERE, "_baseline.json"), encoding="utf-8"))


def md5(p):
    return hashlib.md5(open(p, "rb").read()).hexdigest()


def first_diff(a, b):
    i = 0
    n = min(len(a), len(b))
    while i < n and a[i] == b[i]:
        i += 1
    return i


def main():
    fails = 0
    update = "--update" in sys.argv
    new_base = dict(BASE)
    for name, exp in BASE.items():
        if not exp:
            continue
        example = os.path.join(SKILL, "examples", name)
        if not os.path.isdir(example):
            print("  − %s 样例已移除，跳过" % name)
            continue
        out = tempfile.mkdtemp(prefix="tripreg_")
        r = subprocess.run([sys.executable, os.path.join(HERE, "build.py"), example, "-o", out],
                           capture_output=True, text=True, encoding="utf-8")
        if r.returncode != 0:
            print("  ✗ %-12s build 失败\n%s" % (name, (r.stdout or "")[-600:]))
            fails += 1
            continue

        ok = True
        for kind, glob_pat in (("html", "*.html"), ("kml", "*.kml")):
            files = glob.glob(os.path.join(out, glob_pat))
            if not files:
                print("  ✗ %-12s 没产出 %s" % (name, kind))
                ok = False
                continue
            got = md5(files[0])
            want = exp.get(kind, {}).get("md5")
            if got != want and update:
                new_base.setdefault(name, {})[kind] = {
                    "md5": got, "bytes": os.path.getsize(files[0])}
                print("  ↻ %-12s %-4s 基线已更新 %s" % (name, kind, got[:12]))
            elif got != want:
                a = open(files[0], "rb").read().decode("utf-8", "ignore")
                print("  ✗ %-12s %s MD5 变了 (%s → %s)"
                      % (name, kind, (want or "?")[:10], got[:10]))
                print("      产物 %d 字节，基线 %s 字节"
                      % (len(a.encode()), exp.get(kind, {}).get("bytes")))
                ok = False
            else:
                print("  ✓ %-12s %-4s MD5 一致 %s" % (name, kind, got[:12]))
        if not ok:
            fails += 1

    if update:
        with open(os.path.join(HERE, "_baseline.json"), "w", encoding="utf-8") as f:
            json.dump(new_base, f, ensure_ascii=False, indent=1)
        print("=" * 56)
        print("  基线已写入 _baseline.json（确认这次变化是有意的）")
        print("=" * 56)
        return

    print("=" * 56)
    print("  %s" % ("全部通过" if not fails else "%d 个样例不一致" % fails))
    print("=" * 56)
    raise SystemExit(1 if fails else 0)


if __name__ == "__main__":
    main()
