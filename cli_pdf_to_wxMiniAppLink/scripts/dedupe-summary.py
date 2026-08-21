# 汇总去重: 合并所有点位文件, 按名称去重, 统计覆盖
import json, os, glob

base = os.path.join(os.environ['USERPROFILE'], 'Desktop', '抓包', '点位采集')
files = sorted(glob.glob(os.path.join(base, '点位-*-经纬度.json')))
print(f'找到 {len(files)} 个点位文件:')
for f in files:
    print('  ', os.path.basename(f))

# 合并去重 (按 text 名称)
seen = {}
all_points = []
for f in files:
    d = json.load(open(f, encoding='utf-8'))
    for m in d.get('markers', []):
        if not m.get('text'): continue
        all_points.append(m)
        key = m['text']
        if key not in seen:
            seen[key] = m

print(f'\n总记录: {len(all_points)}')
print(f'去重后点位: {len(seen)}')

# 经纬度范围
lats = [m['lat'] for m in seen.values() if m.get('lat')]
lngs = [m['lng'] for m in seen.values() if m.get('lng')]
if lats:
    print(f'纬度范围: {min(lats):.4f} ~ {max(lats):.4f}')
    print(f'经度范围: {min(lngs):.4f} ~ {max(lngs):.4f}')

# 落盘
out = {
    'summary_at': __import__('datetime').datetime.now().isoformat(),
    'source_files': len(files),
    'total_records': len(all_points),
    'unique_points': len(seen),
    'lat_range': [min(lats), max(lats)] if lats else None,
    'lng_range': [min(lngs), max(lngs)] if lngs else None,
    'points': list(seen.values()),
}
outf = os.path.join(os.environ['USERPROFILE'], 'Desktop', '抓包', '去重汇总.json')
json.dump(out, open(outf, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
print(f'\n已保存: {outf}')

# 简单分布: 纬度区间分桶
if lats:
    print('\n纬度分布(每0.5度):')
    for bucket in range(int(min(lats)//0.5), int(max(lats)//0.5)+1):
        lo, hi = bucket*0.5, (bucket+1)*0.5
        cnt = sum(1 for m in seen.values() if m.get('lat') and lo <= m['lat'] < hi)
        if cnt:
            print(f'  {lo:.1f}~{hi:.1f}°N: {cnt} 个点位')
