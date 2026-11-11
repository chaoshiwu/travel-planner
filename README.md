# travel-planner

> 给一句「XX 玩 3 天」，还你一份**手机上能直接点开用**的路书。

一个把旅游攻略做成**单文件交互网页**的 Agent Skill。填三个 JSON，跑两条命令，得到一份带真实地图、逐点导航、KML 导出、预算与避坑的行程页。零外网依赖，微信里点链接就能开。

```bash
python scripts/build.py  my-trip -o out      # → HTML + KML
python scripts/verify.py "out/xx.html" --kml "out/xx.kml"
```

---

## 它解决的不是"写攻略"，是"攻略没法用"

网上攻略的通病：收藏了几十篇，到了地方还是要把地名一个个敲进地图 App。

这份产物的做法不一样——**每个点位都是一个导航入口**：

| 能力 | 说明 |
|---|---|
| 真实地图 | Leaflet + 高德瓦片，**整份内联进 HTML**，断网也不白屏 |
| 一键导航 | 每个点位的弹窗里三个按钮：高德 / 百度 / 苹果地图，直接唤起 App |
| 分日图层 | 每天一条彩色行车线，可单独开关，图例联动 |
| 真实路网 | 用 OSRM 抓回来的几何（样例 3 天 2157 个点），不是两点连线 |
| KML 导出 | 给奥维 / 两步路 / 高德网页版用；**三出口兜底**，沙箱里点了也不会"没反应" |
| 手机优先 | 单列布局、大点击区，微信内置浏览器实测可用 |

成品样例（乌兰布统 3 日亲子自驾，22 点位）：

```
examples/wulanbutong/   →  3 天 + 1 备选日 · 约 676 km · 全内联 255 KB 单文件
```

---

## 快速开始

### 依赖

只有一个：**Python 3.9+**，标准库即可，**不用 pip install**。

### 三步

```bash
# 1. 抄一份最小样例（2 天 4 个点）
cp -r examples/mini  my-trip

# 2. 改成你的目的地：编辑 my-trip/trip.json 和 sections.json
#    trip.json     —— 每天去哪、几点到、门票多少、亮点和提醒
#    sections.json —— 天气 / 交通 / 住宿 / 预算 / 避坑 / 出行清单

# 3. 抓真实路网 + 生成
python scripts/fetch_route.py my-trip      # 可选；不抓就是虚线连点位
python scripts/build.py      my-trip -o out
```

产物在 `out/` 下：一个自包含的 `.html` 和一个 `.kml`。

### 交付前自检

```bash
python scripts/verify.py "out/xxx.html" --kml "out/xxx.kml"
```

14 项检查（Leaflet 是否内联、有无 CDN 残留、KML 兜底面板、点位数、坐标是否落在国内、有没有空的折线……）。全绿再发。

---

## 数据格式

三个 JSON，职责分得很清：

| 文件 | 谁写 | 内容 |
|---|---|---|
| `trip.json` | **人写** | 天 / 点位 / 时间 / 门票 / 亮点 / 提醒 / 路线途经点 |
| `sections.json` | **人写** | 天气 / 交通 / 住宿 / 预算 / 避坑 / 清单 等区块文案 |
| `routes.json` | **脚本生成** | 路网几何，别手写 |

**坐标一律 GCJ-02**（高德 / 腾讯的坐标系）。`places` 里写 `"lng"/"lat"`，`routes.json` 里是 `[lat, lng]`。
混用 WGS-84 会让所有点整体偏移 300~600 米，而且**没有脚本能替你查出来**。

字段逐个说明见 [`references/trip-schema.md`](references/trip-schema.md)。

---

## 目录结构

```
travel-planner/
├── SKILL.md                    给 Agent 的流程说明（四阶段 + 硬规则）
├── assets/                     页面引擎，改目的地不用动这里
│   ├── template.html             骨架，用 {{HERO}} {{MAP}} 这类占位符
│   ├── app.js                    渲染引擎：地图 / 导航 / KML / 兜底
│   ├── page.css                  已验证的样式
│   └── leaflet.js / leaflet.css  内联用，零外网依赖
├── scripts/
│   ├── build.py                  trip.json → HTML + KML
│   ├── fetch_route.py            route.via → OSRM 真实路网 → routes.json
│   ├── verify.py                 交付前 14 项自检
│   └── test_regression.py        改模板后跑，确认已验证样例没被改坏
├── references/
│   ├── trip-schema.md            三个 JSON 的完整字段 + 各区块 HTML 骨架
│   └── pitfalls.md               20 条踩过的坑
└── examples/
    ├── wulanbutong/              完整范例：3 天 + 1 备选日、22 点位
    └── mini/                     最小范例：2 天 4 点
```

### 改了模板怎么保证没改坏

```bash
python scripts/test_regression.py            # 两个样例重跑，比字节 MD5
python scripts/test_regression.py --update   # 确认变化是有意的，再更新基线
```

`build.py` 是幂等的：同一份数据跑两次，产物逐字节一致。这条很重要——否则你无法判断「这次 diff 是改对了，还是生成器自己在抖」。

现有的乌兰布统样例，重跑产物与人工校验过的成品 **MD5 完全相同**（`c711e980…` / `f4d1da50…`）。

---

## 六条硬规则

违反任意一条，用户就拿不到能用的页面。

1. **Leaflet 必须内联**，不许改回 CDN。CDN 在微信 / 离线环境白屏。
2. **KML 导出必须保留三出口面板**（保存为文件 / 复制全部内容 / 关闭）。微信和 IDE 预览面板会**静默丢弃** `<a download>`——点下去不下载、不报错、没提示。
3. **坐标统一 GCJ-02**。
4. **老版本不许覆盖**。用户说"留着"就是真会对比。
5. **改完读回复核**。同一文件的多处编辑不要并行提交，会静默丢失。
6. **生成器保持幂等**。

还有一条不在代码里、但最省事：**别发本地 HTML 文件，发在线链接**。
微信里 `.html` 是附件，没有"用浏览器打开"这个入口；链接点开就是网页。

---

## 部署到手机上

三种方式，按场景选：

| 场景 | 做法 |
|---|---|
| 电脑上看 / 自己要存档 | 直接用 `out/xxx.html` |
| **手机、微信里打开**（最常见） | 丢到任意静态托管（GitHub Pages / Vercel / 对象存储），**发链接** |
| 导进奥维 / 两步路 / 高德网页版 | 给 `.kml` |

GitHub Pages 的最小做法：把产物重命名成 `index.html` 推到仓库，仓库设置里开 Pages。

---

## 已知边界

诚实地说清楚，免得你以为它什么都能干：

- **内容得自己核**。门票价、开放时间、是否要预约，脚本不查也不猜。页面里标「截至 YYYY-MM」。
- **坐标得自己取**。从高德 / 腾讯地图分享链接里抄，精度 5~6 位。偏远点位 OSRM 会报「路网未连通」，那段退化成虚线，不影响导航按钮。
- **不排飞机高铁**。默认自驾场景；其它交通方式就是把点位换成车站，但里程几何要自己给。
- **手机高德 App 不能导入 KML**。这是高德的限制，不是这里的 bug。

---

## 关于示例数据

`examples/wulanbutong/` 是一次真实行程的完整快照，含具体日期和住宿点名称，仅作技术演示。
换目的地时复制 `examples/mini/` 起手，别在完整样例上改。

---

## License

[MIT](LICENSE)
