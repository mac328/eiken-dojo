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
import re
import sys

VOICE = "en-US-JennyNeural"   # ふだんの声(文を よむとき。選択肢・模範解答・音読など)

# 単語カード(1語だけ)を よむときの 声。
#   ふだんは VOICE と 同じ Jenny。聞きとりやすさが いちばん よいためです。
#   Jenny が 読みまちがえる 語だけ、下の VOICE_FOR で 別の声に します。
VOICE_WORD = "en-US-JennyNeural"

# 語ごとに 声を 指定したい ときの 例外表。
#   VOICE_WORD で うまく 読めない 語だけ、ここに 書きます。
#   例) graduate は Michelle だと 名詞の 読み(グラデュエット)に なるので、
#       動詞の 読み(グラデュエイト)が できる Jenny を つかいます。
#   Jenny は 語あたまの v が 弱く、日本語話者には d のように 聞こえます。
#   音声認識は 前後から 補って 正しく 認識できてしまいますが、
#   このアプリの つかい手は 学習者なので、聞き分けやすさを 優先して
#   「v で はじまる語」は まとめて Michelle に します。
#   (Michelle は v を はっきり 出します)
VOICE_FOR = {
    # v ではじまる語(全6語)
    "variety": "en-US-MichelleNeural",
    "various": "en-US-MichelleNeural",
    "vehicle": "en-US-MichelleNeural",
    "view": "en-US-MichelleNeural",
    "valuable": "en-US-MichelleNeural",
    "volunteer": "en-US-MichelleNeural",
    # Jenny だと 「クース(coos)」に なる
    "cause": "en-US-MichelleNeural",
}

# 会話リスニングで つかう 声
#   M = 大人の男性 / F = 大人の女性 / K = 子ども
#
# K(子ども)を えらんだ 経緯:
#   1. en-US-AnaNeural … 子ども声だが 舌足らずで 聞きとりにくい。
#      "Dad," が 「Jad」に 聞こえる 誤読も あった。
#   2. en-US-MichelleNeural +15Hz … 発音は 正確だが、
#      タグが News/Novel(朗読向け)で 落ちついて 聞こえすぎる。
#   3. en-US-EmmaNeural … 子どもらしいが カンマの 間が 156ms しか なく、
#      "Dad, my bike…" が 一続きに 聞こえる。話速も 大人役より 25%速い。不採用。
#   4. en-US-JennyNeural … 間は よいが、F(大人の女性)と 同じ 声。
#      K の 会話 18件中 13件が F との 掛けあいなので、
#      だれが 話しているか 聞きわけられなく なる。不採用。
#   5. en-US-AvaNeural +30Hz … 会話向き(Expressive)で カンマの 間も 感じられる。
#      やや ませた 声だが、中身は 中高生の 会話なので むしろ 合う。採用。
VOICES = {
    "M": "en-US-GuyNeural",
    "F": "en-US-JennyNeural",
    "K": "en-US-AvaNeural",
}

# 声の たかさ(ピッチ)の 調整。
# K は 大人の声を 高くして 子どもらしく 聞かせています。
# ピッチは 声の たかさだけを かえます。間の とりかたや 話速は かわりません
# (実測ずみ。+23〜+30Hz で 長さは 2372〜2382ms と ほぼ 同じ)。
PITCH = {
    "K": "+30Hz",
}
RATE = "-10%"                 # 少しゆっくり。ふつうの速さにするなら "+0%"


# ============================================================
# 読み上げが おかしい 語の 言いかえ表
# ============================================================
# TTS に 1語だけ わたすと、まちがった 読み方に なることが あります。
# (例) cause … 単独だと because の 短縮形 'cause と 解釈されて
#              「クース」のように 弱く 読まれてしまう
#
# ここに 「もとのつづり: 読ませたい つづり」を 書くと、
# 音声を 作るときだけ 差しかえます。
# ファイル名は もとの つづりから 決まるので、
# index.html は さわらなくて 大丈夫です。
#
# 直したい語を 見つけたら 1行 足して、その語の mp3 を 消してから
# make_audio.py を もう一度 実行してください。
# どの つづりが よいかは  python tools/try_pron.py cause  で
# 聴きくらべて 決められます。
SAY_AS = {
    # いまは 空です。
    # 声を かえても どうしても 直らない 語が 出たら、ここに 書きます。
    # 例)  "cause": "koz",
}

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
GAP_MS = 220         # 文と文の あいだの 無音を この長さまで 縮めます
                     # (「。」のあとの 長い ポーズ対策。0にはしないこと)

def trim_silence(path):
    """mp3の 無音を ととのえて 上書きします。
      (1) 前後の 無音を けずる
      (2) 文と文の あいだの 長い 無音を GAP_MS まで 縮める
    pydub が 入っていない ときは なにも しません。"""
    if not TRIM:
        return
    try:
        from pydub import AudioSegment
        from pydub.silence import detect_leading_silence, detect_silence
    except ImportError:
        return
    try:
        a = AudioSegment.from_mp3(path)

        # (1) 前後を そろえる
        lead = detect_leading_silence(a, silence_threshold=-45)
        tail = detect_leading_silence(a.reverse(), silence_threshold=-45)
        start = max(0, lead - KEEP_MS)
        end = len(a) - max(0, tail - KEEP_MS)
        if end - start < 200:      # 短すぎるときは さわらない
            return
        a = a[start:end]

        # (2) まん中の 長い 無音を 縮める
        #     GAP_MS より 長い ところだけ 対象(短い 区切りは そのまま)
        gaps = [(s, e) for s, e in
                detect_silence(a, min_silence_len=GAP_MS + 80,
                               silence_thresh=-45)
                if s > 50 and e < len(a) - 50]
        if gaps:
            out = AudioSegment.empty()
            pos = 0
            for s, e in gaps:
                out += a[pos:s] + a[s:s + GAP_MS]
                pos = e
            out += a[pos:]
            a = out

        a.export(path, format="mp3", bitrate="48k")
    except Exception:
        pass


def speak_text(item):
    """よみあげ用に 少し ととのえます。
      (1) 言いかえ表に ある語は 差しかえる
      (2) 熟語の 記号(〜 や -ing)を 読み上げ用に ととのえる
      (3) 模範解答の 「A / B / C」は 間(ま)が あくように する
    """
    t = item["text"]

    # (1) 言いかえ表(完全一致のみ)
    if t in SAY_AS:
        return SAY_AS[t]

    # (2) 熟語の 記号
    #     「〜」は 読ませない。 "look after 〜" → "look after"
    t = t.replace("\u301c", " ").replace("\uff5e", " ")
    #     "-ing" は そのままだと 記号として 読まれるので doing に する
    #     "keep -ing" → "keep doing" / "be used to -ing" → "be used to doing"
    t = re.sub(r"\s*-ing\b", " doing", t)
    t = re.sub(r"\s+", " ", t).strip()

    # (3) スラッシュ区切り
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
                if sp:
                    voice = VOICES.get(sp, VOICE)
                elif item.get("kind") == "word":
                    # 単語カードは 専用の声。語ごとの 指定が あれば そちら。
                    voice = VOICE_FOR.get(item["text"], VOICE_WORD)
                else:
                    voice = VOICE
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
    print("\n  声(文)   : %s" % VOICE)
    print("  声(単語) : %s%s" % (VOICE_WORD,
          ("  ※例外 %d 語" % len(VOICE_FOR)) if VOICE_FOR else ""))
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
