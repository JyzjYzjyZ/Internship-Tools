#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
vision-bridge.py — Give vision capability to non-vision LLMs (e.g. DeepSeek).

How it works: read local images -> base64 -> send to an external vision model
(OpenAI Chat Completions protocol, default agnes-2.5-flash) -> return text.
The API key is only read from environment variables, never stored in project files.

Three modes:
  1. Recognize (default)
       python vision-bridge.py <image-path> [more-images] [prompt] [options]
       python vision-bridge.py --url <image-url> [prompt] [options]
       python vision-bridge.py --from-transcript [prompt] [options]
     --from-transcript: no path needed — auto-pull the most recent image pasted
       in the Claude Code chat from the session transcript (.jsonl). Also
       auto-triggered when the prompt carries an image tag like `[Image: ...]`,
       `[Unsupported Image]`, or `Saved attachments:` but no file path is given.
  2. Configure (persist env vars across platforms; just replace the placeholder)
       python vision-bridge.py config "<your vision API key>"
       python vision-bridge.py config --region global|china "<your key>"
  3. Check (is the vision model API configured?)
       python vision-bridge.py check

Environment variables:
  VISION_API_KEY   vision model API key (required unless embedded by install.py)
                   (Key priority: skill config.json -> this env var -> builtin.)
  VISION_BASE_URL  OpenAI-compatible API base URL.
                   Regional auto-select when unset: api.agnes-ai.cn (China)
                   vs apihub.agnes-ai.com (global).
  VISION_MODEL     vision model name, default agnes-2.5-flash
  VISION_LANG      force language: zh or en (auto-detect when unset)

Deps: Python 3.9+ standard library only (urllib / winreg / ctypes / pathlib / re).

Bilingual: UI text auto-switches between Chinese and English based on the system
language (or VISION_LANG). Output format of `check` stays parseable for agents.
"""

import sys
import os
import re
import json
import time
import socket
import base64
import tempfile
import argparse
import urllib.request
import urllib.error
from pathlib import Path

# Force UTF-8 stdin/stdout (cross-platform).
# Windows Chinese locales default to GBK for console I/O and Python 3.9 does not
# enable UTF-8 mode by default, which conflicts with UTF-8 Chinese output.
# Rebinding at the interpreter level avoids relying on PYTHONIOENCODING.
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        sys.stdin.reconfigure(encoding="utf-8", errors="replace")
    except (ValueError, OSError):
        pass

# winreg / ctypes only on Windows; null on POSIX to avoid import errors
if sys.platform == "win32":
    import winreg
    import ctypes
    from ctypes import wintypes
else:
    winreg = None
    ctypes = None

BASE_URL_GLOBAL = "https://api.moonshot.cn/v1"  # Kimi API
BASE_URL_CHINA = "https://api.moonshot.cn/v1"       # Kimi API (same endpoint)
DEFAULT_MODEL = "kimi-k3"
TIMEOUT_SECONDS = 120  # thinking model: responses measured at 60-90s
MAX_RETRIES = 3
MAX_IMAGE_BYTES = 10 * 1024 * 1024  # 10MB warning threshold

MIME_MAP = {
    "jpg": "jpeg", "jpeg": "jpeg", "png": "png", "gif": "gif",
    "webp": "webp", "bmp": "bmp", "svg": "svg+xml", "ico": "x-icon",
}
IMAGE_EXTS = {"." + k for k in MIME_MAP}

BLOCK_MARKER = "# Added by vision-bridge"

# ---------------------------------------------------------------------------
# Language detection
# ---------------------------------------------------------------------------

def _win_is_chinese_locale():
    """Detect Chinese UI language on Windows via GetUserDefaultUILanguage."""
    if sys.platform != "win32":
        return False
    try:
        lang_id = ctypes.windll.kernel32.GetUserDefaultUILanguage()
        primary = lang_id & 0x3FF  # LANG_CHINESE == 0x04
        return primary == 0x04
    except Exception:
        return False


def _is_chinese_env():
    """Auto-detect whether the environment prefers Chinese. VISION_LANG overrides."""
    lang = os.environ.get("VISION_LANG")
    if lang:
        return lang.strip().lower().startswith("zh")
    for k in ("LC_ALL", "LANG", "LC_MESSAGES"):
        v = (os.environ.get(k) or "").strip().lower()
        if v.startswith("zh"):
            return True
    return _win_is_chinese_locale()


LANG_ZH = _is_chinese_env()


def _t(zh, en):
    """Bilingual helper: returns the Chinese or English string based on LANG_ZH."""
    return zh if LANG_ZH else en


def default_base_url():
    """Regional-aware base URL. VISION_BASE_URL wins; else .cn for Chinese env, .com otherwise."""
    if os.environ.get("VISION_BASE_URL"):
        return os.environ["VISION_BASE_URL"]
    return BASE_URL_CHINA if LANG_ZH else BASE_URL_GLOBAL

# ---------------------------------------------------------------------------
# Environment variable reading (current process env -> system config)
# ---------------------------------------------------------------------------

def env_file_path():
    """Return the rc file to write, based on the current shell."""
    if sys.platform == "win32":
        return None
    shell = os.environ.get("SHELL", "")
    if shell.rstrip("/").endswith("fish"):
        return Path.home() / ".config/fish/config.fish"
    if sys.platform == "darwin" or "zsh" in shell:
        return Path.home() / ".zshrc"
    return Path.home() / ".bashrc"


def is_fish_env():
    return env_file_path() is not None and env_file_path().name == "config.fish"


# Compatible with: double quotes / single quotes / no quotes / spaces around '=' / trailing comment
def _key_re(name):
    return re.compile(
        rf'^[ \t]*export[ \t]+{re.escape(name)}[ \t]*=[ \t]*'
        rf'(?:"([^"]*)"|\'([^\']*)\'|([^\s#]+))'
        rf'(?:[ \t]*#.*)?[ \t]*$',
        re.MULTILINE,
    )


def _fish_key_re(name):
    return re.compile(
        rf'^[ \t]*set[ \t]+-gx[ \t]+{re.escape(name)}[ \t]+'
        rf'(?:"([^"]*)"|\'([^\']*)\'|([^\s#]+))'
        rf'(?:[ \t]*#.*)?[ \t]*$',
        re.MULTILINE,
    )


def read_var_from_rc(name):
    rc = env_file_path()
    if rc is None or not rc.exists():
        return None
    text = rc.read_text(encoding="utf-8", errors="replace")
    regex = _fish_key_re(name) if rc.name == "config.fish" else _key_re(name)
    m = regex.search(text)
    if not m:
        return None
    return m.group(1) or m.group(2) or m.group(3)


def read_var_winreg(name):
    if sys.platform != "win32":
        return None
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_READ) as hkey:
            value, _typ = winreg.QueryValueEx(hkey, name)
            return value if isinstance(value, str) and value else None
    except OSError:
        return None


def get_env_var(name):
    """Read a persisted env var: process env first, then system config.
    This makes `config` usable in the current session immediately."""
    if os.environ.get(name):
        return os.environ[name]
    if sys.platform == "win32":
        return read_var_winreg(name)
    return read_var_from_rc(name)


def skill_config_path():
    """config.json in the skill root (written by install.py at install time)."""
    return Path(__file__).resolve().parent.parent / "config.json"


def get_api_key():
    """Return the vision API key. Priority: skill config.json > env var > builtin."""
    try:
        cfg = json.loads(skill_config_path().read_text(encoding="utf-8"))
        key = (cfg.get("api_key") or "").strip()
        if key:
            return key
    except (OSError, ValueError):
        pass
    key = get_env_var("VISION_API_KEY")
    if key:
        return key
    # Fallback: hardcoded Kimi API key
    return "{your key}"


def is_configured():
    return get_api_key() is not None

# ---------------------------------------------------------------------------
# Environment variable writing (persist across platforms)
# ---------------------------------------------------------------------------

def broadcast_environment_change():
    """Broadcast WM_SETTINGCHANGE so explorer notices the variable change. Best-effort."""
    if sys.platform != "win32":
        return
    try:
        user32 = ctypes.windll.user32
        # argtypes must be declared: lParam is LPCWSTR so a Python str converts to
        # a NUL-terminated UTF-16 pointer automatically.
        user32.SendMessageTimeoutW.argtypes = [
            wintypes.HWND, ctypes.c_uint, wintypes.WPARAM,
            wintypes.LPCWSTR, ctypes.c_uint, ctypes.c_uint,
            ctypes.POINTER(ctypes.c_ulong),
        ]
        user32.SendMessageTimeoutW.restype = ctypes.c_ulong
        user32.SendMessageTimeoutW(
            0xFFFF, 0x001A, 0, "Environment", 0x0002, 5000,
            ctypes.byref(ctypes.c_ulong()),
        )
    except Exception:
        pass  # failure to broadcast does not affect the write result


def set_env_var_winreg(name, value):
    """Write directly to HKCU\\Environment, bypassing cmd/setx:
    no 1024 truncation, no shell character interpretation."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_SET_VALUE) as hkey:
            # REG_SZ not REG_EXPAND_SZ: the latter expands %VAR% in new processes.
            winreg.SetValueEx(hkey, name, 0, winreg.REG_SZ, value)
    except OSError as e:
        print(f"[{_t('错误', 'ERROR')}] {_t('写入注册表失败', 'failed to write registry')}: {e}", file=sys.stderr)
        print(_t("   请手动在你的终端配置文件中设置 %s。" % name,
                 f"   Please set {name} manually in your terminal config file."), file=sys.stderr)
        return 1
    broadcast_environment_change()
    return 0


# Idempotent block handling: remove the marker comment + (adjacent) export/set
# line as one block. Deliberately no DOTALL: blocks are line-structured, so we
# anchor with MULTILINE at line start and constrain each line with [^\n]*.
def _block_re(name):
    return re.compile(
        rf'^[ \t]*#\s*Added by vision-bridge\b[^\n]*\r?\n'
        rf'(?:[ \t]*export[ \t]+{re.escape(name)}[ \t]*=[^\n]*\r?\n)?',
        re.MULTILINE,
    )


def _fish_block_re(name):
    return re.compile(
        rf'^[ \t]*#\s*Added by vision-bridge\b[^\n]*\r?\n'
        rf'(?:[ \t]*set[ \t]+-gx[ \t]+{re.escape(name)}[ \t]*[^\n]*\r?\n)?',
        re.MULTILINE,
    )


def _export_re(name):
    return re.compile(
        rf'^[ \t]*export[ \t]+{re.escape(name)}[ \t]*=[^\n]*\r?\n?',
        re.MULTILINE,
    )


def _fish_export_re(name):
    return re.compile(
        rf'^[ \t]*set[ \t]+-gx[ \t]+{re.escape(name)}[ \t]+[^\n]*\r?\n?',
        re.MULTILINE,
    )


def set_env_var_rc(name, value):
    """Idempotent rc-file write: after any number of `config` runs the file holds
    exactly one block and one line per variable."""
    rc = env_file_path()
    if rc is None:
        return 1
    fish = is_fish_env()
    if fish:
        new_line = f'set -gx {name} "{value}"'
        block_re, export_re = _fish_block_re(name), _fish_export_re(name)
    else:
        new_line = f'export {name}="{value}"'
        block_re, export_re = _block_re(name), _export_re(name)

    try:
        rc.parent.mkdir(parents=True, exist_ok=True)
        content = rc.read_text(encoding="utf-8", errors="replace") if rc.exists() else ""

        # ① delete all old blocks (marker + adjacent line)
        content = block_re.sub("", content)

        # ② absorb bare lines: first one carries the new value and gets the marker, others removed
        state = {"n": 0}
        def _repl(m):
            state["n"] += 1
            if state["n"] == 1:
                return f"{BLOCK_MARKER}\n{new_line}\n"
            return ""
        content = export_re.sub(_repl, content)

        # ③ only append a new block if there was no existing line at all
        if state["n"] == 0:
            content = content.rstrip("\n")
            if content:
                content += "\n"
            content += f"\n{BLOCK_MARKER}\n{new_line}\n"

        content = re.sub(r"\n{3,}", "\n\n", content)

        # Path.write_text(newline=...) is 3.10+; use open()'s newline instead.
        with open(rc, "w", encoding="utf-8", newline="\n") as f:
            f.write(content)
    except OSError as e:
        print(f"[{_t('错误', 'ERROR')}] {_t('写入', 'failed to write')} {rc}: {e}", file=sys.stderr)
        print(_t("   请手动在你的 shell 配置文件中设置 %s。" % name,
                 f"   Please set {name} manually in your shell config file."), file=sys.stderr)
        return 1
    return 0


def _validate_key(api_key):
    api_key = (api_key or "").strip()
    if not api_key:
        print(f"[{_t('错误', 'ERROR')}] {_t('用法', 'Usage')}: python vision-bridge.py config \"{_t('你的视觉模型API', 'your-vision-api-key')}\"", file=sys.stderr)
        print(_t("   请把双引号里的占位符替换成你申请的 API key。",
                 "   Replace the placeholder inside the quotes with your API key."), file=sys.stderr)
        return None
    if "\n" in api_key or "\r" in api_key:
        print(f"[{_t('错误', 'ERROR')}] {_t('API key 不能包含换行。', 'API key must not contain newlines.')}", file=sys.stderr)
        return None
    return api_key


def write_config(api_key, region=None):
    """Persist VISION_API_KEY (and VISION_BASE_URL if --region given) across platforms."""
    api_key = _validate_key(api_key)
    if api_key is None:
        return 1

    results = []
    if sys.platform == "win32":
        rc = set_env_var_winreg("VISION_API_KEY", api_key)
        results.append(rc)
        base_saved = None
        if region:
            base_saved = set_env_var_winreg("VISION_BASE_URL", BASE_URL_CHINA if region == "china" else BASE_URL_GLOBAL)
            results.append(base_saved)
        _print_config_result(rc, "HKCU\\Environment")
        if base_saved is not None and base_saved == 0:
            _print_base_url_saved(region)
    else:
        rc = set_env_var_rc("VISION_API_KEY", api_key)
        results.append(rc)
        base_saved = None
        if region:
            base_saved = set_env_var_rc("VISION_BASE_URL", BASE_URL_CHINA if region == "china" else BASE_URL_GLOBAL)
            results.append(base_saved)
        _print_config_result(rc, str(env_file_path()))
        if base_saved is not None and base_saved == 0:
            _print_base_url_saved(region)

    if all(r == 0 for r in results):
        return 0
    return 1


def _print_config_result(rc, target):
    if rc == 0:
        print(f"[OK] {_t('已写入 VISION_API_KEY（永久生效，已写入', 'VISION_API_KEY saved (permanent, written to')} {target}）。" if LANG_ZH else f"[OK] VISION_API_KEY saved (permanent, written to {target}).")
        print(_t("   请「重启终端」后再运行识图命令（当前会话环境变量尚未更新）。",
                 "   Restart the terminal before recognizing images (current session env is not updated)."))
        print(_t("   验证方式", "   Verify with") + f": python vision-bridge.py check")
    else:
        print(f"[{_t('错误', 'ERROR')}] {_t('配置未完全成功，请检查上面的错误。', 'Configuration incomplete; check the error above.')}", file=sys.stderr)


def _print_base_url_saved(region):
    url = BASE_URL_CHINA if region == "china" else BASE_URL_GLOBAL
    print(f"[OK] {_t('已写入 VISION_BASE_URL', 'VISION_BASE_URL saved')} = {url}")


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def build_parser():
    p = argparse.ArgumentParser(
        prog="vision-bridge.py",
        description=_t("为无视觉模型提供识图能力（OpenAI 兼容协议）",
                       "Give vision capability to non-vision LLMs (OpenAI-compatible)"),
    )
    p.add_argument("tokens", nargs="*",
                   help=_t("位置参数：前若干张图片路径，剩余拼成提示词",
                           "positional: leading items are image paths, the rest form the prompt"))
    p.add_argument("--url", action="append", default=[], metavar="URL",
                   help=_t("网络图片链接，可多次指定", "image URL; may be repeated"))
    p.add_argument("--from-transcript", action="store_true",
                   help=_t("从 Claude Code 会话记录(.jsonl)自动提取最近粘贴的图片（无需提供路径）",
                           "auto-pull the most recent pasted image from the Claude Code transcript (.jsonl); no path needed"))
    p.add_argument("--model", default=os.environ.get("VISION_MODEL") or DEFAULT_MODEL,
                   help=_t(f"视觉模型名（默认 {DEFAULT_MODEL}）", f"vision model (default {DEFAULT_MODEL})"))
    p.add_argument("--max-tokens", type=int, default=2048,
                   help=_t("最大输出 token 数（默认 2048，给思考+答案留足空间）",
                           "max output tokens (default 2048, room for thinking + answer)"))
    p.add_argument("--temperature", type=float, default=None,
                   help=_t("采样温度 0~2（默认跟随模型）", "sampling temperature 0-2 (default: model default)"))
    p.add_argument("--json", action="store_true",
                   help=_t("输出 API 返回的原始 JSON 响应体", "output the raw JSON response body"))
    return p


def classify_tokens(tokens):
    """Leading items are image paths (file exists or has an image extension); the rest is the prompt."""
    images, words = [], []
    for t in tokens:
        p = Path(t)
        if p.exists() or p.suffix.lower() in IMAGE_EXTS:
            images.append(t)
        else:
            words.append(t)
    return images, " ".join(words)

# ---------------------------------------------------------------------------
# Image -> data URL
# ---------------------------------------------------------------------------

def to_data_url(path_str):
    p = Path(path_str).resolve()
    if not p.exists():
        raise ValueError(_t(f"文件不存在: {p}", f"File not found: {p}"))
    size = p.stat().st_size
    if size == 0:
        raise ValueError(_t(f"文件为空: {p}", f"File is empty: {p}"))
    if size > MAX_IMAGE_BYTES:
        print(_t(f"[警告] 图片 {p.name} 超过 10MB，部分 API 可能拒绝",
                 f"[WARN] image {p.name} exceeds 10MB; some APIs may reject it"), file=sys.stderr)
    mime = MIME_MAP.get(p.suffix.lower().lstrip("."), "jpeg")
    b64 = base64.b64encode(p.read_bytes()).decode("ascii")
    return f"data:image/{mime};base64,{b64}"

# ---------------------------------------------------------------------------
# Claude Code transcript extraction (pasted images from the chat UI)
# ---------------------------------------------------------------------------
#
# In the Claude Code VSCode extension, an image pasted into the chat input gets
# written to a temp file that is held open (exclusive lock -> PermissionError)
# and the backend model may not support image blocks (rendered as
# `[Unsupported Image]`). However, the image's base64 data is always persisted
# in the session transcript JSONL under ~/.claude/projects/**/*.jsonl as
# {type:"image", source:{type:"base64", media_type, data}}. So when the request
# carries an image tag (e.g. `[Image: original 2271x1358 ...]`, `[Unsupported
# Image]`, `Saved attachments:`) but no readable file path, we pull it from
# there instead of asking the user to save/point to a file.

IMAGE_MARKER_KEYWORDS = (
    "[image", "[image:", "unsupported image", "saved attachments",
)


def _has_image_marker(text):
    """Does the prompt carry a pasted-image tag from the chat UI?"""
    low = (text or "").lower()
    return any(k in low for k in IMAGE_MARKER_KEYWORDS)


def transcript_paths():
    return sorted((Path.home() / ".claude" / "projects").glob("**/*.jsonl"))


def extract_latest_user_image():
    """Return (media_type, base64_data, timestamp) of the newest USER message
    that carries an image block, scanning all transcripts; or None."""
    best = None
    for path in transcript_paths():
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    try:
                        o = json.loads(line)
                    except Exception:
                        continue
                    if o.get("type") != "user":
                        continue
                    content = (o.get("message") or {}).get("content")
                    if not isinstance(content, list):
                        continue
                    for blk in content:
                        if isinstance(blk, dict) and blk.get("type") == "image":
                            src = blk.get("source") or {}
                            data = src.get("data") or ""
                            if data:
                                ts = o.get("timestamp") or ""
                                if best is None or str(ts) > str(best[2]):
                                    best = (src.get("media_type", ""), data, ts)
        except OSError:
            continue
    return best


def save_extracted_image(media_type, base64_data):
    ext = ".jpg" if "jpeg" in media_type else (".png" if "png" in media_type else ".img")
    out = Path(tempfile.gettempdir()) / ("latest_pasted_image" + ext)
    out.write_bytes(base64.b64decode(base64_data))
    return str(out)

# ---------------------------------------------------------------------------
# API request (timeout + exponential backoff retry + error classification)
# ---------------------------------------------------------------------------

def classify_error(status, body):
    detail = body[:200]
    try:
        j = json.loads(body)
        detail = (j.get("error") or {}).get("message") or j.get("message") or detail
    except (ValueError, AttributeError):
        pass
    if status == 401:
        return _t("VISION_API_KEY 无效或已过期。请检查 key，或用 `python vision-bridge.py config \"你的视觉模型API\"` 重新配置。",
                  "VISION_API_KEY is invalid or expired. Check the key, or reconfigure with `python vision-bridge.py config \"your-vision-api-key\"`.")
    if status == 404:
        return _t(f"模型不存在或 API 地址有误（{status}）: {detail}\n   检查 VISION_MODEL 与 VISION_BASE_URL 是否正确。",
                  f"Model not found or wrong API URL ({status}): {detail}\n   Check VISION_MODEL and VISION_BASE_URL.")
    if status == 429:
        return _t(f"请求过于频繁或配额用尽（{status}）: {detail}\n   请稍后重试，或检查 API 配额。",
                  f"Rate limited or quota exhausted ({status}): {detail}\n   Retry later, or check your quota.")
    if status == 400:
        return _t(f"请求参数/图片格式有问题（{status}）: {detail}\n   请检查图片格式与大小。",
                  f"Invalid request or image format ({status}): {detail}\n   Check the image format and size.")
    return _t(f"API 错误 {status}: {detail}", f"API error {status}: {detail}")


def request_once(payload, base_url, api_key):
    url = base_url.rstrip("/") + "/chat/completions"
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST", headers={
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Content-Length": str(len(body)),
    })
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        # HTTPError is a URLError subclass: turn 4xx/5xx into (status, body) so
        # the retry loop only ever sees pure network URLErrors.
        return e.code, e.read().decode("utf-8", "replace")


def request_with_retry(payload, base_url, api_key):
    last_error = None
    for attempt in range(MAX_RETRIES + 1):  # 0..3
        if attempt > 0:
            time.sleep(1.0 * (2 ** (attempt - 1)))  # 1s, 2s, 4s
        try:
            status, body = request_once(payload, base_url, api_key)
        except urllib.error.URLError as e:
            reason = e.reason
            if isinstance(reason, (socket.timeout, TimeoutError)):
                last_error = _t(f"请求超时（{TIMEOUT_SECONDS}s）", f"Request timed out ({TIMEOUT_SECONDS}s)")
            else:
                last_error = _t(f"网络请求失败: {reason}", f"Network request failed: {reason}")
            if attempt == MAX_RETRIES:
                return {"error": last_error}
            continue
        if status == 429 or status >= 500:
            last_error = classify_error(status, body)
            if attempt == MAX_RETRIES:
                return {"error": last_error}
            continue
        if status >= 400:
            return {"error": classify_error(status, body)}
        # 2xx: parse the result
        try:
            j = json.loads(body)
            message = (j.get("choices") or [{}])[0].get("message", {}) or {}
            content = message.get("content") or ""
        except (ValueError, AttributeError, IndexError):
            message, content = {}, ""
        # agnes-2.5-flash is a thinking model: the answer may live only in
        # reasoning_content while content is empty (finish_reason=length).
        # Extract the final answer near a "final answer" marker when that happens.
        if not content.strip() and (message.get("reasoning_content") or "").strip():
            rc = message["reasoning_content"]
            for marker in ("最终回答", "Final Answer", "Final answer", "Output:", "最终答案", "Response:"):
                idx = rc.rfind(marker)
                if idx != -1:
                    content = rc[idx + len(marker):].strip()
                    break
            if not content:
                content = rc.strip().split("\n\n")[-1].strip()
        if isinstance(content, str) and content:
            return {"content": content, "raw": body}
        return {"content": body, "raw": body}
    return {"error": last_error or _t("未知错误", "Unknown error")}

# ---------------------------------------------------------------------------
# Output & main flow
# ---------------------------------------------------------------------------

def print_config_guide():
    print("", file=sys.stderr)
    if LANG_ZH:
        print("[提示] 尚未配置视觉模型 API（VISION_API_KEY 不存在）。", file=sys.stderr)
        print("   识图需要把图片发给外部视觉模型（默认 agnes-2.5-flash），需要你提供 API key。", file=sys.stderr)
        print("", file=sys.stderr)
        print("   请用下面任一种方式完成配置（只需替换“你的视觉模型API”占位符）：", file=sys.stderr)
        print("", file=sys.stderr)
        print("   方式 A（推荐，由我代写）：直接把 API key 粘贴给我，我帮你写入环境变量。", file=sys.stderr)
        print("   方式 B（自己执行）：在终端运行下面这条命令：", file=sys.stderr)
        print("     python vision-bridge.py config \"你的视觉模型API\"", file=sys.stderr)
        print("", file=sys.stderr)
        print("   配置完成后重启终端，再重新发图片给我即可。之后不会再询问。", file=sys.stderr)
    else:
        print("[INFO] Vision API not configured yet (VISION_API_KEY missing).", file=sys.stderr)
        print("   Recognizing images requires an external vision model (default agnes-2.5-flash) and an API key.", file=sys.stderr)
        print("", file=sys.stderr)
        print("   Configure it one of two ways (just replace the placeholder):", file=sys.stderr)
        print("", file=sys.stderr)
        print("   Method A (recommended, I do it for you): paste the API key here and I will save it to the env var.", file=sys.stderr)
        print("   Method B (you run it): run this command in your terminal:", file=sys.stderr)
        print("     python vision-bridge.py config \"your-vision-api-key\"", file=sys.stderr)
        print("", file=sys.stderr)
        print("   Restart the terminal after configuring, then send me the image again. You won't be asked again.", file=sys.stderr)


def cmd_check():
    ok = is_configured()
    if ok:
        model = os.environ.get("VISION_MODEL") or DEFAULT_MODEL
        base = os.environ.get("VISION_BASE_URL") or default_base_url()
        try:
            cfg = json.loads(skill_config_path().read_text(encoding="utf-8"))
            source = "skill-config" if (cfg.get("api_key") or "").strip() else "env-or-builtin"
        except (OSError, ValueError):
            source = "env-or-builtin"
        print(f"configured=true source={source} model={model} base={base}")
    else:
        print("configured=false")
    return 0 if ok else 1


def main():
    argv = sys.argv[1:]

    # Subcommand: config (small arg surface, handled manually)
    if argv and argv[0] == "config":
        # config [--region global|china] "<key>"
        region = None
        rest = argv[1:]
        if rest and rest[0] == "--region":
            region = rest[1].lower() if len(rest) > 1 else "global"
            rest = rest[2:]
        key = rest[0] if rest else ""
        sys.exit(write_config(key, region))

    # Subcommand: check
    if argv and argv[0] == "check":
        sys.exit(cmd_check())

    # Default: recognize
    parser = build_parser()
    args = parser.parse_args(argv)
    images, prompt = classify_tokens(args.tokens)

    # Image-tag auto-extraction: if the request carries a pasted-image tag from
    # the chat UI (e.g. `[Image: ...]`, `[Unsupported Image]`, `Saved attachments:`)
    # but no file path/URL was given, pull the image straight from the Claude
    # Code transcript instead of failing. `--from-transcript` forces this.
    want_transcript = args.from_transcript or (
        not images and not args.url and _has_image_marker(" ".join(args.tokens) + " " + prompt)
    )
    if want_transcript:
        found = extract_latest_user_image()
        if found:
            media, data, _ts = found
            pulled = save_extracted_image(media, data)
            images.append(pulled)
            print(_t(f"[提示] 检测到图片标记，已从会话记录(.jsonl)提取最近粘贴的图片:\n  {pulled}",
                     f"[INFO] Image tag detected; pulled most recent pasted image from transcript (.jsonl):\n  {pulled}"),
                  file=sys.stderr)
        else:
            print(_t("[提示] 检测到图片标记，但未在任何会话记录(.jsonl)中找到图片数据。",
                     "[INFO] Image tag detected, but no image data was found in any transcript (.jsonl)."),
                  file=sys.stderr)

    if not images and not args.url:
        parser.print_help()
        sys.exit(1)

    api_key = get_api_key()
    if not api_key:
        print_config_guide()
        sys.exit(1)

    try:
        parts = [{"type": "image_url", "image_url": {"url": to_data_url(p)}} for p in images]
        parts += [{"type": "image_url", "image_url": {"url": u}} for u in args.url]
        parts.append({"type": "text", "text": prompt or _t("请详细描述这张图片的内容。",
                                                           "Please describe this image in detail.")})

        payload = {
            "model": args.model,
            "messages": [{"role": "user", "content": parts}],
            "stream": False,
            "max_tokens": args.max_tokens,
        }
        if args.temperature is not None:
            payload["temperature"] = args.temperature

        result = request_with_retry(payload, default_base_url(), api_key)
        if result.get("error"):
            print(f"[{_t('错误', 'ERROR')}] {_t('识图失败', 'Recognition failed')}: {result['error']}", file=sys.stderr)
            sys.exit(1)
        if args.json:
            print(result["raw"])
        else:
            print(result["content"])
    except Exception as e:
        print(f"[{_t('错误', 'ERROR')}] {_t('识图失败', 'Recognition failed')}: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
