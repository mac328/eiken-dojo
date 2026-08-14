#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
少年の声を きいてくらべる ための おためしスクリプト。

つかいかた:
    python tools/try_voices.py

audio_test/ という フォルダに mp3 が いくつか できるので、
きいてみて 好きなものを えらんでください。
えらんだら make_audio.py の PITCH の 数字を 書きかえて、
もう一度  python tools/make_audio.py  を 実行します。
"""
import asyncio
import os
import sys

# ためす 組み合わせ (ファイル名のあたま, 声, ピッチ)
PATTERNS = [
    ("1_ana_sonomama",   "en-US-AnaNeural",    "+0Hz"),
    ("2_ana_m20",        "en-US-AnaNeural",    "-20Hz"),
    ("3_ana_m60",        "en-US-AnaNeural",    "-60Hz"),   # いまの 設定
    ("4_ana_m80",        "en-US-AnaNeural",    "-80Hz"),
    ("5_ana_m100",       "en-US-AnaNeural",    "-100Hz"),
    ("6_andrew_wakai",   "en-US-AndrewNeural", "+0Hz"),
    ("7_andrew_takame",  "en-US-AndrewNeural", "+20Hz"),
    ("8_guy_otona",      "en-US-GuyNeural",    "+0Hz"),
]

# ためしに 読ませる セリフ(実際に アプリで つかう 少年の せりふ)
TEXT = "I'm home, Mom. The school trip was great. We saw many old temples."

RATE = "-10%"

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "audio_test")

try:
    import edge_tts
except ImportError:
    print("\n[エラー] edge-tts が 入っていません:  pip install edge-tts\n")
    sys.exit(1)


async def one(name, voice, pitch):
    path = os.path.join(OUT, name + ".mp3")
    try:
        tts = edge_tts.Communicate(TEXT, voice, rate=RATE, pitch=pitch)
        await tts.save(path)
        print("  できました: %-20s (%s %s)" % (name + ".mp3", voice, pitch))
    except Exception as e:
        print("  しっぱい  : %-20s %s" % (name + ".mp3", e))


async def main():
    os.makedirs(OUT, exist_ok=True)
    print("\n  セリフ: %s\n" % TEXT)
    await asyncio.gather(*[one(n, v, p) for n, v, p in PATTERNS])
    print("\n  %s の中の mp3 を きいてくらべてください。\n" % OUT)
    print("  きにいった ものが きまったら:")
    print("    - Ana の どれか  → make_audio.py の PITCH[\"K\"] を その数字に")
    print("    - Andrew が よい → VOICES[\"K\"] を \"en-US-AndrewNeural\" に")
    print("  そのあと  python tools/make_audio.py  を もう一度 実行します。")
    print("  (audio_test フォルダは あとで 消して かまいません)\n")


if __name__ == "__main__":
    if sys.platform.startswith("win"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
