# 中旅旅行小程序 搜索→复制链接 自动化 Skill

> 通过 WMPFDebugger CDP 通道(ws://127.0.0.1:62000)驱动「中旅旅行」小程序(wx56a6e0e5d7b06a52,后端 pro-api.ourtour.com)。
> 适用:搜索商品 → 进详情 → 复制小程序链接 → 退回搜索页 的完整链路。

## 一、前置条件

- WMPFDebugger 后端运行: `cd C:\Users\65164\WMPFDebugger; npx ts-node src/index.ts`
- 小程序已连接(日志出现 `[miniapp] miniapp client connected`)
- 脚本目录: `C:\Users\65164\playwright-tools\`(Node ≥ 22,全局 WebSocket,无依赖)

## 二、核心逻辑(精简 5 步链路)

```
设搜索框 → 点搜索 → 点第一个结果(验证标题) → 直接 dispatch 胶囊复制链接(读剪贴板) → 退出×2 回搜索页
```

| 步骤 | 动作 | 关键点 |
|---|---|---|
| 1 设搜索框 | 改 iframe[1] 真实 INPUT 的 value | **只改原生 `<input>`**,wx-input 是包装无 value |
| 2 点搜索 | 坐标点击 `.commonSearch__btn`(370,84) | 用 `Input.dispatchMouseEvent`,别用 touch |
| 3 点结果+验证 | 坐标点击第一个 `.index-module__productCard`(中心),读取 `.cardTitle` 确认 | 标题读到 = 结果在;多方式轮换更稳 |
| 4 复制链接 | **直接** dispatch 胶囊菜单复制图标 | 点胶囊(328,43)开菜单 → 找 `M23.5425` 图标 dispatch → 读剪贴板 |
| 5 退出×2 | **复制完成后必须点两次返回** | 可见时坐标 (22,42),不可见 dispatch;两次都点完再验证回到搜索页 |

**关键洞察**:点完第一个结果后**不用等/不用验证详情页跳转**,直接 dispatch 胶囊复制链接——**拿到剪贴板链接即证明已进详情页**。这避免连接抖动期间的等待和误判。

## 三、关键代码(精简可直接用)

### Step1 设置搜索框
```js
const expr = `(() => {
  const d = document.querySelectorAll('iframe')[1].contentDocument;
  const el = [...d.querySelectorAll('input')].find(e => e.getBoundingClientRect().width > 0);
  if (!el) return { found: false };
  Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(el, '3100195031');
  el.dispatchEvent(new (d.defaultView.Event)('input', { bubbles: true }));
  return { found: true, set: el.value };
})()`;
// send('Runtime.evaluate', { expression: expr, returnByValue: true })
```

### Step2 点击搜索(坐标点击模板)
```js
// send('Runtime.evaluate', 定位 .commonSearch__btn 拿 vx,vy)
await send('Input.dispatchMouseEvent', { type: 'mouseMoved', x, y });
await send('Input.dispatchMouseEvent', { type: 'mousePressed', x, y, button: 'left', clickCount: 1 });
await wait(120);
await send('Input.dispatchMouseEvent', { type: 'mouseReleased', x, y, button: 'left', clickCount: 1 });
```

### Step4 复制链接(推荐:点卡片+复制 组合脚本)
```js
// 完整组合脚本: 点第一个结果 -> dispatch 胶囊复制链接 (已验证 3100202887)
const ws = new WebSocket('ws://127.0.0.1:62000');
let msgId = 0; const pending = new Map();
function send(method, params = {}) {
  return new Promise((res, rej) => {
    const id = ++msgId; pending.set(id, { res, rej });
    ws.send(JSON.stringify({ id, method, params }));
  });
}
const wait = (ms) => new Promise(r => setTimeout(r, ms));
// ... ws.onopen:
// 1) 定位 .index-module__productCard 中心 (vx,vy), mouse 点击 2 次
//    await send('Input.dispatchMouseEvent', {type:'mousePressed', x, y, button:'left', clickCount:1}); await wait(150);
//    await send('Input.dispatchMouseEvent', {type:'mouseReleased', x, y, button:'left', clickCount:1});
// 2) 验证标题: d.querySelector('.index-module__cardTitle___dKinZ').innerText
// 3) 点胶囊开菜单: 坐标 (328, 43)
// 4) 找复制图标 M23.5425 并 dispatch 点击:
const disp = `(() => {
  const items = document.querySelectorAll('.menu_item');
  for (const el of items) {
    const img = el.querySelector('img');
    if (img && img.src.includes('M23.5425')) {
      const o = { bubbles: true, cancelable: true };
      el.dispatchEvent(new MouseEvent('click', o));
      el.dispatchEvent(new Event('touchstart', o));
      el.dispatchEvent(new Event('touchend', o));
      return { dispatched: true };
    }
  }
  return { dispatched: false };
})()`;
// 5) 读剪贴板(PowerShell):
//    Add-Type -AssemblyName System.Windows.Forms
//    [System.Windows.Forms.Clipboard]::GetText()
```

## 四、避坑指南(每条都是血泪教训)

1. **连接很脆**:每次脚本开新 CDP 连接,小程序可能断线重连 → 命令超时。对策:少开脚本、一个脚本做完一整步;超时就等 2-3 秒再试。
2. **`Input.dispatchTouchEvent` 会卡死**:小程序不响应 touch 命令,卡住不返回。**只用 `Input.dispatchMouseEvent`** 或 DOM dispatch。
3. **wx-input 没 value**:搜索框外层是 `<wx-input class="input h5-input">`,设值没用;**只对原生 `<input>` 设 value**。
4. **菜单纯图标无文字**:胶囊菜单项 `innerText` 全空,`innerText` 找"复制链接"必失败。**用图标路径 `M23.5425`(双箭头)识别**,位于第 2 行第 4 个,屏幕 (296,302)。
5. **点胶囊会弹出 tips 弹窗**:详情页首次点胶囊会先弹 `tips-dialog`("我知道了"按钮 ~207,263),要先点掉再操作菜单。
6. **坐标点击偶尔不触发跳转**:结果卡片坐标点击可能"发了但没跳"。对策:同一坐标点 2 次(mouse pressed/released ×2,间隔 1.2s);**不必等跳转确认**,直接进 Step4 dispatch 复制链接。
7. **详情页判定易误判**:搜索结果页含 ¥/价格,`/¥|价格|预订/` 正则会把搜索结果当详情。**判定详情要识别"旅游内容"(标题/景点/酒店)或 frame 内容变化**。
   - **实测修正**:frame2 一直显示结果页是**正常**的——小程序详情页是独立页面栈,结果页 iframe 缓存不销毁。**不要**以"frame2 变了"来判定进详情。正确做法:**点卡片(点 2 次)→ 直接 dispatch 胶囊复制链接 → 读剪贴板,拿到链接即证明已进详情页**。
8. **复制链接后直接读系统剪贴板**:链接写入 Windows 剪贴板,`[System.Windows.Forms.Clipboard]::GetText()` 最可靠,零干扰。
9. **返回按钮 `.back`(复制完成后必须点两次)**:复制链接后必须**连点两次返回**才回到搜索页(一次只退回一层:详情→结果页→搜索页)。可见时坐标 (22,42) 点击;不可见(rect 全 0)时对祖先链 dispatch 事件。两次都点完再用 iframe1 是否有可见 input 验证回到搜索页。
10. **搜索历史自动更新**:每次搜索会写进 iframe[1] 的搜索历史,可据此确认搜索确实执行了。

## 五、产物

- 每次搜索: `pro-api.ourtour.com/openapi/search/product`(明文 JSON,keyword 字段)
- 链接格式: `#小程序://中旅旅行/<hash>`
