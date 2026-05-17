"""
notify_runner.py
================
執行指定的 Jupyter Notebook，擷取 print 輸出，
與上次執行結果比對方向，若改變則先發警報，再發一般通知。

用法（由 GitHub Actions 呼叫）：
    python notify_runner.py <notebook_path> <strategy_id>

範例：
    python notify_runner.py Macro_US_Stock.ipynb macro_us
"""

import os
import sys
import json
import re
import subprocess
import tempfile
import textwrap
from datetime import datetime

import pytz
import requests

# ── 環境變數 ──────────────────────────────────────────────────────────────────
TELEGRAM_TOKEN   = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
STATES_FILE      = "strategy_states.json"
TW               = pytz.timezone("Asia/Taipei")

# ── 方向關鍵字（依優先順序比對）────────────────────────────────────────────
_SIGNAL_MAP = [
    # 做多
    ("做多",   "LONG"), ("多單",  "LONG"), ("買進", "LONG"),
    ("buy",    "LONG"), ("long",  "LONG"), ("看多", "LONG"),
    # 做空
    ("做空",   "SHORT"), ("空單", "SHORT"), ("賣出", "SHORT"),
    ("sell",   "SHORT"), ("short","SHORT"), ("看空", "SHORT"),
    # 觀望
    ("觀望",   "NEUTRAL"), ("等待", "NEUTRAL"), ("持平", "NEUTRAL"),
    ("neutral","NEUTRAL"), ("hold","NEUTRAL"),
]

_EMOJI = {
    "LONG":    "📈 做多",
    "SHORT":   "📉 做空",
    "NEUTRAL": "⏸ 觀望",
    "UNKNOWN": "❓ 不明",
}


# ══════════════════════════════════════════════════════════════════════════════
#  工具函式
# ══════════════════════════════════════════════════════════════════════════════

def load_states() -> dict:
    if os.path.exists(STATES_FILE):
        with open(STATES_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_states(states: dict):
    with open(STATES_FILE, "w", encoding="utf-8") as f:
        json.dump(states, f, ensure_ascii=False, indent=2)


def detect_signal(text: str) -> str:
    """在輸出文字中搜尋方向關鍵字，回傳 LONG / SHORT / NEUTRAL / UNKNOWN。"""
    lower = text.lower()
    for kw, sig in _SIGNAL_MAP:
        if kw in lower:
            return sig
    return "UNKNOWN"


def clean_script(script: str) -> str:
    """移除 nbconvert 產生的 IPython magic 與 get_ipython() 呼叫。"""
    lines = []
    for line in script.splitlines():
        stripped = line.strip()
        # 跳過 magic 指令與 In[n]: 標記
        if stripped.startswith("get_ipython()"):
            continue
        if re.match(r"^#\s*In\[", stripped):
            continue
        lines.append(line)
    return "\n".join(lines)


def run_notebook(nb_path: str) -> str:
    """
    將 notebook 轉成 .py 後執行，回傳所有 print 輸出（stdout）。
    執行失敗時拋出 RuntimeError。
    """
    if not os.path.exists(nb_path):
        raise FileNotFoundError(f"找不到 notebook：{nb_path}")

    with tempfile.TemporaryDirectory() as tmpdir:
        base = os.path.splitext(os.path.basename(nb_path))[0]
        script_path = os.path.join(tmpdir, base + ".py")

        # Step 1：轉成 .py
        conv = subprocess.run(
            ["jupyter", "nbconvert", "--to", "script", nb_path,
             "--output-dir", tmpdir],
            capture_output=True, text=True,
        )
        if conv.returncode != 0:
            raise RuntimeError(f"nbconvert 失敗：{conv.stderr[:400]}")

        # Step 2：清理 magic 指令
        with open(script_path, encoding="utf-8") as f:
            raw = f.read()
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(clean_script(raw))

        # Step 3：執行並擷取 stdout
        run = subprocess.run(
            [sys.executable, script_path],
            capture_output=True, text=True, timeout=600,
            cwd=os.path.dirname(os.path.abspath(nb_path)) or ".",
        )
        output = run.stdout.strip()

        if run.returncode != 0 and not output:
            raise RuntimeError(run.stderr[:500])

        return output


def send_telegram(text: str):
    """發送 Telegram 訊息（HTML 格式）。"""
    url  = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    resp = requests.post(url, json={
        "chat_id":    TELEGRAM_CHAT_ID,
        "text":       text,
        "parse_mode": "HTML",
    }, timeout=30)
    resp.raise_for_status()


def build_message(name: str, signal: str, output: str,
                  prev_signal: str | None, changed: bool) -> str:
    now      = datetime.now(TW).strftime("%Y/%m/%d %H:%M")
    sig_disp = _EMOJI.get(signal, "❓")

    header = [f"<b>📊 {name}</b>", f"🕐 {now}", ""]

    if changed and prev_signal:
        prev_disp = _EMOJI.get(prev_signal, "❓")
        header += [f"🔄 方向：{prev_disp} → <b>{sig_disp}</b>", ""]
    else:
        header += [f"方向：{sig_disp}", ""]

    # 輸出摘要，最多 900 字元
    summary = output if len(output) <= 900 else "…（節錄後段）\n" + output[-850:]
    body    = "<pre>" + summary + "</pre>"

    return "\n".join(header) + body


# ══════════════════════════════════════════════════════════════════════════════
#  主程式
# ══════════════════════════════════════════════════════════════════════════════

def main():
    if len(sys.argv) < 3:
        print("用法：python notify_runner.py <notebook.ipynb> <strategy_id>")
        sys.exit(1)

    nb_path     = sys.argv[1]
    strategy_id = sys.argv[2]
    name        = os.path.splitext(os.path.basename(nb_path))[0].replace("_", " ")

    print(f"▶ 執行 {nb_path} ...")

    # ── 執行 notebook ────────────────────────────────────────────────────────
    try:
        output = run_notebook(nb_path)
        print(f"   輸出長度：{len(output)} 字元")
    except Exception as exc:
        err_msg = (
            f"⚠️ <b>{name}</b> 執行失敗\n"
            f"<pre>{str(exc)[:400]}</pre>"
        )
        send_telegram(err_msg)
        print(f"✗ 執行失敗：{exc}")
        sys.exit(1)

    # ── 偵測方向 ─────────────────────────────────────────────────────────────
    signal = detect_signal(output)
    print(f"   偵測方向：{signal}")

    # ── 與上次比對 ───────────────────────────────────────────────────────────
    states      = load_states()
    prev        = states.get(strategy_id, {})
    prev_signal = prev.get("signal")
    changed     = (prev_signal is not None) and (signal != prev_signal)

    # ── 方向改變 → 先發警報 ──────────────────────────────────────────────────
    if changed:
        alert = (
            "🚨🚨🚨\n"
            f"<b>{name} 方向改變！</b>\n"
            f"{_EMOJI.get(prev_signal, '?')} → {_EMOJI.get(signal, '?')}\n"
            "🚨🚨🚨"
        )
        send_telegram(alert)
        print(f"   ⚡ 警報已發送（{prev_signal} → {signal}）")

    # ── 發一般通知 ───────────────────────────────────────────────────────────
    msg = build_message(name, signal, output, prev_signal, changed)
    send_telegram(msg)
    print("   ✅ 通知已發送")

    # ── 更新狀態 ─────────────────────────────────────────────────────────────
    states[strategy_id] = {
        "signal":     signal,
        "updated_at": datetime.now(TW).isoformat(),
    }
    save_states(states)
    print(f"✅ 完成")


if __name__ == "__main__":
    main()
