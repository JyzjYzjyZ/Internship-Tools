#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
slice_by_alpha.py — 按 alpha 通道把拼接图切成独立的矩形图片。

原理:整张图片由若干不透明矩形拼接而成,矩形之间隔着完全(或接近)透明的
行/列间隙。脚本对每一行/列统计不透明像素占比,低于 --tol 的视为间隙,
把连续的不透明行段、列段分别聚成"行带/列带",再按 行带×列带 组合出每个
矩形的包围盒并裁剪。

用法:
    python slice_by_alpha.py <输入图片> <输出文件夹> [选项]

示例:
    python slice_by_alpha.py Desktop\\outputA.png Desktop\\slices
    python slice_by_alpha.py out.png slices --prefix A

参数:
    输入图片    Pillow 可读格式(PNG/JPG/WebP…),建议 RGBA PNG。
    输出文件夹  不存在则自动创建。
    --prefix    输出文件名前缀,默认取输入文件主名。
                如 outputA.png → outputA_01.png、outputA_02.png …
    --tol       行/列不透明像素占比低于该值判定为间隙,默认 0.001(0.1%)。
                纯透明间隙是 0;小杂点可调大到 0.01~0.05。
    --dry-run   只打印将切出的矩形与数量,不写文件。

输出命名按行优先(从左到右、自上而下):{prefix}_{NN:02d}.png
"""

import argparse
import os
import sys

import numpy as np
from PIL import Image


def load_alpha(path: str) -> np.ndarray:
    """读取图片,返回 alpha 通道数组;无 alpha 通道则视为全不透明。"""
    img = Image.open(path)
    if img.mode == "RGBA":
        return np.array(img)[:, :, 3]
    if img.mode == "LA":
        return np.array(img)[:, :, 1]
    # RGB / 其他:没有透明信息,当作整张不透明
    arr = np.array(img.convert("RGBA"))
    return arr[:, :, 3]


def opaque_bands(mask: np.ndarray, tol: float) -> list:
    """根据逐行/逐列不透明比例掩码,返回连续不透明段 [(start, end), ...](含端点)。"""
    keep = mask > tol
    bands = []
    start = None
    for i, v in enumerate(keep):
        if v and start is None:
            start = i
        elif not v and start is not None:
            bands.append((start, i - 1))
            start = None
    if start is not None:
        bands.append((start, len(keep) - 1))
    return bands


def slice_image(src: str, dst_dir: str, prefix: str, tol: float, dry_run: bool) -> int:
    alpha = load_alpha(src)
    h, w = alpha.shape

    row_ratio = (alpha > 0).mean(axis=1)   # 每行不透明占比
    col_ratio = (alpha > 0).mean(axis=0)   # 每列不透明占比

    row_bands = opaque_bands(row_ratio, tol)
    col_bands = opaque_bands(col_ratio, tol)

    if not row_bands or not col_bands:
        print(f"错误:未检测到任何不透明内容(整图透明?)。{src}", file=sys.stderr)
        return 0

    cells = []  # (col_band, row_band)
    for (y0, y1) in row_bands:
        for (x0, x1) in col_bands:
            cells.append((x0, y0, x1, y1))

    print(f"图片 {w}x{h},行带 {len(row_bands)} 个,列带 {len(col_bands)} 个 → 共 {len(cells)} 张")
    for i, (x0, y0, x1, y1) in enumerate(cells, 1):
        cw, ch = x1 - x0 + 1, y1 - y0 + 1
        print(f"  [{i:02d}]  x[{x0},{x1}] y[{y0},{y1}]  尺寸 {cw}x{ch}")
    if not cells:
        print("没有可切的矩形。", file=sys.stderr)
        return 0

    if dry_run:
        return len(cells)

    os.makedirs(dst_dir, exist_ok=True)
    img = Image.open(src).convert("RGBA")
    for i, (x0, y0, x1, y1) in enumerate(cells, 1):
        name = f"{prefix}_{i:02d}.png"
        img.crop((x0, y0, x1 + 1, y1 + 1)).save(os.path.join(dst_dir, name))
        print(f"已写出 {name}")
    print(f"完成,共 {len(cells)} 张 → {os.path.abspath(dst_dir)}")
    return len(cells)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="按 alpha 通道把拼接图切成独立的矩形图片",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("input", help="输入图片路径")
    parser.add_argument("output", help="输出文件夹路径(不存在则创建)")
    parser.add_argument("--prefix", help="输出文件名前缀(默认取输入文件主名)")
    parser.add_argument("--tol", type=float, default=0.001,
                        help="行/列不透明占比低于该值视为间隙")
    parser.add_argument("--dry-run", action="store_true", help="只打印不写文件")
    args = parser.parse_args()

    if not os.path.isfile(args.input):
        print(f"错误:找不到输入文件 {args.input}", file=sys.stderr)
        sys.exit(1)

    prefix = args.prefix or os.path.splitext(os.path.basename(args.input))[0]
    n = slice_image(args.input, args.output, prefix, args.tol, args.dry_run)
    if n == 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
