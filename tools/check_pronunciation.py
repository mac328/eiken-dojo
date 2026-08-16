#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
単語の mp3 を 音声認識に かけて、まちがった 発音の 語を 自動で さがします。

じゅんび:
    pip install faster-whisper

つかいかた:
    python tools/check_pronunciation.py             ← 単語300語を 点検
    python tools/check_pronunciation.py --idiom     ← 熟語90語も 点検
    python tools/check_pronunciation.py --model small   ← 精度を 上げる(おそい)

しくみ:
    mp3 を 音声認識で 文字に もどして、もとの 単語と くらべます。
    「cause」の mp3 が 「coos」と 認識されたら、発音が ちがう しるしです。
    結果は audio_check_report.tsv に 出ます。

だいじな こと:
    これは 「あやしいものを ふるいに かける」道具です。
    音声認識も かんぺきでは ないので、
      ・NG と 出たのに 実は 正しい (からぶり)
      ・OK と 出たのに 実は ちがう (見のがし)
    が あります。NG と 出たものだけ 耳や Gemini で 確かめてください。
    300個 ぜんぶ 聴くより はるかに 楽に なります。
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
AUDIO = os.path.join(ROOT, "audio")
MANIFEST = os.path.join(ROOT, "data", "audio_manifest.json")
REPORT = os.path.join(ROOT, "audio_check_report.tsv")


def norm(s):
    s = s.lower().strip()
    s = re.sub(r"[^a-z' ]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def similarity(a, b):
    """0.0〜1.0。1.0 が 完全一致"""
    a, b = norm(a), norm(b)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    # レーベンシュタイン距離
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1,
                           prev[j - 1] + (ca != cb)))
        prev = cur
    return 1.0 - prev[-1] / max(len(a), len(b))


def main():
    args = sys.argv[1:]
    with_idiom = "--idiom" in args
    model_name = "tiny.en"   # 小さくて 落としやすい。精度を 上げるなら --model base.en
    if "--model" in args:
        model_name = args[args.index("--model") + 1]

    try:
        from faster_whisper import WhisperModel
    except ImportError:
        print("\n[エラー] faster-whisper が 入っていません:")
        print("    pip install faster-whisper\n")
        print("  ※ はじめて 動かすときだけ、モデルの ダウンロードが おきます")
        print("    (base.en で 150MB ほど。ネットに つながっている 必要が あります)\n")
        sys.exit(1)

    if not os.path.exists(MANIFEST):
        print("\n[エラー] data/audio_manifest.json が ありません。")
        print("    さきに python tools/build_audio_manifest.py を 実行してください。\n")
        sys.exit(1)

    with open(MANIFEST, encoding="utf-8") as f:
        items = json.load(f)
    words = [i for i in items if i.get("kind") == "word"]
    if not with_idiom:
        words = [i for i in words
                 if " " not in i["text"] and "\u301c" not in i["text"]]
    words.sort(key=lambda x: x["text"].lower())

    print("\n  モデルを よみこんでいます (%s)…" % model_name)
    print("  ※ はじめての ときは ダウンロードが おきます。")
    print("    とちゅうで 切れても、もう一度 実行すれば 続きから 落とします。\n")
    model = None
    for attempt in range(5):
        try:
            model = WhisperModel(model_name, device="cpu", compute_type="int8")
            break
        except Exception as e:
            print("  よみこみ しっぱい (%d回目): %s" % (attempt + 1, str(e)[:90]))
            if attempt < 4:
                import time
                time.sleep(3 * (attempt + 1))
    if model is None:
        print("""
  モデルを よみこめませんでした。つぎを ためしてください:

    1) もう一度 実行する（途中まで 落ちた分は のこっています）
    2) もっと 小さい モデルに する
         python tools/check_pronunciation.py --model tiny.en
    3) セキュリティソフトや VPN を 一時的に 止める
    4) それでも だめなら 手動で 落とす:
         pip install -U huggingface_hub
         huggingface-cli download Systran/faster-whisper-tiny.en
""")
        sys.exit(1)
    print("  点検する 語: %d 個\n" % len(words))

    rows, ng, miss = [], [], 0
    for n, it in enumerate(words, 1):
        path = os.path.join(AUDIO, it["id"] + ".mp3")
        if not os.path.exists(path):
            miss += 1
            continue
        try:
            segs, _ = model.transcribe(path, language="en", beam_size=5,
                                       vad_filter=False)
            heard = " ".join(s.text for s in segs).strip()
        except Exception as e:
            heard = "[認識できません: %s]" % e
        sc = similarity(it["text"], heard)
        judge = "OK" if sc >= 0.75 else ("？" if sc >= 0.5 else "NG")
        rows.append((judge, "%.2f" % sc, it["text"], heard, it["id"] + ".mp3"))
        if judge != "OK":
            ng.append((judge, sc, it["text"], heard, it["id"] + ".mp3"))
        sys.stdout.write("\r  [%d/%d] %-20s" % (n, len(words), it["text"][:20]))
        sys.stdout.flush()

    rows.sort(key=lambda r: float(r[1]))
    with open(REPORT, "w", encoding="utf-8") as f:
        f.write("判定\t一致度\t単語\t聞こえた内容\tファイル\n")
        for r in rows:
            f.write("\t".join(r) + "\n")

    print("\n\n  ==== 結果 ====")
    print("  点検: %d 個 / mp3なし: %d 個" % (len(rows), miss))
    print("  要確認 (NG または ？): %d 個\n" % len(ng))
    for judge, sc, w, heard, fn in sorted(ng, key=lambda x: x[1])[:40]:
        print("   %-3s %.2f  %-16s 聞こえた: %-24s %s" % (judge, sc, w, heard[:24], fn))
    if len(ng) > 40:
        print("   ...ほか %d 個" % (len(ng) - 40))
    print("\n  ぜんぶの 結果: %s" % REPORT)
    print("""
  つぎに すること:
    1. 上に 出た語だけ 実際に 聴いて(または Gemini に わたして)確かめる
       → audio_check/ に わかりやすい 名前で 出せます:
          python tools/export_word_audio.py
    2. 本当に おかしい語を tools/make_audio.py の SAY_AS に 追記
       言いかえの 候補さがしは:  python tools/try_pron.py <単語>
    3. その語の mp3 を audio/ から 消して  python tools/make_audio.py
    4. もう一度 このスクリプトで 確認
""")


if __name__ == "__main__":
    main()
