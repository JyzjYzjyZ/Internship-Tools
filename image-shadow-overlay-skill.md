---
name: image-shadow-overlay
description: 给透明方形覆盖图生成 PS 风格投影（基于 alpha），缩放后叠加到底图上。适用于"产品贴图浮在背景上"的场景。触发词: 阴影、投影、叠加、drop shadow。
---

# 图像阴影叠加 (PS 风格投影 + 缩放叠加)

## 用途
把一组带透明的方形覆盖图（如产品图、抠图素材）按 PS 图层样式加投影后，叠到另一组同名底图上。自动缩放覆盖图到与底图一致。

## 逻辑链
1. **配对应**：遍历底图目录，找同名覆盖图（`底图目录/a.png` ↔ `覆盖目录/a.png`）。
2. **缩放**：覆盖图用 `LANCZOS` 高质量等比缩放到底图尺寸。
3. **生成投影**（PS Drop Shadow 算法）：
   - 取覆盖图 alpha 通道 → 填充纯黑实心蒙版
   - 按距离 (offset) 平移
   - 高斯模糊（半径 = 大小/2）
   - **扩展 (spread)** 映射：`a' = 255*(a-low)/(255-low)`，`low=255*(1-spread)`，低于 low 归零 —— 阴影边缘收硬
   - 按不透明度缩放 alpha
4. **合成**：底图 → alpha_composite(投影) → alpha_composite(覆盖图)。
5. **输出**：PNG，与底图同名，输出到指定目录。

## 关键点
- 覆盖图必须有透明通道（无透明时投影不可见；可用脚本里 CheckAlpha 逻辑先检测）。
- **大小 (Size) ↔ 模糊半径**：PS 大小 = 半径 × 2（Size 18 → 模糊半径 9）。
- 覆盖图内容贴边时，阴影会溢出画布被裁掉，检查成品边缘。

## 完整代码 (Python + Pillow)

```python
import os
from PIL import Image, ImageFilter

BASE_DIR = r"C:\Users\65164\Desktop\底图目录"      # 底图 (1080x1080)
OVER_DIR = r"C:\Users\65164\Desktop\覆盖图目录"    # 带透明方形覆盖图 (5528x5528)
OUT_DIR = os.path.join(BASE_DIR, "叠加")

# PS 投影参数 —— 当前值 = 基准值 x3
SHADOW_OFFSET = (36, 36)    # 距离 12 -> 36px
SHADOW_BLUR = 27            # 大小 18 -> 54，半径 = 54/2
SHADOW_ALPHA = 0.72         # 不透明度 72%
SHADOW_SPREAD = 0.57        # 扩展 19% -> 57%
SHADOW_COLOR = (0, 0, 0)    # 纯黑

os.makedirs(OUT_DIR, exist_ok=True)

def add_shadow(overlay, offset, blur, alpha, spread):
    """PS 投影: 黑色蒙版 -> 偏移 -> 高斯模糊 -> spread 扩展 -> 缩不透明度"""
    shadow = Image.new("RGBA", overlay.size, (0, 0, 0, 0))
    black = Image.new("RGBA", overlay.size, SHADOW_COLOR + (255,))
    black.paste(SHADOW_COLOR + (255,), (0, 0), overlay.getchannel("A"))
    shadow.paste(black, offset, black)
    shadow = shadow.filter(ImageFilter.GaussianBlur(blur))
    a = shadow.getchannel("A")
    if spread > 0:
        low = 255 * (1 - spread)
        a = a.point(lambda v: int(255 * (v - low) / (255 - low)) if v > low else 0)
    if alpha < 1.0:
        a = a.point(lambda v: int(v * alpha))
    shadow.putalpha(a)
    return shadow

for name in sorted(os.listdir(BASE_DIR)):
    if not name.lower().endswith(".png"):
        continue
    base_path = os.path.join(BASE_DIR, name)
    over_path = os.path.join(OVER_DIR, name)
    if not os.path.exists(over_path):
        print("SKIP 无对应覆盖图:", name)
        continue

    base = Image.open(base_path).convert("RGBA")
    overlay = Image.open(over_path).convert("RGBA")
    overlay = overlay.resize(base.size, Image.LANCZOS)  # 缩放铺满

    shadow = add_shadow(overlay, SHADOW_OFFSET, SHADOW_BLUR, SHADOW_ALPHA, SHADOW_SPREAD)

    result = base.copy()
    result.alpha_composite(shadow)
    result.alpha_composite(overlay)
    result.convert("RGB").save(os.path.join(OUT_DIR, name))
    print("OK", name, "->", result.size)

print("done")
```

## 参数速调
| PS 参数 | 变量 | 说明 |
|---|---|---|
| 距离 | `SHADOW_OFFSET` | 偏移 px，(x, y) |
| 大小 | `SHADOW_BLUR` | 模糊半径 = 大小/2 |
| 扩展 | `SHADOW_SPREAD` | 0~1，越大边缘越实 |
| 不透明度 | `SHADOW_ALPHA` | 0~1 |
| 颜色 | `SHADOW_COLOR` | RGB 元组 |

## 运行
```bash
python overlay_shadow.py
```
（依赖: `pip install Pillow`）
