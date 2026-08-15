#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""install.py — 交互式安装 / 覆盖 vision-bridge skill（并写入 Kimi 3 API key）.

流程:
  1. 若目标 ~/.claude/skills/vision-bridge 已存在，提醒会覆盖旧的 vision-bridge skill
  2. 向用户索要 Kimi 3 (kimi-k3 / Moonshot 平台) 的 API key
  3. 用户确认后，把本目录的 skill 文件复制到目标位置，并把 key 写入目标 config.json

选项:
  --target <dir>   安装到自定义目录（默认 ~/.claude/skills/vision-bridge）
  --dry-run        只预览将执行的操作，不实际写入

运行方式（在 skill 目录下或任何地方）:
  python install.py
"""
import sys
import json
import shutil
import argparse
from pathlib import Path

SKILL_NAME = "vision-bridge"
CONFIG_NAME = "config.json"
DEFAULT_MODEL = "kimi-k3"
DEFAULT_BASE_URL = "https://api.moonshot.cn/v1"


def main():
    ap = argparse.ArgumentParser(
        description="Install/overwrite the vision-bridge skill and embed a Kimi 3 API key.")
    ap.add_argument("--target",
                    default=str(Path.home() / ".claude" / "skills" / SKILL_NAME),
                    help=f"install target dir (default: ~/.claude/skills/{SKILL_NAME})")
    ap.add_argument("--dry-run", action="store_true",
                    help="preview actions, write nothing")
    args = ap.parse_args()

    source = Path(__file__).resolve().parent
    target = Path(args.target).expanduser()
    cfg_path = target / CONFIG_NAME

    print("vision-bridge skill 安装器")
    print(f"  源目录:   {source}")
    print(f"  目标目录: {target}")

    # ---- dry-run: 只预览，不询问、不写入 ----
    if args.dry_run:
        print()
        print("[dry-run] 预览:")
        print(f"  覆盖提醒: {'是（目标已存在，会替换旧 vision-bridge skill）' if target.exists() else '否（全新安装）'}")
        print(f"  会询问:   Kimi 3 API key，确认后写入目标 {CONFIG_NAME}")
        print(f"  会复制:   SKILL.md、scripts/ 等（跳过 {CONFIG_NAME} 与 __pycache__）")
        print(f"  会写入:   {cfg_path}（含用户提供的 key）")
        print("[dry-run] 未做任何修改。")
        return 0

    # ---- 1) 覆盖提醒 ----
    if target.exists():
        print("⚠️  目标目录已存在，安装将覆盖现有的 vision-bridge skill。")
        ans = input("  是否继续? [y/N] ").strip().lower()
        if ans not in ("y", "yes"):
            print("已取消。")
            return 1
    else:
        print("ℹ️  将全新安装。")

    # ---- 2) 索要 Kimi 3 key ----
    print()
    print(f"请输入 Kimi 3 的 API key（Moonshot 平台，模型 {DEFAULT_MODEL}，形如 sk-...）。")
    print("留空表示不写入 key，运行时将回退到环境变量 VISION_API_KEY 或内置默认 key。")
    key = input("Kimi 3 API key: ").strip()
    if "\n" in key or "\r" in key:
        print("错误: key 不能包含换行。")
        return 1

    # ---- 3) 最终确认 ----
    print()
    print("即将执行:")
    print("  1. 复制 skill 文件 ->", target)
    print(f"  2. 写入 {CONFIG_NAME}（含 API key {'√' if key else '×（跳过）'}）")
    ans = input("确认安装? [y/N] ").strip().lower()
    if ans not in ("y", "yes"):
        print("已取消。")
        return 1

    # ---- 安装 ----
    target.mkdir(parents=True, exist_ok=True)

    # 备份旧 config.json，避免误覆盖丢 key
    if cfg_path.exists():
        try:
            shutil.copy2(cfg_path, cfg_path.with_suffix(".json.bak"))
        except OSError:
            pass

    # 复制 skill 文件（跳过 config.json / __pycache__）
    if source.resolve() != target.resolve():
        def _ignore(d, names):
            return {n for n in names if n in (CONFIG_NAME, "__pycache__")}
        try:
            shutil.copytree(source, target, dirs_exist_ok=True, ignore=_ignore)
            print("  ✅ 已复制 skill 文件。")
        except Exception as e:
            print("错误: 复制文件失败:", e)
            return 1
    else:
        print("  检测到从已安装位置运行，跳过文件复制。")

    # 写入 key
    if key:
        cfg = {
            "model": DEFAULT_MODEL,
            "base_url": DEFAULT_BASE_URL,
            "api_key": key,
        }
        cfg_path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n",
                            encoding="utf-8")
        print("  ✅ 已写入 API key ->", cfg_path)
    else:
        print("  ℹ️  未写入 key，运行时将使用环境变量 VISION_API_KEY 或内置默认 key。")

    print()
    print("✅ 安装完成。重启终端后生效。")
    print("   安全提示: key 以明文保存在", cfg_path, "，请勿分享/同步该目录。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
