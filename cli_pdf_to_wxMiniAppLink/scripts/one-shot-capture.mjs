// one-shot-capture.mjs - 一次抓包 + 换算 + 落盘
// 用法: node one-shot-capture.mjs
import fs from 'node:fs';

const DIR = "C:\\Users\\65164\\Desktop\\抓包\\点位采集";
fs.mkdirSync(DIR, { recursive: true });

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
async function wait(ms) { return new Promise(r => setTimeout(r, ms)); }

const EXPR = `(() => {
  const frames = document.querySelectorAll('iframe');
  for (const f of frames) {
    try {
      const d = f.contentDocument;
      if (!d) continue;
      const maps = d.querySelectorAll('wx-map');
      if (!maps.length) continue;
      const map = maps[0];
      const container = map.querySelector('.wx-gl-map-container');
      if (!container) continue;
      const markers = [];
      const all = container.querySelectorAll('*');
      for (const el of all) {
        const style = el.getAttribute('style') || '';
        if (!/translate3d/.test(style)) continue;
        const text = (el.innerText || '').trim();
        const img = el.querySelector('img');
        let x = null, y = null;
        const m = style.match(/translate3d\\(([-\\d.]+)px,\\s*([-\\d.]+)px/);
        if (m) { x = parseFloat(m[1]); y = parseFloat(m[2]); }
        if (text || img) {
          markers.push({
            x: x !== null ? Math.round(x * 10) / 10 : null,
            y: y !== null ? Math.round(y * 10) / 10 : null,
            text: text.slice(0, 120),
            img: img ? img.src.slice(0, 60) : '',
          });
        }
      }
      return {
        mapCenter: { lat: map.getAttribute('latitude'), lng: map.getAttribute('longitude') },
        scale: map.getAttribute('scale'),
        markerCount: markers.length,
        markers,
      };
    } catch(e) {}
  }
  return null;
})()`;

// Web Mercator 换算 (与 final-convert.py 相同, 含锚点校准)
function lnglatToPix(lng, lat, world) {
  const x = (lng + 180) / 360 * world;
  const sin = Math.sin(lat * Math.PI / 180);
  const y = (0.5 - Math.log((1 + sin) / (1 - sin)) / (4 * Math.PI)) * world;
  return { x, y };
}
function pixToLngLat(px, py, world) {
  const lng = px / world * 360 - 180;
  const n = Math.PI - 2 * Math.PI * py / world;
  const lat = 180 / Math.PI * Math.atan(0.5 * (Math.exp(n) - Math.exp(-n)));
  return { lat, lng };
}

function convert(markers, mapCenter, scale) {
  const world = 256 * Math.pow(2, scale);
  const VW = 414, VH = 781;
  const centerLat = parseFloat(mapCenter.lat);
  const centerLng = parseFloat(mapCenter.lng);
  const c = lnglatToPix(centerLng, centerLat, world);

  // 锚点校准 (闵塔公路)
  const a = lnglatToPix(121.17, 31.03, world);
  const offsetX = a.x - c.x - (201 - VW / 2);
  const offsetY = a.y - c.y - (394.8 - VH / 2);

  return markers.map(m => {
    if (m.x === null || m.y === null) return { ...m, lat: null, lng: null };
    const px = c.x + (m.x - VW / 2) + offsetX;
    const py = c.y + (m.y - VH / 2) + offsetY;
    const ll = pixToLngLat(px, py, world);
    return { ...m, lat: Math.round(ll.lat * 1e6) / 1e6, lng: Math.round(ll.lng * 1e6) / 1e6 };
  });
}

async function main() {
  console.log('=== One-shot capture ===');
  let out = null;
  for (let attempt = 1; attempt <= 8; attempt++) {
    try {
      const res = await Promise.race([
        send('Runtime.evaluate', { expression: EXPR, returnByValue: true }),
        new Promise((_, rej) => setTimeout(() => rej(new Error('timeout')), 8000)),
      ]);
      out = res.result.value;
      if (out && out.markerCount > 0) { console.log(`attempt ${attempt}: OK ${out.markerCount} markers`); break; }
      console.log(`attempt ${attempt}: ${out ? out.markerCount + ' markers' : 'null'}`);
    } catch(e) { console.log(`attempt ${attempt}: err ${e.message.slice(0, 30)}`); }
    await wait(1000);
  }
  if (!out || !out.markerCount) { console.log('FAILED'); process.exit(1); }

  // 换算
  const markers = convert(out.markers, out.mapCenter, out.scale);
  const stamp = new Date().toISOString().replace(/[:.]/g, '-').slice(11, 19);

  // 原始 json
  const rawFile = `${DIR}\\点位-${stamp}.json`;
  fs.writeFileSync(rawFile, JSON.stringify({ ...out, markers }, null, 2), 'utf-8');

  // 经纬度 json
  const llFile = `${DIR}\\点位-${stamp}-经纬度.json`;
  fs.writeFileSync(llFile, JSON.stringify({
    captured_at: new Date().toISOString(),
    map_center: out.mapCenter,
    scale: out.scale,
    coordinate_system: 'GCJ-02 (近似)',
    markerCount: markers.length,
    markers,
  }, null, 2), 'utf-8');

  // CSV
  const csvFile = `${DIR}\\点位-${stamp}-经纬度.csv`;
  const csv = 'text,screen_x,screen_y,lat,lng,img\n' +
    markers.map(m => `${JSON.stringify(m.text)},${m.x},${m.y},${m.lat},${m.lng},${m.img || ''}`).join('\n');
  fs.writeFileSync(csvFile, csv, 'utf-8');

  console.log('=== 落盘完成 ===');
  console.log(' ', rawFile);
  console.log(' ', llFile);
  console.log(' ', csvFile);
  console.log(`点位: ${markers.length} | 中心: ${out.mapCenter.lat}, ${out.mapCenter.lng} | scale ${out.scale}`);
  console.log('样例:', markers.slice(0, 3).map(m => `(${m.lat}, ${m.lng}) ${m.text.slice(0, 20)}`).join(' | '));
  ws.close();
  process.exit(0);
}

ws.onopen = main;
ws.onmessage = (evt) => {
  let msg;
  try { msg = JSON.parse(evt.data.toString()); } catch(e) { return; }
  if (msg.id && pending.has(msg.id)) {
    const { resolve, reject } = pending.get(msg.id);
    pending.delete(msg.id);
    if (msg.error) reject(new Error(JSON.stringify(msg.error)));
    else resolve(msg.result);
  }
};
ws.onerror = (e) => { console.log('ws error:', e.message); process.exit(1); };
setTimeout(() => { console.log('TOTAL TIMEOUT'); process.exit(1); }, 30000);
