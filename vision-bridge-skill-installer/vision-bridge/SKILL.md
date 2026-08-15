---
name: vision-bridge
auth:JyzjYzjyZ,shiningCockroach
description: Give vision capability to non-vision LLMs (e.g. DeepSeek) by sending images to an external vision model (default agnes-2.5-flash, OpenAI-compatible) and returning text descriptions. 为无视觉能力的大模型（如 DeepSeek）提供识图能力：把图片发给外部视觉模型（默认 agnes-2.5-flash，OpenAI 兼容协议）并返回文字描述。Use this skill whenever the user shares a local image path or network image URL, a message contains "Saved attachments:", a message contains an image tag like `[Image: ...]` / `[Unsupported Image]` / `[image` (a pasted image — run `vision-bridge.py --from-transcript` and it auto-pulls the image from the Claude Code session transcript .jsonl), or the user asks to describe/recognize/analyze/interpret an image, extract text from an image (OCR), or understand screenshots, charts, tables, QR codes, or memes — do NOT use the Read tool to look at images (the underlying model has no vision). 当用户分享本地图片路径或网络图片 URL、消息中出现 "Saved attachments:"、消息中出现 `[Image: ...]` / `[Unsupported Image]` / `[image` 等图片标记（表示粘贴了图片——用 `vision-bridge.py --from-transcript` 会自动从 Claude Code 会话记录 .jsonl 提取）、用户要求描述/识别/分析/解读图片、提取图片中的文字（OCR）、理解截图/图表/表格/二维码/表情包，或任何需要"看图"的场景，都必须使用本 skill —— 不要用 Read 工具看图（底层模型无视觉能力）。The skill prompts for configuration once on first use when the vision API is not configured; afterwards it recognizes images automatically without asking again. skill 首次使用且视觉 API 未配置时，引导用户配置一次；配置后自动识图，不再询问。
---

# vision-bridge — Vision for non-vision LLMs

Your underlying model has no native vision capability. For anything that requires "seeing" an image, **do NOT use the Read tool** — call the bundled script `vision-bridge.py`, which asks an external vision model to "look" for you and returns text.

## When to trigger

- The user shares a **local image path** or **network image URL**
- The message contains `Saved attachments:` listing images
- The message contains an **image tag** from a pasted image — `[Image: original ...]`, `[Unsupported Image]`, `[image`, etc. When you see one and have no readable file path, call `python vision-bridge.py --from-transcript "<prompt>"`: the script detects the tag and auto-pulls the image's base64 straight from the Claude Code session transcript (`~/.claude/projects/**/*.jsonl`), then analyzes it. Do NOT try to Read the locked temp file or ask the user to save it.
- The user asks to describe, recognize, analyze, interpret an image; extract text (OCR); understand screenshots, charts, tables, QR codes, memes, captchas
- Any task that needs information from an image

## Script location & modes

Script: `scripts/vision-bridge.py` in this skill. Requires only Python 3.9+ standard library — **zero third-party dependencies** (no pip install). Cross-platform: Windows / Linux / macOS / fish.

| Mode | Command | Purpose |
|---|---|---|
| Recognize (default) | `python vision-bridge.py <image-path> [more-images] [prompt] [options]` | Look at the image and return a text description |
| Recognize (URL) | `python vision-bridge.py --url <image-url> [prompt] [options]` | Look at a remote image |
| Recognize (transcript) | `python vision-bridge.py --from-transcript [prompt]` | Pull the most recent image pasted in the Claude Code chat from the session transcript (.jsonl), then look at it. No path needed. Also auto-triggered when the prompt carries an image tag (`[Image: ...]`, `[Unsupported Image]`, `Saved attachments:`) and no path is given. |
| Check config | `python vision-bridge.py check` | Is the vision API configured? (exit 0=yes, 1=no) |
| Configure | `python vision-bridge.py config "<key>"` | Persist VISION_API_KEY across platforms |

If `python` is unavailable on Windows, use `py -3 vision-bridge.py ...` instead.

Common options: `--model <model>`, `--max-tokens <n>`, `--temperature <0~2>`, `--json` (raw JSON response), `config --region global|china` (pin a regional base URL).

## Installation & API key

The skill ships with an interactive installer (`install.py`) in the skill folder. Running it:

1. **Warns** if an existing `vision-bridge` skill at `~/.claude/skills/vision-bridge` will be **overwritten**.
2. **Asks for your Kimi 3 (kimi-k3 / Moonshot)** API key (`sk-...`).
3. After confirmation, copies the skill files into place and writes the key into the skill's `config.json`.

```bash
python install.py                 # install / overwrite + set Kimi 3 key
python install.py --dry-run       # preview only, change nothing
python install.py --target <dir>  # install to a custom directory
```

Key priority at runtime: **skill `config.json` → env var `VISION_API_KEY` → built-in fallback**. `config.json` holds `{"model","base_url","api_key"}`; edit it to switch models, or delete it to fall back to the env var. Verify with `python vision-bridge.py check` — it prints `source=skill-config|env-or-builtin`.

## First use: configure once

**Principle**: the API key is only written to an environment variable — never into code, scripts, or any project file, to prevent leakage. Run `check` before recognizing; only guide the user when `VISION_API_KEY` is missing, and never ask again afterwards.

When not configured, guide the user (offer one of two options):

1. Run `python vision-bridge.py check`, confirm `configured=false`.
2. Tell the user a vision model API key is needed (default agnes, model `agnes-2.5-flash`); ask them to choose **one** way:
   - **Method A (user hands the key over)**: ask the user to paste the API key into the chat; when received, run `python vision-bridge.py config "<user key>"` to persist it. **Do not repeat the key in plaintext in the session afterwards.**
   - **Method B (user configures it themselves)**: send the user this command — they only replace the placeholder inside the quotes:
     ```
     python vision-bridge.py config "your-vision-api-key"
     ```
3. Ask the user to **restart the terminal** (system env vars only take effect for new processes), then verify with `python vision-bridge.py check`.
4. After configuration, immediately recognize the current image.

If the user already has a key and insists on pasting it, reject placeholders like `sk-xxx` or `your-vision-api-key` before persisting.

## Usage

Examples:

```bash
python vision-bridge.py "D:\photos\example.png" "Describe this image"
python vision-bridge.py --url "https://example.com/a.png" "Extract the text"
python vision-bridge.py "img1.png" "img2.png" "Compare these two images"
python vision-bridge.py --from-transcript "描述这张图片"   # 用户在聊天里粘贴的图，自动从会话记录提取
python vision-bridge.py "这张图是什么 [Image: original 2271x1358 ...]"  # 提示词含图片标记时也会自动提取
```

The script: base64-encodes local images → submits all images at once → timeout/retry/error classification (401=bad key, 404=wrong model/URL, 429=rate limited) → prints text to stdout. Surface stderr error messages to the user verbatim on failure.

## Regional base URLs

The default is agnes `agnes-2.5-flash` (free and unlimited; see the [Agnes docs](https://agnes-ai.com/doc/agnes-25-flash)) via an **auto-selected regional endpoint** (an apihub API key works on both):

| Region | Base URL | Note |
|---|---|---|
| Global | `https://apihub.agnes-ai.com/v1` | Faster for users outside mainland China |
| China | `https://api.agnes-ai.cn/v1` | Faster for users in mainland China |

Selection priority: `VISION_BASE_URL` (explicit) > system language (Chinese locale → `.cn`, otherwise → `.com`) > default `.com`.

To pin a region explicitly (e.g. a Chinese user on an English system), use:
```bash
python vision-bridge.py config --region china "your-key"   # writes VISION_BASE_URL too
python vision-bridge.py config --region global "your-key"
```

To use any other OpenAI-compatible vision service:
```bash
# Windows
setx VISION_BASE_URL "https://your-provider/v1"
setx VISION_MODEL "your-vision-model"
# Linux / macOS (write to ~/.bashrc or ~/.zshrc)
export VISION_BASE_URL="https://your-provider/v1"
export VISION_MODEL="your-vision-model"
```

## Notes

- Bilingual UI: script output auto-switches Chinese/English based on system language; force with `VISION_LANG=zh` or `VISION_LANG=en`.
- **Pasted images from the chat UI**: the extension writes them to a temp file that is exclusively locked (unreadable), so the script pulls the base64 from the Claude Code session transcript (`~/.claude/projects/**/*.jsonl`) instead. Use `--from-transcript`, or just include the image tag in the prompt — the script detects it and extracts automatically. It always takes the most recent user-pasted image across all transcripts.
- Images over 10MB trigger a warning (some APIs reject very large images).
- `agnes-2.5-flash` is a **thinking model**: recognition may take 10–90 s (script timeout is 120 s). To use a faster model, set `VISION_MODEL`.
- The script auto-extracts the final answer from the thinking output (when `content` is empty, it takes the conclusion in `reasoning_content`); default output is clean text, `--json` outputs the raw API response.
- `config` writes to **system environment variables**; the script re-reads system config, so it works in the current session immediately — but a **new terminal** is where each shell actually loads the variable. Restart the terminal if another program does not see it.
- Windows writes via `winreg` directly to the registry (not setx): supports special characters like `& ^ %` and has no 1024-char limit.
- `config` never prints the plaintext key, so it is safe to copy for the user.
- 401 = bad/expired key; 404 = wrong model or API URL; 429 = rate limited.
