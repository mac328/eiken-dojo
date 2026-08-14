#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
英語音声(mp3)を一括で作ります。

じゅんび:  pip install edge-tts
じっこう:  python tools/make_audio.py

・すでにある mp3 は作りなおしません（とちゅうで止めても、もう一度実行すれば続きから）
・8本ずつ同時に作るので、721個でだいたい 3〜6分です
"""
import asyncio
import json
import os
import sys

VOICE = "en-US-JennyNeural"   # ふだんの声(単語・模範解答など)

# 会話リスニングで つかう 声
#   M = 大人の男性 / F = 大人の女性 / K = 子ども
VOICES = {
    "M": "en-US-GuyNeural",
    "F": "en-US-JennyNeural",
    "K": "en-US-AnaNeural",
}

# 声の たかさ(ピッチ)の 調整。
# 子ども(K)の声は そのままだと 幼すぎるので すこし 低くしています。
# もっと低くしたいときは "-25Hz" のように 数字を 大きく、
# 高くもどしたいときは "-5Hz" や "+0Hz" にしてください。
PITCH = {
    "K": "-60Hz",
}
RATE = "-10%"                 # 少しゆっくり。ふつうの速さにするなら "+0%"
PARALLEL = 8                  # 同時に作る数
RETRY = 3                     # しっぱいしたときのやりなおし回数

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "audio")

try:
    import edge_tts
except ImportError:
    print("\n[エラー] edge-tts が入っていません。さきに次を実行してください:")
    print("    pip install edge-tts\n")
    sys.exit(1)


def load_manifest():
    path = os.path.join(ROOT, "data", "audio_manifest.json")
    if not os.path.exists(path):
        print("\n[エラー] data/audio_manifest.json がありません。")
        print("    さきに  python tools/build_data.py  を実行してください。\n")
        sys.exit(1)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


class Counter:
    def __init__(self, total):
        self.total = total
        self.done = 0
        self.made = 0
        self.skip = 0
        self.fail = []

    def tick(self, kind, label=""):
        self.done += 1
        if kind == "made":
            self.made += 1
        elif kind == "skip":
            self.skip += 1
        else:
            self.fail.append(label)
        bar_len = 30
        filled = int(bar_len * self.done / self.total)
        bar = "#" * filled + "." * (bar_len - filled)
        sys.stdout.write("\r  [%s] %d/%d  (新規 %d / スキップ %d / 失敗 %d)   "
                         % (bar, self.done, self.total, self.made,
                            self.skip, len(self.fail)))
        sys.stdout.flush()


# --- 前後の 無音を 切りとる ---------------------------------
# edge-tts の mp3 は おしりに 1秒ちかい 無音が つくので、
# 会話が とぎれて 聞こえます。それを 短くします。
TRIM = True          # 無音カットを つかうか
KEEP_MS = 80         # 前後に のこす 余白(ミリ秒)

def trim_silence(path):
    """mp3の 前後の 無音を けずって 上書きします。
    pydub が 入っていない ときは なにも しません。"""
    if not TRIM:
        return
    try:
        from pydub import AudioSegment
        from pydub.silence import detect_leading_silence
    except ImportError:
        return
    try:
        a = AudioSegment.from_mp3(path)
        lead = detect_leading_silence(a, silence_threshold=-45)
        tail = detect_leading_silence(a.reverse(), silence_threshold=-45)
        start = max(0, lead - KEEP_MS)
        end = len(a) - max(0, tail - KEEP_MS)
        if end - start < 200:      # 短すぎるときは さわらない
            return
        a[start:end].export(path, format="mp3", bitrate="48k")
    except Exception:
        pass


def speak_text(item):
    """よみあげ用に 少し ととのえます。
    模範解答の 「A / B / C」は スラッシュのままだと 読みにくいので
    間(ま)が あくように します。"""
    t = item["text"]
    if " / " in t:
        t = t.replace(" / ", " ... ")
    return t


async def one(item, sem, counter):
    path = os.path.join(OUT, item["id"] + ".mp3")
    if os.path.exists(path) and os.path.getsize(path) > 500:
        counter.tick("skip")
        return
    async with sem:
        for attempt in range(RETRY):
            tmp = path + ".part"
            try:
                sp = item.get("speaker")
                voice = VOICES.get(sp, VOICE)
                pitch = PITCH.get(sp, "+0Hz")
                tts = edge_tts.Communicate(speak_text(item), voice,
                                           rate=RATE, pitch=pitch)
                await tts.save(tmp)
                if os.path.getsize(tmp) < 500:
                    raise RuntimeError("ファイルが小さすぎます")
                os.replace(tmp, path)
                trim_silence(path)
                counter.tick("made")
                return
            except Exception:
                if os.path.exists(tmp):
                    try:
                        os.remove(tmp)
                    except OSError:
                        pass
                if attempt == RETRY - 1:
                    counter.tick("fail", item["text"])
                    return
                await asyncio.sleep(1.5 * (attempt + 1))


def clean_orphans(items):
    """マニフェストに ない mp3 は もう使われないので 消します。
    （単語を 直したときに 古い音声が 残らないように）"""
    want = set(i["id"] + ".mp3" for i in items)
    if not os.path.isdir(OUT):
        return 0
    gone = [f for f in os.listdir(OUT) if f.endswith(".mp3") and f not in want]
    for f in gone:
        try:
            os.remove(os.path.join(OUT, f))
        except OSError:
            pass
    return len(gone)


async def main():
    os.makedirs(OUT, exist_ok=True)
    items = load_manifest()
    n_gone = clean_orphans(items)
    if n_gone:
        print("\n  使われなくなった mp3 を %d 個 かたづけました" % n_gone)
    n_sp = sum(1 for i in items if i.get("speaker"))
    print("\n  声       : %s" % VOICE)
    if n_sp:
        print("  会話の声 : 男性 %s / 女性 %s / 子ども %s%s  (%d本)"
              % (VOICES["M"], VOICES["F"], VOICES["K"],
                 " " + PITCH["K"] if PITCH.get("K") else "", n_sp))
    print("  はやさ   : %s" % RATE)
    print("  作る数   : %d 個" % len(items))
    print("  ほぞん先 : %s\n" % OUT)

    if TRIM:
        try:
            import pydub  # noqa
            print("  無音カット: ON (前後の 無音を けずります)")
        except ImportError:
            print("  無音カット: OFF")
            print("    ※ pip install pydub  を すると、会話の 間が")
            print("      ちょうど よくなります(ffmpeg も 必要です)")
    print("")

    counter = Counter(len(items))
    sem = asyncio.Semaphore(PARALLEL)
    await asyncio.gather(*[one(i, sem, counter) for i in items])

    print("\n")
    if counter.fail:
        print("  %d 個だけ作れませんでした:" % len(counter.fail))
        for t in counter.fail[:10]:
            print("    - " + t)
        if len(counter.fail) > 10:
            print("    ...ほか %d 個" % (len(counter.fail) - 10))
        print("\n  もう一度  python tools/make_audio.py  を実行すると、")
        print("  足りない分だけ作りなおします。\n")
    else:
        total = sum(os.path.getsize(os.path.join(OUT, f))
                    for f in os.listdir(OUT) if f.endswith(".mp3"))
        print("  ぜんぶできました！  合計 %.1f MB\n" % (total / 1024 / 1024))


if __name__ == "__main__":
    if sys.platform.startswith("win"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
