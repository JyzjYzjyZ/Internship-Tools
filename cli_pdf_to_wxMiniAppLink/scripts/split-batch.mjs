// split-batch.mjs <batchName> - 把 raw.jsonl 里"上次分割后新增"的请求整理成独立批次存档
// 用法: node split-batch.mjs 批次1
import fs from 'node:fs';

const DIR = 'C:\\Users\\65164\\Desktop\\抓包';
const RAW = DIR + '\\raw.jsonl';
const MARK = DIR + '\\last-line.txt';
const batchName = process.argv[2] || `batch-${Date.now()}`;

// 读上次处理到第几行
let startLine = 0;
try { startLine = parseInt(fs.readFileSync(MARK, 'utf-8').trim() || '0', 10); } catch(e) {}

const lines = fs.readFileSync(RAW, 'utf-8').split('\n').filter(Boolean);
const newLines = lines.slice(startLine);

if (!newLines.length) {
  console.log('无新增请求(上次分割后没有新数据)');
  process.exit(0);
}

const recs = newLines.map(l => JSON.parse(l));
console.log(`新增请求: ${newLines.length} 条 (从行 ${startLine+1} 到 ${lines.length})`);

// ===== 业务参数 JSON =====
const business = recs.map(r => {
  // 解析 URL query
  const u = new URL(r.url);
  const query = Object.fromEntries(u.searchParams.entries());
  return {
    ts: new Date(r.ts).toISOString(),
    method: r.method,
    endpoint: u.origin + u.pathname,
    query_params: query,
    post_body: r.postData,
    headers: r.headers,
  };
});
const jsonPath = `${DIR}\\${batchName}-业务参数.json`;
fs.writeFileSync(jsonPath, JSON.stringify(business, null, 2), 'utf-8');

// ===== 分析 MD =====
let md = `# 抓包批次: ${batchName}\n\n> 时间: ${new Date().toISOString()} | 小程序: wxb35d66d9d73f7991 (摩托地图)\n`;
md += `> 本批 ${recs.length} 个业务请求\n\n`;

recs.forEach((r, i) => {
  const u = new URL(r.url);
  md += `## 请求 ${i+1}: ${r.method} ${u.origin}${u.pathname}\n\n`;
  md += `**完整 URL:**\n\`\`\`\n${r.url}\n\`\`\`\n\n`;
  md += `**Query 参数(明文):**\n\n| 参数 | 值 |\n|---|---|\n`;
  for (const [k, v] of Object.entries(Object.fromEntries(u.searchParams.entries()))) {
    md += `| ${k} | \`${(v||'').slice(0,120)}\` |\n`;
  }
  if (r.postData) {
    md += `\n**POST Body(明文):**\n\`\`\`\n${r.postData.slice(0, 1500)}\n\`\`\`\n`;
  }
  md += `\n**关键 Headers(明文):**\n\n`;
  for (const k of ['X-YH-Token', 'Cookie', 'Authorization', 'Referer']) {
    if (r.headers[k]) md += `- \`${k}\`: \`${r.headers[k].slice(0, 120)}\`\n`;
  }
  md += `\n---\n\n`;
});

// 明文/密文结论
md += `## 本批加密状态\n\n`;
const allPlain = recs.every(r => !r.url.includes('sign=') && !r.url.includes('encrypt=') && !r.postData?.includes('q='));
md += allPlain ? `**全程明文,无加密参数** (无 q/sign/token 加密签名,仅 X-YH-Token 明文鉴权)\n` : `**含加密参数,需逐请求分析**\n`;

const mdPath = `${DIR}\\${batchName}-分析.md`;
fs.writeFileSync(mdPath, md, 'utf-8');

// 更新 mark
fs.writeFileSync(MARK, String(lines.length), 'utf-8');

console.log(`已保存:\n  ${jsonPath}\n  ${mdPath}`);
console.log(`下次分割将从行 ${lines.length} 开始`);
