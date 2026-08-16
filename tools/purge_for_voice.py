#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
声を かえた ときに、作り直しが 必要な mp3 だけを 消します。

つかいかた:
    python tools/purge_for_voice.py            ← 何を 消すか 見るだけ
    python tools/purge_for_voice.py --yes      ← じっさいに 消す
    python tools/purge_for_voice.py --speaker F --yes   ← 会話の F の声も 消す

しくみ:
    make_audio.py の VOICE(ふだんの声)を かえたときは、
    会話リスニング いがいの すべて(単語・選択肢・質問文・模範解答・
    音読パッセージ)を 作り直す 必要が あります。
    会話リスニングは VOICES{M,F,K} で 別に 決まるので、
    そちらを かえた ときだけ --speaker で 指定してください。

    消したあと  python tools/make_audio.py  を 実行すると、
    足りない分だけ 新しい声で 作りなおします。
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
AUDIO = os.path.join(ROOT, "audio")
MANIFEST = os.path.join(ROOT, "data", "audio_manifest.json")


def main():
    args = sys.argv[1:]
    do_it = "--yes" in args
    speakers = []
    while "--speaker" in args:
        i = args.index("--speaker")
        speakers.append(args[i + 1])
        del args[i:i + 2]

    if not os.path.exists(MANIFEST):
        print("\n[エラー] data/audio_manifest.json が ありません。")
        print("    さきに python tools/build_audio_manifest.py を 実行してください。\n")
        sys.exit(1)
    with open(MANIFEST, encoding="utf-8") as f:
        items = json.load(f)

    targets, kinds = [], {}
    for it in items:
        sp = it.get("speaker")
        hit = (sp is None) or (sp in speakers)
        if not hit:
            continue
        p = os.path.join(AUDIO, it["id"] + ".mp3")
        if os.path.exists(p):
            targets.append(p)
            k = "会話(%s)" % sp if sp else it.get("kind", "?")
            kinds[k] = kinds.get(k, 0) + 1

    label = {"word": "単語・熟語", "passage": "音読パッセージ", "q": "質問文",
             "a": "模範解答", "choice": "選択肢"}
    print("\n  作り直しの 対象: %d 個" % len(targets))
    for k, v in sorted(kinds.items(), key=lambda x: -x[1]):
        print("    %-16s %4d" % (label.get(k, k), v))
    if speakers:
        print("\n  会話リスニングの 話者 %s も ふくめています" % ",".join(speakers))
    else:
        print("\n  会話リスニングは のこします(VOICES を かえた ときは --speaker を つけてください)")

    if not do_it:
        print("\n  ためしに 見ただけです。じっさいに 消すには:")
        print("    python tools/purge_for_voice.py --yes\n")
        return

    n = 0
    for p in targets:
        try:
            os.remove(p)
            n += 1
        except OSError:
            pass
    print("\n  %d 個 消しました。" % n)
    print("  つぎは  python tools/make_audio.py  を 実行してください。\n")


if __name__ == "__main__":
    main()
