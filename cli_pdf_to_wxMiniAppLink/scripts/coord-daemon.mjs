// coord-daemon.mjs - 全新坐标抓取守护
// 监听 getNewList(地图移动) -> 每次移动后提取 wx-map polygons -> 单独存一个文件
import fs from 'node:fs';

const DIR = 'C:\\Users\\65164\\Desktop\\抓包\\坐标采集';
fs.mkdirSync(DIR, { recursive: true });

const ws = new WebSocket('ws://127.0.0.1:62000');
let msgId = 0;
const pending = new Map();
let seq = 0;
let lastReqTime = 0;

function send(method, params = {}) {
  return new Promise((resolve, reject) => {
    const id = ++msgId;
    pending.set(id, { resolve, reject, method });
    ws.send(JSON.stringify({ id, method, params }));
  });
}

async function readPolygons() {
  // 重试最多 5 次, 地图重绘间隙可能读不到 wx-map
  for (let attempt = 1; attempt <= 5; attempt++) {
    try {
      const res = await send('Runtime.evaluate', {
        expression: `(() => {
          const frames = document.querySelectorAll('iframe');
          for (const f of frames) {
            try {
              const d = f.contentDocument;
              if (!d) continue;
              const maps = d.querySelectorAll('wx-map');
              if (maps.length) {
                const map = maps[0];
                const out = {
                  latitude: map.getAttribute('latitude'),
                  longitude: map.getAttribute('longitude'),
                  scale: map.getAttribute('scale'),
                };
                const pa = map.getAttribute('polygons');
                if (pa) {
                  try {
                    const p = JSON.parse(pa);
                    out.polygonCount = p.length;
                    out.totalPoints = p.reduce((s, x) => s + (x.points?.length || 0), 0);
                    out.polygons = p;
                  } catch(e) { out.polygonsError = String(e).slice(0, 50); }
                }
                // 禁摩点位标记(名称 + 屏幕坐标)
                const container = map.querySelector('.wx-gl-map-container');
                if (container) {
                  const markers = [];
                  const all = container.querySelectorAll('*');
                  for (const el of all) {
                    const style = el.getAttribute('style') || '';
                    const t = style.match(/transform:\s*translate3d\(([-\d.]+)px,\s*([-\d.]+)px/);
                    const text = (el.innerText || '').trim();
                    const img = el.querySelector('img');
                    if (t && (text || img)) {
                      markers.push({
                        x: Math.round(parseFloat(t[1]) * 10) / 10,
                        y: Math.round(parseFloat(t[2]) * 10) / 10,
                        text: text.length < 100 ? text : '',
                        img: img ? img.src.slice(0, 50) : '',
                      });
                    }
                  }
                  out.markers = markers;
                }
                return out;
              }
            } catch(e) {}
          }
          return null;
        })()`,
        returnByValue: true,
      });
      const data = res.result && res.result.value;
      if (data && data.polygons && data.polygonCount) return { result: { value: data } };
    } catch(e) {
      console.log('[coord] read attempt', attempt, 'error:', e.message.slice(0, 60));
    }
    await new Promise(r => setTimeout(r, 700));
  }
  return { result: { value: null } };
}

async function saveCapture(reqUrl) {
  try {
    // 等地图重绘完成
    await new Promise(r => setTimeout(r, 1200));
    const res = await readPolygons();
    const data = res.result.value;
    if (!data) { console.log('[coord] no wx-map found'); return; }
    if (!data.polygons || !data.polygonCount) { console.log('[coord] no polygons yet'); return; }

    seq++;
    const q = new URL(reqUrl).searchParams;
    const file = `${DIR}\\坐标-${String(seq).padStart(3, '0')}.json`;
    const dump = {
      seq,
      captured_at: new Date().toISOString(),
      request_center: { lng: q.get('lng'), lat: q.get('lat') },
      request_range: { oneLng: q.get('oneLng'), oneLat: q.get('oneLat'), twoLng: q.get('twoLng'), twoLat: q.get('twoLat') },
      map_center: { lat: data.latitude, lng: data.longitude },
      scale: data.scale,
      polygonCount: data.polygonCount,
      totalPoints: data.totalPoints,
      markerCount: data.markers ? data.markers.length : 0,
      polygons: data.polygons,
      markers: data.markers || [],
    };
    fs.writeFileSync(file, JSON.stringify(dump, null, 2), 'utf-8');
    console.log(`[coord] 坐标-${String(seq).padStart(3,'0')}.json saved: ${data.polygonCount}个多边形, ${data.totalPoints}点, ${dump.markerCount}个点位标记`);
  } catch(e) {
    console.log('[coord] save error:', e.message.slice(0, 80));
  }
}

ws.onopen = async () => {
  console.log('[coord-daemon] connected to CDP');
  try { await send('Network.enable'); console.log('[coord-daemon] Network.enable OK'); }
  catch(e) { console.log('[coord-daemon] enable error:', e.message); }
};

ws.onmessage = (evt) => {
  let msg;
  try { msg = JSON.parse(evt.data.toString()); }
  catch(e) { return; }  // 忽略非 JSON 帧(二进制/心跳)
  if (msg.id && pending.has(msg.id)) {
    const { resolve, reject } = pending.get(msg.id);
    pending.delete(msg.id);
    if (msg.error) reject(new Error(JSON.stringify(msg.error)));
    else resolve(msg.result);
    return;
  }
  // 地图移动触发 getNewList
  if (msg.method === 'Network.requestWillBeSent' && /mtmapp\.motomao\.com.*getNewList/.test(msg.params.request.url)) {
    const now = Date.now();
    // 防抖: 同一时刻的多余请求只存一次
    if (now - lastReqTime > 1500) {
      console.log(`[coord-daemon] getNewList -> ${new Date().toLocaleTimeString()}`);
      lastReqTime = now;
      saveCapture(msg.params.request.url);
    }
  }
};

ws.onerror = (e) => { console.log('[coord-daemon] ws error:', e.message); process.exit(1); };
setInterval(() => {}, 10000);
console.log('[coord-daemon] listening for map moves...');
