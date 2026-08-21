# 最终换算: 用 offset 校准法, 把点位屏幕坐标转成经纬度, 落盘
import json, os, math, csv

base = os.path.join(os.environ['USERPROFILE'], 'Desktop', '抓包', '点位采集')
src = os.path.join(base, '点位-08-53-54.json')
d = json.load(open(src, encoding='utf-8'))

center_lat, center_lng = 31.223520278930664, 121.4559097290039
scale = 8
world = 256 * 2**scale
VW, VH = 414, 781

def lnglat_to_pix(lng, lat):
    x = (lng + 180) / 360 * world
    sin = math.sin(math.radians(lat))
    y = (0.5 - math.log((1+sin)/(1-sin)) / (4*math.pi)) * world
    return x, y

def pix_to_lnglat(px, py):
    lng = px / world * 360 - 180
    n = math.pi - 2*math.pi*py/world
    lat = math.degrees(math.atan(math.sinh(n)))
    return lat, lng

cx, cy = lnglat_to_pix(center_lng, center_lat)

# offset 校准 (来自 闵塔公路锚点)
anchor_lat, anchor_lng = 31.03, 121.17   # 闵塔公路/辰塔路交叉口 (上海松江, 近似)
ax, ay = lnglat_to_pix(anchor_lng, anchor_lat)
# 屏幕(201, 394.8) 是闵塔
offset_x = ax - cx - (201 - VW/2)
offset_y = ay - cy - (394.8 - VH/2)

converted = []
for m in d['markers']:
    if m['x'] is None or m['y'] is None:
        converted.append({**m, 'lat': None, 'lng': None})
        continue
    px = cx + (m['x'] - VW/2) + offset_x
    py = cy + (m['y'] - VH/2) + offset_y
    lat, lng = pix_to_lnglat(px, py)
    converted.append({**m, 'lat': round(lat, 6), 'lng': round(lng, 6)})

out = {
    'source': src,
    'converted_at': __import__('datetime').datetime.now().isoformat(),
    'method': 'WebMercator + 锚点校准 (闵塔公路 offset)',
    'coordinate_system': 'GCJ-02 (腾讯地图), 近似值',
    'note': '锚点闵塔公路(31.03,121.17)为近似估计, 存在~0.1度误差; 如需精确需从polygons取真实锚点',
    'map_center': d['mapCenter'],
    'scale': scale,
    'markerCount': len(converted),
    'markers': converted,
}
outf = os.path.join(base, '点位-08-53-54-经纬度.json')
json.dump(out, open(outf, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)

# CSV
csvf = os.path.join(base, '点位-08-53-54-经纬度.csv')
with open(csvf, 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.writer(f)
    w.writerow(['text', 'screen_x', 'screen_y', 'lat', 'lng'])
    for m in converted:
        w.writerow([m['text'], m['x'], m['y'], m['lat'], m['lng']])

print('converted:', len(converted))
print('saved:', outf)
print('saved:', csvf)
print('\nsample:')
for m in converted[:8]:
    print(f"  ({m['lat']:.4f}, {m['lng']:.4f}) {m['text'][:30]}")
