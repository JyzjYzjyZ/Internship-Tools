---
name: wmpf-debugger
description: >
  WMPFDebugger 小程序调试与禁摩点位抓取技能。用于通过 WMPFDebugger 的 CDP 通道
  (ws://127.0.0.1:62000) 调试微信小程序、抓取网络请求、采集地图点位坐标。
  核心流程: 抓包 -> 换算经纬度 -> 落盘。适用于已授权的微信小程序分析场景。
---

# WMPFDebugger 小程序调试技能

## 前置条件

- **WMPFDebugger 后端运行中**(端口 9421 + 62000):
  ```
  cd C:\Users\65164\WMPFDebugger
  npx ts-node src/index.ts
  ```
- **小程序已连上调试器**(后端日志出现 `[miniapp] miniapp client connected`)
- **Chrome DevTools 已打开**: `devtools://devtools/bundled/inspector.html?ws=127.0.0.1:62000`
- 需要 Node.js ≥ 22(脚本用全局 WebSocket,无第三方依赖)

## 关键经验(每次都要遵守)

1. **失焦会断线**: 小程序连接断开/读不到 DOM 时, 先检查 9421 端口连接数
   (`Get-NetTCPConnection -LocalPort 9421 -State Established`)。失焦导致的断线不是 bug。
2. **只读旁观**: 抓包脚本只监听 CDP, 不发起请求, 不干预小程序。
3. **手动抓包更可靠**: 小程序连接不稳时, 守护进程可能读不到 DOM,
   "你叫我 -> 我抓一次存一次" 的方式最稳。
4. **CDP 读不到响应体**: `Network.getResponseBody` 不可用, 价格等数据从 DOM 文本读。
5. **逻辑层被 anti-frida 保护**: 不要试图 Frida 注入逻辑层进程(会被原生拦截)。

## 核心工作流: 一次抓包

```bash
# 在 playwright-tools 目录(脚本所在处)
node one-shot-capture.mjs
```

这个脚本一次完成:**抓取当前地图所有点位标记 -> 屏幕坐标换算经纬度 -> 落盘**。

**落盘位置**: `桌面\抓包\点位采集\点位-<时间>.json` + `-经纬度.json` + `-经纬度.csv`

**输出**:
```
点位: <N> | 中心: <lat>, <lng> | scale <scale>
样例: (lat, lng) 点位名称
```

## 脚本清单

| 脚本 | 用途 |
|---|---|
| `one-shot-capture.mjs` | **主流程**: 抓包+换算+落盘(最常用) |
| `coord-daemon.mjs` | 守护进程: 监听地图移动自动存坐标 |
| `map-daemon.mjs` | 守护进程: 监听业务请求写 raw.jsonl |
| `split-batch.mjs` | 把 raw.jsonl 新请求切成分批 md+json |
| `organize-batch.mjs` | 组织批次: 去重+总结 |
| `dedupe-summary.py` | 汇总去重: 合并所有点位文件, 统计唯一点位 |
| `final-convert.py` | 屏幕坐标 -> 经纬度(WebMercator + 锚点校准) |

## 换算原理(重要)

- 坐标是**屏幕像素**(DOM overlay 的 `translate3d(x, y)`)
- 换算用 **Web Mercator + 锚点校准**(闵塔公路 31.03, 121.17)
- 坐标系: **GCJ-02**(腾讯地图), 非 WGS84
- 精度: 约 0.1 度误差(锚点近似), 点位相对位置正确
- 若需更高精度: 用 polygons 真实经纬度做多锚点拟合

## 数据源(怎么拿坐标)

- **禁摩多边形**(静态全局): `wx-map` 元素的 `polygons` 属性(113 个多边形, 全国固定)
- **点位标记**(随地图变化): 地图容器 `.wx-gl-map-container` 内所有 `translate3d` 元素
  - 每个有 `innerText`(点位名称) + `translate3d(x, y)`(屏幕坐标)
  - 这才是 `getNewList` 返回的坐标点

## 常见排查

| 现象 | 原因 | 处理 |
|---|---|---|
| 守护进程 `no wx-map found` | 地图重绘间隙 or 连接断 | 手动跑一次抓包 / 重进小程序 |
| CDP 查询超时 | 小程序断开 | 重进小程序, 保持 DevTools 前台 |
| 抓到的点位全一样 | 地图没移动 | 移动地图再抓 |
| 换算出坐标在海里 | 锚点/原点假设错 | 用中心点=视口中心假设 + 锚点校准 |

## 批量抓取工作流: PDF 列表 -> 复制小程序链接(本次经验)

场景: 小程序「所有PDF」列表 66 项, 逐个进入预览页, 胶囊菜单复制 `#小程序://...` 分享链接, 返回列表, 结果落盘 JSON。

### 铁律(血泪经验, 违反会闪退/丢数据)

1. **绝不合并成大脚本**: 一个 Node 进程内循环多个文件的连续操作(点击->复制->返回)必闪退。
   正确做法: **每个文件 = 每次 `node` 独立进程, 独立 CDP 连接**, 由 PowerShell 串行驱动。
2. **胶囊菜单只能用 DOM dispatch**: `Input.dispatchMouseEvent` 点胶囊(387,43)会卡死/闪退。
   复制图标 = 菜单项内 `img.src` 含 `M23.5425`, dispatch 三连(click+touchstart+touchend)。
3. **返回按钮只 dispatch 一次 click**: 三连会 pop 两层直接退出标签页。
4. **滚动 iframe 内容**: BODY/HTML 直接赋值 `scrollTop` 无效(now 仍为 0)!
   必须 `d.scrollingElement.scrollTop = N` 或 `d.defaultView.scrollTo(0, N)`。
5. **CDP 表达式内禁 `\n`**: 模板字符串里 `t.split('\n')` 的 `\n` 变真实换行导致 SyntaxError,
   用 `String.fromCharCode(10)`。
6. **PowerShell JSON 落盘坑**:
   - `Get-Content -Raw` 读 UTF8 带 BOM 文件, `ConvertFrom-Json` 静默失败 -> 数组变空 ->
     `+=` 从头覆盖写盘 **丢光已有数据**。必须用 `[System.IO.File]::ReadAllText($out)` 读。
   - 空数组 `+= $obj` 会嵌套成 `{"value":[...]}`, 写盘前校验结构, 去重按 index 排序。
7. **断点续跑**: 每完成一项立即写盘(全量数组), 重跑时按 index 跳过已完成项。

### 页面结构

- 主文档 = nav 栏 + 胶囊 + 菜单 + tips-dialog(在 `.menu_item` / `.tips-dialog__button` DOM)
- `iframe[0]` = 首页 tab(含「所有PDF」tab 文本, 可按 innerText 定位)
- `iframe[1]` = 列表页(66 个 `wx-fileitem`, 标题 = innerText 第一行)
- `iframe[2]` = 预览页(`wx-web-view` src 为 preview-static.clewm.net)

### 脚本(playwright-tools 目录)

| 脚本 | 用途 |
|---|---|
| `click-item.mjs <idx>` | 恢复列表 -> 滚动使第 idx 项到视口中部 -> 双击进入预览 |
| `copy-link-ref.mjs` | 点 tips(若在) -> 胶囊(若菜单未开) -> M23.5425 三连 -> 等 1s |
| `back-once.mjs` | 返回一次(单事件 dispatch) |
| `run-all.ps1` | 串行驱动循环: 每项 = click-item + copy-link-ref + 读剪贴板 + back-once, 逐项写盘 |
| `run-one.ps1` | 补跑单个 index |

- 等待时长经验: 点击进预览后等 **2500ms**(原 5000 可缩短), 复制后 1000ms, 每项约 10s。
- 剪贴板读取(PowerShell): `Add-Type -AssemblyName System.Windows.Forms; [Console]::OutputEncoding=[Text.Encoding]::UTF8; [Windows.Forms.Clipboard]::GetText()`。
- 链接每次复制都会重新生成(同一文件每次不同), 历史链接仍有效。

## 目录结构

```
桌面\抓包\
├── raw.jsonl              # 原始请求记录
├── dom.jsonl              # DOM 快照
├── 批次1-*.md/json        # 分批存档
├── 去重汇总.json          # 去重后唯一点位
├── 点位采集\              # 每次抓包落盘
│   ├── 点位-<时间>.json
│   ├── 点位-<时间>-经纬度.json
│   └── 点位-<时间>-经纬度.csv
├── scripts\               # 核心脚本副本
└── 分析\                  # 分析文档
```
