#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
単語の mp3 を 「単語名のファイル名」で コピーして 出します。

つかいかた:
    python tools/export_word_audio.py            ← 単語300語ぶん
    python tools/export_word_audio.py --idiom    ← 熟語90語も 入れる
    python tools/export_word_audio.py --batch 30 ← 30個ずつ フォルダ分け

なぜ 必要か:
    本番の audio/ の ファイル名は ハッシュ値(a1k8221.mp3)なので、
    音声を 人や AI に 確認して もらうとき、どの語か わかりません。
    このスクリプトは audio_check/ に 「cause.mp3」のような
    わかりやすい 名前で コピーします。中身は 同じ ファイルです。

確認の しかた:
    audio_check/batch01/ などを まとめて Gemini などに わたして
    「各ファイルが ファイル名どおりに 発音されているか」と きいてください。
    おかしい語が 見つかったら tools/make_audio.py の SAY_AS に
    言いかえを 足して、その語の mp3 を 消してから make_audio.py を
    実行しなおします。

audio_check/ は 確認用の コピーなので、消しても 本番に 影響しません。
"""
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, "audio")
OUT = os.path.join(ROOT, "audio_check")
MANIFEST = os.path.join(ROOT, "data", "audio_manifest.json")


def safe_name(w):
    """ファイル名に つかえる 形に します"""
    out = ""
    for ch in w:
        if ch.isalnum() or ch in " '-":
            out += ch
        else:
            out += "_"
    return "_".join(out.split()).strip("_")[:60]


def main():
    args = sys.argv[1:]
    with_idiom = "--idiom" in args
    batch = 0
    if "--batch" in args:
        batch = int(args[args.index("--batch") + 1])

    if not os.path.exists(MANIFEST):
        print("\n[エラー] data/audio_manifest.json が ありません。")
        print("    さきに  python tools/build_audio_manifest.py  を実行してください。\n")
        sys.exit(1)

    with open(MANIFEST, encoding="utf-8") as f:
        items = json.load(f)

    words = [i for i in items if i.get("kind") == "word"]
    if not with_idiom:
        # 熟語(スペースや 〜 を ふくむ)は のぞく
        words = [i for i in words
                 if " " not in i["text"] and "\u301c" not in i["text"]]

    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT, exist_ok=True)

    made, missing = 0, []
    listing = []
    for n, it in enumerate(sorted(words, key=lambda x: x["text"].lower())):
        src = os.path.join(SRC, it["id"] + ".mp3")
        if not os.path.exists(src):
            missing.append(it["text"])
            continue
        sub = OUT
        if batch:
            sub = os.path.join(OUT, "batch%02d" % (n // batch + 1))
            os.makedirs(sub, exist_ok=True)
        dst = os.path.join(sub, safe_name(it["text"]) + ".mp3")
        shutil.copyfile(src, dst)
        listing.append("%s\t%s.mp3" % (it["text"], safe_name(it["text"])))
        made += 1

    with open(os.path.join(OUT, "_一覧.txt"), "w", encoding="utf-8") as f:
        f.write("語\tファイル名\n" + "\n".join(listing) + "\n")

    print("\n  出しました: %d 個  ->  %s" % (made, OUT))
    if batch:
        print("  %d 個ずつ batch01/ batch02/ ... に 分けています" % batch)
    if missing:
        print("\n  mp3 が 見つからない語 (%d):" % len(missing))
        for w in missing[:10]:
            print("    - " + w)
        if len(missing) > 10:
            print("    ...ほか %d 個" % (len(missing) - 10))
        print("  → python tools/make_audio.py を さきに 実行してください")
    print("""
  確認の しかた:
    1. audio_check/batch01/ の mp3 を まとめて Gemini に わたす
    2. 「各ファイルが ファイル名どおりに 発音されているか、
        ちがうものだけ 挙げてください」と きく
    3. 見つかった語を tools/make_audio.py の SAY_AS に 追記
    4. その語の mp3 を audio/ から 消して make_audio.py を 実行
""")


if __name__ == "__main__":
    main()
