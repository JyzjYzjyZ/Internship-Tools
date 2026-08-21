// map-daemon.mjs - 持续捕获地图小程序业务请求, 实时写入 桌面/抓包/raw.jsonl
// 运行方式: node map-daemon.mjs (后台常驻)
import fs from 'node:fs';

const DIR = 'C:\\Users\\65164\\Desktop\\抓包';
fs.mkdirSync(DIR, { recursive: true });
const RAW = DIR + '\\raw.jsonl';
const DOM = DIR + '\\dom.jsonl';

const ws = new WebSocket('ws://127.0.0.1:62000');
let msgId = 0;
const pending = new Map();

function send(method, params = {}) {
  return new Promise((resolve, reject) => {
    const id = ++msgId;
    pending.set(id, { resolve, reject, method });
    ws.send(JSON.stringify({ id, method, params }));
  });
}

// 过滤: 静态资源 + 微信/地图/广告埋点
function shouldSkip(url) {
  if (/\.(png|jpg|jpeg|webp|gif|svg|css|woff|ttf|ico)(\?|$)/i.test(url)) return true;
  if (/pr\.map\.qq\.com/.test(url)) return true;               // 腾讯地图埋点
  if (/report-online\.sh\.wxgateway\.com/.test(url)) return true; // 微信 SdkReport
  if (/sh\.servicewechat\.com/.test(url)) return true;
  if (/cube\.weixinbridge\.com/.test(url)) return true;
  if (/wdaa\.shuzilm\.cn/.test(url)) return true;              // 广告
  return false;
}

function appendTo(file, obj) {
  try { fs.appendFileSync(file, JSON.stringify(obj) + '\n', 'utf-8'); } catch(e) { console.log('[daemon] append err', e.message); }
}

ws.onopen = async () => {
  console.log('[daemon] connected to CDP');
  try { await send('Network.enable'); console.log('[daemon] Network.enable OK'); }
  catch(e) { console.log('[daemon] enable error:', e.message); }
};

ws.onmessage = (evt) => {
  const msg = JSON.parse(evt.data.toString());
  if (msg.id && pending.has(msg.id)) {
    const { resolve, reject } = pending.get(msg.id);
    pending.delete(msg.id);
    if (msg.error) reject(new Error(JSON.stringify(msg.error)));
    else resolve(msg.result);
    return;
  }
  if (msg.method === 'Network.requestWillBeSent') {
    const req = msg.params.request;
    if (shouldSkip(req.url)) return;
    const rec = { ts: Date.now(), method: req.method, url: req.url, headers: req.headers || {}, postData: req.postData ?? null };
    appendTo(RAW, rec);
    console.log(`[daemon] ${new Date().toLocaleTimeString()} ${req.method} ${req.url.slice(0, 110)}`);

    // 业务请求(mtmapp) 时延迟抓 DOM
    if (/mtmapp\.motomao\.com/.test(req.url)) {
      setTimeout(async () => {
        try {
          const r = await send('Runtime.evaluate', {
            expression: `(() => { const fs=document.querySelectorAll('iframe'); const out=[]; for (const f of fs){ try { const d=f.contentDocument; if (d&&d.body) out.push((d.body.innerText||'').slice(0,3000)); } catch(e){} } return out.join('\\n---FRAME---\\n'); })()`,
            returnByValue: true
          });
          const text = r.result && r.result.value;
          if (text) { appendTo(DOM, { ts: Date.now(), url: req.url, text }); console.log('[daemon] dom snapshot captured'); }
        } catch(e) { console.log('[daemon] dom err', e.message.slice(0,80)); }
      }, 600);
    }
  }
};

ws.onerror = (e) => { console.log('[daemon] ws error:', e.message); process.exit(1); };
// 心跳保持, 防止意外退出
setInterval(() => { console.log('[daemon] alive'); }, 60000);
console.log('[daemon] listening for business requests...');
