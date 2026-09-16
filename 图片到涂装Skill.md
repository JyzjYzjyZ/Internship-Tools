# 摩托车涂装转渐变风格网页生成 Skill

## 技能概述
此 Skill 旨在将用户上传的同一款摩托车的多张不同涂装图片，自动提取颜色，并生成为一个干净的、类似官方配置器的网页。网页使用斜向 45 度的渐变块来代表每种涂装，并通过一个按钮进行循环切换。

## 触发条件
用户上传 1 张或多张同一款摩托车不同涂装的图片，并提及“涂装转渐变”、“生成配置器网页”或直接调用此 Skill。

## 处理逻辑与规则

### 1. 图片分析与颜色提取
- 识别用户上传的图片数量（记为 N），对应 N 种涂装。
- 对每一张图片提取**最多两种**最具代表性的车身主色调（尽量提取车漆颜色，忽略背景、排气管等非涂装部分）。
- **限制**：每种涂装的颜色最多两种。

### 2. HTML 结构要求
- 生成一个包含 N 个 `div` 的容器。这 N 个 `div` 分别对应 N 种涂装的渐变。
- 容器形状需使用 `border-radius` 模拟摩托车整流罩的流线型。
- 包含一个固定在底部的黑色按钮，用于切换涂装。

### 3. CSS 渐变规则
- 必须使用 **斜向 45 度** 的线性渐变：`linear-gradient(45deg, color1, color2)`。
- 初始状态下，只有第一个 `div` 拥有 `active` 类名（可见），其余隐藏（`opacity: 0`）。
- 使用 `transition` 增加切换时的平滑过渡效果（淡入淡出配合轻微缩放 `transform: scale`）。

### 4. JavaScript 交互逻辑
- 监听按钮点击事件。
- 使用取模运算 `(currentIndex + 1) % N` 实现循环切换。
- 切换时移除上一个 `div` 的 `active` 类，给下一个 `div` 添加 `active` 类。

### 5. 视觉风格要求（参考图4 UI）
- 网页背景：浅灰或米白（如 `#f5f5f5`）。
- 按钮样式：深色（如 `#1a1a1a`），白色粗体字，带有微小的圆角和阴影，悬停时有变色反馈。

## 输出格式
直接输出一个完整的、可直接在浏览器运行的 HTML 单文件代码（包含内联的 CSS 和 JS）。并在代码前后附上简短的视觉提取说明。

---

## 提示词模板（用户直接复制使用）

> 请使用【摩托车涂装转渐变风格网页生成 Skill】为我生成代码。
> 我上传了 N 张图片，它们是同一辆车的不同涂装。
> 请提取颜色，确保每个渐变最多两种颜色，斜向 45 度。
> 生成包含 N 个 div 的 HTML 文件，并带有一个按钮来循环切换这些渐变，风格要类似干净现代的配置器 UI。

---

## 参考代码骨架（供 AI 生成时参考）

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>摩托车涂装切换</title>
    <style>
        body {
            margin: 0; display: flex; justify-content: center; align-items: center; min-height: 100vh;
            background-color: #f5f5f5; font-family: sans-serif;
        }
        .container { display: flex; flex-direction: column; align-items: center; gap: 40px; }
        .paint-wrapper {
            position: relative; width: 420px; height: 220px;
            border-radius: 30px 100px 30px 80px; /* 流线型 */
            box-shadow: 0 20px 40px rgba(0,0,0,0.15); overflow: hidden; background-color: #fff;
        }
        .paint {
            position: absolute; top: 0; left: 0; width: 100%; height: 100%;
            opacity: 0; transition: opacity 0.6s ease, transform 0.6s ease;
            transform: scale(0.95); border-radius: inherit;
        }
        .paint.active { opacity: 1; transform: scale(1); }
        
        /* 动态生成的渐变，替换提取的颜色 */
        .paint-1 { background: linear-gradient(45deg, #提取色1, #提取色2); }
        .paint-2 { background: linear-gradient(45deg, #提取色1, #提取色2); }
        /* ...N个 */

        #toggle-btn {
            padding: 16px 45px; font-size: 16px; font-weight: 600; color: #fff;
            background-color: #1a1a1a; border: none; border-radius: 8px; cursor: pointer;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1); letter-spacing: 1px;
        }
        #toggle-btn:hover { background-color: #333; }
        #toggle-btn:active { transform: scale(0.97); }
    </style>
</head>
<body>
    <div class="container">
        <div class="paint-wrapper">
            <!-- 根据图片数量N动态生成 -->
            <div class="paint paint-1 active"></div>
            <div class="paint paint-2"></div>
            <!-- ... -->
        </div>
        <button id="toggle-btn">切换涂装</button>
    </div>
    <script>
        const paints = document.querySelectorAll('.paint');
        const toggleBtn = document.getElementById('toggle-btn');
        let currentIndex = 0;
        toggleBtn.addEventListener('click', () => {
            paints[currentIndex].classList.remove('active');
            currentIndex = (currentIndex + 1) % paints.length;
            paints[currentIndex].classList.add('active');
        });
    </script>
</body>
</html>