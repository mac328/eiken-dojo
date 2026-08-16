#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
おかしな 発音の 語を、いろいろな 声で 作りくらべます。

つかいかた:
    python tools/try_voices.py cause object refuse
    python tools/try_voices.py --file words.txt      ← 1行1語の ファイルから

なぜ:
    誤読は 声(モデル)ごとに ちがうことが あります。
    べつの 声なら 正しく 読める なら、
    make_audio.py の VOICE を かえるだけで まとめて 直る かもしれません。

    audio_voices/<単語>/ に 声ごとの mp3 が 出るので、
    同じ 単語の フォルダを 開いて 聴きくらべてください。

つながらない ときは:
    edge-tts の サーバーは 短時間に たくさん つなぐと 接続を 切ります
    (WinError 10054)。このスクリプトは 1本ずつ 間を あけて、
    しっぱいしたら 5回まで やりなおします。
    すでに できている mp3 は とばすので、
    エラーが 出ても もう一度 実行すれば 足りない分だけ 作ります。
"""
import asyncio
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "audio_voices")
RATE = "-10%"
RETRY = 5          # つながらない ときの やりなおし回数
WAIT = 1.2         # 1本ごとに あける 秒数(まとめて つなぐと 切られます)

VOICES = [
    "en-US-JennyNeural",     # いま つかっている 声
    "en-US-AriaNeural",
    "en-US-MichelleNeural",
    "en-US-AnaNeural",
    "en-US-GuyNeural",
    "en-GB-SoniaNeural",
    "en-AU-NatashaNeural",
]

# --short を つけたときに つかう 声(いま の 声 と 本命 だけ)
# たくさんの 語を くらべる ときは こちらが 速く、接続も 切れにくいです。
VOICES_SHORT = [
    "en-US-JennyNeural",     # いま の 声(比較用)
    "en-US-MichelleNeural",  # 本命
]

try:
    import edge_tts
except ImportError:
    print("\n[エラー] edge-tts が 入っていません:  pip install edge-tts\n")
    sys.exit(1)


async def main():
    args = sys.argv[1:]
    voices = VOICES
    if "--short" in args:
        voices = VOICES_SHORT
        args.remove("--short")
    if "--file" in args:
        p = args[args.index("--file") + 1]
        with open(p, encoding="utf-8") as f:
            words = [l.strip() for l in f if l.strip() and not l.startswith("#")]
    else:
        words = args
    if not words:
        print(__doc__)
        sys.exit(1)

    os.makedirs(OUT, exist_ok=True)
    print("\n  語: %d 個 / 声: %d 種類\n" % (len(words), len(voices)))
    for w in words:
        d = os.path.join(OUT, "".join(c if c.isalnum() else "_" for c in w)[:40])
        os.makedirs(d, exist_ok=True)
        print("  " + w)
        for v in voices:
            path = os.path.join(d, v + ".mp3")
            if os.path.exists(path) and os.path.getsize(path) > 500:
                print("     %-24s -> すでにあります" % v)
                continue
            ok = False
            for attempt in range(RETRY):
                try:
                    tts = edge_tts.Communicate(w, v, rate=RATE, pitch="+0Hz")
                    await tts.save(path)
                    if os.path.getsize(path) < 500:
                        raise RuntimeError("ファイルが小さすぎます")
                    print("     %-24s -> %s" % (v, os.path.basename(path)))
                    ok = True
                    break
                except Exception as e:
                    if os.path.exists(path):
                        try:
                            os.remove(path)
                        except OSError:
                            pass
                    if attempt == RETRY - 1:
                        print("     %-24s -> %d回ためして だめでした (%s)"
                              % (v, RETRY, str(e)[:60]))
                    else:
                        await asyncio.sleep(WAIT * (attempt + 1))
            # サーバーに 続けて つなぐと 切られやすいので すこし 待ちます
            await asyncio.sleep(WAIT)
    print("\n  %s の 各フォルダを 聴きくらべてください。\n" % OUT)


if __name__ == "__main__":
    if sys.platform.startswith("win"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
