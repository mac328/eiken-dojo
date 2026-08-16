#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
読み方が おかしい 単語の 「言いかえ候補」を 聴きくらべる ための 道具です。

つかいかた:
    python tools/try_pron.py cause
    python tools/try_pron.py cause kawz cawz kauze        ← 候補を 自分で 指定
    python tools/try_pron.py object --voice en-US-AriaNeural   ← 声を かえて ためす

・audio_test/ フォルダに 候補ごとの mp3 を つくります
・ファイル名の 先頭に 番号が つくので、順に 聴いて いちばん よいものを えらびます
・きまったら tools/make_audio.py の SAY_AS に 1行 足して、
  その語の 本番mp3 を 消してから make_audio.py を 実行してください
・audio_test/ は 本番の audio/ とは 別なので、消しても 大丈夫です
"""
import asyncio
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "audio_test")

RATE = "-10%"                  # make_audio.py と そろえています
DEFAULT_VOICE = "en-US-JennyNeural"

# 候補を 指定しなかった ときに 自動で ためす パターン
def auto_candidates(word):
    c = [
        word,                        # そのまま(いまの音)
        word + ".",                  # 文の おわりとして 読ませる
        word.capitalize() + ".",     # 大文字はじまり + ピリオド
        "The word is " + word + ".", # 文の中に 入れる(前置きごと 読まれます)
    ]
    # よくある つづりかえ
    swap = {
        "au": "aw", "ause": "awz", "ose": "oze", "use": "yooz",
        "ough": "uff", "ea": "ee",
    }
    for a, b in swap.items():
        if a in word:
            c.append(word.replace(a, b))
    # 重複を のぞいて 順番を たもつ
    seen, out = set(), []
    for x in c:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


try:
    import edge_tts
except ImportError:
    print("\n[エラー] edge-tts が 入っていません:  pip install edge-tts\n")
    sys.exit(1)


def safe(s):
    return "".join(ch if ch.isalnum() else "_" for ch in s)[:40]


async def main():
    args = [a for a in sys.argv[1:]]
    voice = DEFAULT_VOICE
    ssml_ipa = None
    if "--ipa" in args:
        i = args.index("--ipa")
        ssml_ipa = args[i + 1]
        del args[i:i + 2]
    if "--voice" in args:
        i = args.index("--voice")
        voice = args[i + 1]
        del args[i:i + 2]
    if not args:
        print(__doc__)
        sys.exit(1)

    word = args[0]
    cands = args[1:] if len(args) > 1 else auto_candidates(word)

    # --ipa をつけたときは SSML の phoneme タグが 効くか ためします
    if ssml_ipa:
        cands = [
            '<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" '
            'xml:lang="en-US"><phoneme alphabet="ipa" ph="%s">%s</phoneme></speak>'
            % (ssml_ipa, word),
            '<phoneme alphabet="ipa" ph="%s">%s</phoneme>' % (ssml_ipa, word),
        ]
        print("\n  [SSML試験] タグが そのまま 読み上げられたら 非対応です。")
        print("             ただしく %s と 読まれたら 対応しています。\n" % ssml_ipa)

    os.makedirs(OUT, exist_ok=True)
    print("\n  語     : %s" % word)
    print("  声     : %s" % voice)
    print("  はやさ : %s" % RATE)
    print("  ほぞん先: %s\n" % OUT)

    for n, text in enumerate(cands, 1):
        path = os.path.join(OUT, "%02d_%s_%s.mp3" % (n, safe(word), safe(text)))
        try:
            tts = edge_tts.Communicate(text, voice, rate=RATE, pitch="+0Hz")
            await tts.save(path)
            print("  %2d) %-28s -> %s" % (n, repr(text), os.path.basename(path)))
        except Exception as e:
            print("  %2d) %-28s -> しっぱい (%s)" % (n, repr(text), e))

    print("\n  audio_test/ の mp3 を 番号順に 聴いて、")
    print("  いちばん 正しく 聞こえた 候補の テキストを")
    print("  tools/make_audio.py の SAY_AS に 書いてください。")
    print("  例:  SAY_AS = { \"%s\": \"<えらんだテキスト>\" }\n" % word)


if __name__ == "__main__":
    if sys.platform.startswith("win"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
