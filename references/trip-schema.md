# 数据格式（trip.json / sections.json / routes.json）

三个文件放同一目录，`scripts/build.py <目录>` 即可出成品。

```
my-trip/
├── trip.json       行程骨架：天、点位、提醒     ← 人写
├── sections.json   文案区块：天气、交通、预算…  ← 人写
└── routes.json     路网几何（可选）            ← 脚本生成
```

---

## 一、坐标约定（最容易出错，先看这条）

| 用途 | 坐标系 |
|---|---|
| 高德/腾讯地图上抄来的点位 | **GCJ-02** |
| 页面地图、高德导航、百度导航 | GCJ-02（页面内部自动转 BD-09） |
| KML 导出 | WGS-84（页面自动转） |
| OSRM 请求与返回 | WGS-84（`fetch_route.py` 自动来回转） |

**trip.json 里所有 lng/lat 一律写 GCJ-02**，单位是「度」，小数 5~6 位。
拿 GPS 原始坐标（WGS-84）直接填，在地图上会偏 **300~600 米**——够把车导到隔壁沟里。

`routes.json` 里的点顺序是 **`[lat, lng]`**（纬度在前），和 Leaflet 一致；
`places` 里用的是 `"lng"` / `"lat"` 两个具名字段，别混。

---

## 二、trip.json

```jsonc
{
  "title": "天津亲子 2 日",              // 内部名，也用于文件名兜底
  "pageTitle": "天津亲子 2 日 · 手机路书", // <title> 与文件名
  "kmlName": "tianjin_2d",               // 页面内 KML 下载名（英文更稳）
  "kmlFile": "天津亲子2日.kml",            // 落盘 KML 文件名
  "legendTail": "备选 / 备选点",           // 图例最后一项；不需要就删掉
  "overview": ["① 天津站", "② 古文化街"], // 路线总览那一行
  "mapTip": "…",                         // 可选，覆盖地图下方说明
  "days": [ /* 见下 */ ]
}
```

### days[]（一天一项，按顺序渲染）

| 字段 | 必填 | 说明 |
|---|---|---|
| `name` | ✓ | 例 `Day 1 · 去程：进城早餐 → 桦木沟 → 蛤蟆坝日落`。**图例文字自动从这里取**（`Day 1 去程`） |
| `date` | | 例 `9 月 28 日 周一` |
| `color` | ✓ | 该天线路与点位颜色，如 `#C99A2E`；每天换一个 |
| `km` | | 例 `约 292 km · 纯驾驶 4.2 h`；`{{TOTAL_KM}}` 从这里累加 |
| `highlights` | | 字符串数组，右栏「本日亮点」 |
| `warns` | | 字符串数组，右栏「重要提醒」 |
| `places` | ✓ | 当天的点位，见下 |
| `routes` | | 行车线，见下 |
| `altRoutes` | | 备选线（灰色系，`dash` 可为 `"6 6"`） |
| `noLine` | | `true` = 这天不画连线（备选日、纯清单日） |

### places[]（点位）

```jsonc
{
  "name": "休息 · 灯笼河草原",
  "time": "10:05–10:25",
  "ticket": "免费 · 停 20 min",     // 显示在时间轴第二行，KML 描述也用它
  "tags": ["免费", "拍照圣地"],      // 可用：推荐 / 免费 / 需预约 / 拍照圣地 / 亲子友好
  "desc": "……",                    // 点开气泡看到的正文
  "lng": 117.95, "lat": 42.63
}
```
`k` 字段可选（仅旧数据用），新数据不用写。

### routes[]（行车线）

```jsonc
{
  "id": "d1_1",                    // 与 routes.json 对应；fetch_route.py 会自动写
  "name": "D1 去程",
  "color": "#C99A2E",
  "dash": null,
  "via": [["六分地村", 119.4685, 42.4756], ["桦木沟", 117.3822, 42.6043]]
}
```
- 有 `via` → 跑 `fetch_route.py` 抓真实几何，写进 `routes.json[id]`
- 既没 `pts` 也没 `routes.json` 条目 → 页面退回**虚线连点位**（能用，但看起来像没做功课）
- 直接写 `"pts": [[lat,lng], …]` 也可以，跳过抓取

---

## 三、sections.json

每个 key 是一段 **HTML 字符串**，直接插进页面。常用 key：

| key | 位置 | 建议结构 |
|---|---|---|
| `hero` | 页首大标题区 | `<div class="hero"><h1>…</h1><p>…</p><div class="meta">…</div><div class="stats"><div class="stat"><b>3 天 2 晚</b><span>…</span></div>…</div></div>` |
| `weather` | 天气与穿搭 | `<h2 class="sec">天气与穿搭</h2><div class="wx"><div class="wx-row"><div class="wx-day"><b>9/28 周一</b><span>晴</span><div class="t">0 ~ 18℃</div></div></div><ul class="tips"><li>…</li></ul></div>` |
| `mapTip` | 地图下方小字 | 纯文本 + `<br>`；可用 `{{KML_FILE}}` |
| `overview` | 路线总览 | 必须含 `<div class="route-line" id="routeLine"></div>`，后面随手加里程表 |
| `reserve` | 预约与行前准备 | `<h2 class="sec">…</h2><div class="cols"><div class="col-card"><h3>🎫 门票</h3><ul><li>…</li></ul></div></div>` |
| `advice` | 实用建议（住宿/美食） | 同上，`cols` 两~三列 |
| `budget` | 预算 | `<div class="col-card big"><table><tr><th>类别</th><th>金额</th></tr>…</table></div>` |
| `pitfalls` | 避坑与应急 | `<div class="cols2">` 两列 |
| `checklist` | 出发前最后检查 | `<div class="cols2">` 清单 + 携带物 |
| `tree` | 行程知识图谱 | `<div class="tree">` + 纯文本树（`├─` `└─`），保留换行 |
| `footer` | 页脚 | `<footer>…</footer>`，含免责声明 |

**可用变量**（build 时替换）：`{{TITLE}}` `{{KML_FILE}}` `{{N_PLACES}}` `{{N_DAYS}}` `{{TOTAL_KM}}`

`daysBox`（每日行程）、`routeLine`（总览线）、`map`（地图）由引擎自动渲染，
**sections 里不要自己写这三个容器**（`overview` 里那个 `routeLine` 是例外，必须留）。

---

## 四、routes.json

```json
{"d1_1": [[42.47546, 119.47706], [42.47374, 119.47335]]}
```
由 `fetch_route.py` 生成，也可手写。键 = `routes[].id`，值 = `[lat, lng]` 数组（GCJ-02）。

---

## 五、最小可运行例子

见 `examples/mini/`（2 天 4 个点位，含一条真实路网），跑：
```bash
python scripts/build.py examples/_smoke -o out
```
完整范例见 `examples/wulanbutong/`（3 天 + 1 备选日、22 点位、2157 个路网点）。
