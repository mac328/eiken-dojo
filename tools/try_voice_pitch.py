#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文と 声と ピッチの 組みあわせごとに 作りくらべます。

つかいかた:
    python tools/try_voice_pitch.py

なぜ:
    try_voices.py は 声だけを かえくらべる 道具ですが、
    こちらは 「声 と ピッチの 組みあわせ」を くらべます。
    子どもの声(K)が おかしく 聞こえる とき、
    原因が 声そのものか、ピッチを 下げていることか を 切りわけられます。

出しさき:
    audio_test/ に mp3 が 出ます。
    ファイル名に 番号・声・ピッチが 入るので、順に 聴きくらべてください。
    本番の audio/ には いっさい さわりません。

つながらない ときは:
    edge-tts の サーバーは 短時間に たくさん つなぐと 接続を 切ります
    (WinError 10054)。1本ずつ 間を あけて、しっぱいしたら 5回まで
    やりなおします。すでに できている mp3 は とばすので、
    エラーが 出ても もう一度 実行すれば 足りない分だけ 作ります。
"""
import asyncio
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "audio_test")

RATE = "-10%"      # make_audio.py と そろえています
RETRY = 5          # つながらない ときの やりなおし回数
WAIT = 1.2         # 1本ごとに あける 秒数

BIKE = "Dad, my bike broke down again."
HOME = "I'm home, Mom."
SMELL = "Something smells good. What are you making?"

# (番号, 文, 声, ピッチ, なんのための 比較か)
JOBS = [
    (1, BIKE, "en-US-AnaNeural",      "-20Hz", "もとの設定(比較用)"),
    (2, BIKE, "en-US-AnaNeural",      "+0Hz",  "ピッチ変更が原因かの切りわけ"),
    (3, BIKE, "en-GB-MaisieNeural",   "+0Hz",  "イギリスの子どもの声"),
    (4, BIKE, "en-US-MichelleNeural", "+25Hz", "大人の声を高くして子ども風に"),
    (5, BIKE, "en-US-MichelleNeural", "+18Hz", "同上・上げ幅をひかえめに"),
    (6, BIKE, "en-US-MichelleNeural", "+15Hz", "本番の設定"),
    (7, HOME, "en-US-MichelleNeural", "+15Hz", "本番の設定・みじかい文"),

    # 落ちついて 聞こえる のを なおしたい。
    # Michelle は タグが News/Novel(ニュース・朗読向け)なので、
    # Conversation(会話向け)で 表情の ある 声を くらべます。
    (8,  SMELL, "en-US-MichelleNeural",       "+15Hz", "いまの本番(比較の基準)"),
    (9,  SMELL, "en-US-EmmaNeural",           "+15Hz", "Emma 明るい・会話向き"),
    (10, SMELL, "en-US-AvaNeural",            "+15Hz", "Ava 表情ゆたか・会話向き"),
    (11, SMELL, "en-US-EmmaMultilingualNeural", "+15Hz", "Emma 多言語版"),
    (12, SMELL, "en-US-AvaMultilingualNeural",  "+15Hz", "Ava 多言語版"),
    (13, SMELL, "en-US-EmmaNeural",           "+0Hz",  "Emma 素の声(ピッチなし)"),
    (14, SMELL, "en-US-AvaNeural",            "+0Hz",  "Ava 素の声(ピッチなし)"),

    # Emma に きめて、あげ幅を さがします。
    # +15Hz では まだ 大人の 印象が のこる ため。
    (15, SMELL, "en-US-EmmaNeural", "+18Hz", "Emma あげ幅さがし"),
    (16, SMELL, "en-US-EmmaNeural", "+20Hz", "Emma あげ幅さがし"),
    (17, SMELL, "en-US-EmmaNeural", "+25Hz", "Emma あげ幅さがし"),
    (18, SMELL, "en-US-EmmaNeural", "+28Hz", "Emma あげ幅さがし"),
]


def slug(text):
    """ファイル名用に 文の あたまを 3語だけ とりだします。"""
    words = []
    for w in text.split()[:3]:
        w = "".join(c for c in w if c.isalnum())
        if w:
            words.append(w)
    return "_".join(words)

try:
    import edge_tts
except ImportError:
    print("\n[エラー] edge-tts が 入っていません:  pip install edge-tts\n")
    sys.exit(1)


async def main():
    os.makedirs(OUT, exist_ok=True)
    print("\n  rate: %s / %d パターン\n" % (RATE, len(JOBS)))

    failed = []
    for num, text, voice, pitch, note in JOBS:
        name = "%d_%s_%s_pitch%s.mp3" % (num, slug(text), voice, pitch)
        path = os.path.join(OUT, name)
        if os.path.exists(path) and os.path.getsize(path) > 500:
            print("  %d. %-40s -> すでにあります" % (num, note))
            continue

        for attempt in range(RETRY):
            try:
                tts = edge_tts.Communicate(text, voice, rate=RATE, pitch=pitch)
                await tts.save(path)
                if os.path.getsize(path) < 500:
                    raise RuntimeError("ファイルが小さすぎます")
                print("  %d. %-40s -> %s" % (num, note, name))
                break
            except Exception as e:
                if os.path.exists(path):
                    try:
                        os.remove(path)
                    except OSError:
                        pass
                if attempt == RETRY - 1:
                    print("  %d. %-40s -> %d回ためして だめでした\n     (%s)"
                          % (num, note, RETRY, str(e)[:80]))
                    failed.append(num)
                else:
                    await asyncio.sleep(WAIT * (attempt + 1))
        # サーバーに 続けて つなぐと 切られやすいので すこし 待ちます
        await asyncio.sleep(WAIT)

    print("\n  %s を 順に 聴きくらべてください。" % OUT)
    if failed:
        print("  ※ %d本 できませんでした。もう一度 実行すると 足りない分だけ 作ります。"
              % len(failed))
    print()


if __name__ == "__main__":
    if sys.platform.startswith("win"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
