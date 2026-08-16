#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
話者K(子ども)の 全セリフを、ためしの 声と ピッチで audio_test/ に 作ります。

つかいかた:
    python tools/make_k_test.py

なぜ:
    声を 本番に 入れる まえに、21本を 通して 聴いて 確かめる ための ものです。
    1文だけでは 気づけない 誤読や、文末の きしみ(ジリジリした 低音)が
    どのくらい 出るかは、通して 聴かないと わかりません。

本番との ちがい:
    ありません。本番の make_audio.py から
    speak_text()(読み上げ用の 文の ととのえ)と
    trim_silence()(前後の 無音けずり)を そのまま 借りているので、
    でき上がりは 本番と 同じ 条件です。

    ★ 本番の audio/ には いっさい さわりません。
      出しさきは audio_test/K_<声>_pitch<ピッチ>/ だけです。

声を かえたい ときは:
    下の VOICE と PITCH を 書きかえて もう一度 実行してください。
    ピッチごとに べつの フォルダに 出るので、聴きくらべ できます。
"""
import asyncio
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

# ---- ためす 設定 ----------------------------------------------
# 声と ピッチの 組みあわせ。いくつでも ならべられます。
COMBOS = [
    ("en-US-AvaNeural", "+30Hz"),
]

# 作る 文を id で しぼりこめます。から([])に すると 話者Kの 全部を 作ります。
#   a133nt0w = Dad, my bike broke down again.
#   awf6juj  = Something smells good. What are you making?
ONLY_IDS = []

SPEAKER = "K"                 # 子ども
# ---------------------------------------------------------------

RETRY = 5
WAIT = 1.2

MANIFEST = os.path.join(ROOT, "data", "audio_manifest.json")


def outdir(voice, pitch):
    """声と ピッチ ごとに べつの フォルダに 出します。"""
    return os.path.join(
        ROOT, "audio_test",
        "%s_%s_pitch%s" % (SPEAKER, voice.replace("en-US-", ""), pitch),
    )

try:
    import edge_tts
except ImportError:
    print("\n[エラー] edge-tts が 入っていません:  pip install edge-tts\n")
    sys.exit(1)

# 本番の しくみを そのまま 借ります(make_audio.py は
# if __name__ == "__main__" で 守られているので、読みこんでも 走りません)
import make_audio


def slug(text):
    """ファイル名用に 文の あたまを 4語だけ とりだします。"""
    words = []
    for w in text.split()[:4]:
        w = "".join(c for c in w if c.isalnum())
        if w:
            words.append(w)
    return "_".join(words)


async def main():
    if not os.path.exists(MANIFEST):
        print("\n[エラー] %s が ありません。"
              "さきに build_audio_manifest.py を 実行してください。\n" % MANIFEST)
        sys.exit(1)

    with open(MANIFEST, encoding="utf-8") as f:
        allk = [i for i in json.load(f) if i.get("speaker") == SPEAKER]

    if not allk:
        print("\n[エラー] 話者 %s の 文が 見つかりません。\n" % SPEAKER)
        sys.exit(1)

    # 通し番号は 話者K 全体での 順番に そろえます。
    # (しぼりこんでも フォルダ間で 同じ 番号に なるように)
    numbered = list(enumerate(allk, 1))
    if ONLY_IDS:
        numbered = [(n, i) for n, i in numbered if i["id"] in ONLY_IDS]
        missing = set(ONLY_IDS) - {i["id"] for _, i in numbered}
        if missing:
            print("\n[エラー] 話者%s に この id が ありません: %s\n"
                  % (SPEAKER, ", ".join(sorted(missing))))
            sys.exit(1)

    print("\n  はやさ %s   話者 %s   %d 本 × %d とおり"
          % (make_audio.RATE, SPEAKER, len(numbered), len(COMBOS)))
    print("  ※ 本番と おなじ 処理(speak_text + 無音トリム)です")
    print("  ※ 本番の audio/ には さわりません\n")

    failed = []
    for voice, pitch in COMBOS:
        out = outdir(voice, pitch)
        os.makedirs(out, exist_ok=True)
        print("  --- %s  %s ---" % (voice, pitch))

        for n, item in numbered:
            text = item["text"]
            name = "%02d_%s_%s.mp3" % (n, item["id"], slug(text))
            path = os.path.join(out, name)
            if os.path.exists(path) and os.path.getsize(path) > 500:
                print("    %02d. すでにあります  %s" % (n, text[:46]))
                continue

            for attempt in range(RETRY):
                try:
                    tts = edge_tts.Communicate(
                        make_audio.speak_text(item), voice,
                        rate=make_audio.RATE, pitch=pitch,
                    )
                    await tts.save(path)
                    if os.path.getsize(path) < 500:
                        raise RuntimeError("ファイルが小さすぎます")
                    make_audio.trim_silence(path)   # 本番と おなじ 無音けずり
                    print("    %02d. %s" % (n, text[:46]))
                    break
                except Exception as e:
                    if os.path.exists(path):
                        try:
                            os.remove(path)
                        except OSError:
                            pass
                    if attempt == RETRY - 1:
                        print("    %02d. %d回ためして だめでした  (%s)"
                              % (n, RETRY, str(e)[:56]))
                        failed.append((voice, pitch, n))
                    else:
                        await asyncio.sleep(WAIT * (attempt + 1))
            await asyncio.sleep(WAIT)
        print()

    if failed:
        print("  ※ %d本 できませんでした。もう一度 実行すると 足りない分だけ 作ります。\n"
              % len(failed))
    print("  audio_test/ の 各フォルダを 聴きくらべてください。\n")


if __name__ == "__main__":
    if sys.platform.startswith("win"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
