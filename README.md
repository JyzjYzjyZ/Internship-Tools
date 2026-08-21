# Internship-Tools
This repository hosts various tools I built during my internship to streamline daily workflows. It includes scripts, automation utilities, configuration files, and reusable code snippets for quick access and continuous improvement.

- **vision-bridge-skill-installer/vision-bridge** 对于安装了Claude code assistant for vscode插件，使用vscode作为claude code cli前端页面。可以在对话框黏贴图片，然后使用kimi作为deepseek的眼睛
- **中旅旅行搜索复制链接-skill.md** 中旅编号转换是将旅游产品的编号在小程序里面自动转成小程序链接。工作需求是这样的，遂尝试
  | 3300501086 | #小程序://中旅旅行/F49KbQSlGyMcSii |
  |---|---|
- **travel-product-naming** 批量命名文旅/疗休养产品，统一格式为「编号 目的地 · 主题1,主题2-交通方式N日」，支持多种编号、排序与子分区，（AI概括局限需人工验收）
  | 原文件名 | 新命名 |
  |---|---|
  | 红旅产品本地游A线.docx | `A1 上海 · 寻红色之源,忆党史光辉-漫步半日` |
  | 外滩万国建筑博览Citywalk、上海大厦自助午餐1日游.pdf | `B21 上海 · 上海大厦自助午餐,外滩万国建筑博览-Citywalk1日` |
  | 16 内蒙-呼和浩特 辉腾锡大草原 响沙湾（住呼和浩特）疗休养双飞6日.pdf | `C34 内蒙古呼和浩特 · 辉腾锡勒大草原,响沙湾-双飞疗休养6日` |
  | 04 福建厦门疗休养双飞六日游（4-6月）.doc | `C20 福建厦门-泉州 · 鼓浪屿,蟳埔渔村簪花-双飞疗休养6日` |
- **cli_pdf_to_wxMiniAppLink** 将pdf转成小程序链接
  | 产品名称 | 小程序链接 |
  |---------|-----------|
  | 湖北武汉-恩施 · 黄鹤楼,恩施大峡谷高铁6日 | #小程序://查看二维码/sZQI7841kERklrr |
  | 江苏常熟 · 沙家浜景区,尚湖风景区2日 | #小程序://查看二维码/wycuwVtaplL8vQC |
  | 江西南昌-井冈山-瑞金 · 井冈山革命博物馆,瑞金叶坪旧址群火车7日 | #小程序://查看二维码/qifgMRWHjcC0oYe |
  | 上海漫步 · 静安雕塑公园,淞浦特委机关旧址1日 | #小程序://查看二维码/2TSk12UlNBbGk3c |
- **pdf-to-html** 如名,image形式
- **pdf-to-editable-html** 如名，可编辑html
- **slice_by_alpha.py** 文件将figma导出的图片按照alpha裁剪。用于方便的导出一整个组
- **image-shadow-overlay-skill.md** 批量为图片创建阴影随后叠加在另一个图片上
- **图片批量裁剪工具.html** 一套裁剪所有图片共用 批量裁剪文件夹图片
- - 没有提及的功能价值相对没有那么高，忽略即可
