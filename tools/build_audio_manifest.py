#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
反復道場(index.html)から 英語の音声にしたい文を すべて 取り出して
data/audio_manifest.json を 作ります。

つかいかた:
    python tools/build_audio_manifest.py

・index.html は このスクリプトの ひとつ上のフォルダに ある想定です
・作られた manifest を make_audio.py が よみこんで mp3 を作ります
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
HTML = os.path.join(ROOT, "index.html")
OUTDIR = os.path.join(ROOT, "data")


def js_hash(text):
    """index.html の中の Au() と 同じ計算。ファイル名を そろえるため。
    JavaScript: t=(t<<5)-t+charCode; t|=0  → 32bit符号付き整数
    """
    h = 0
    for ch in text:
        h = (h << 5) - h + ord(ch)
        # 32bit 符号付きに 丸める (JavaScript の |0 と 同じ)
        h &= 0xFFFFFFFF
        if h >= 0x80000000:
            h -= 0x100000000
    return "a" + format(h & 0xFFFFFFFF, "x") if False else "a" + _to36(h & 0xFFFFFFFF)


def _to36(n):
    """JavaScript の toString(36) と 同じ"""
    if n == 0:
        return "0"
    digits = "0123456789abcdefghijklmnopqrstuvwxyz"
    out = ""
    while n:
        out = digits[n % 36] + out
        n //= 36
    return out


def unescape_js(s):
    """\\u3042 のような エスケープを 元の文字に もどす"""
    def rep(m):
        return chr(int(m.group(1), 16))
    s = re.sub(r"\\u([0-9a-fA-F]{4})", rep, s)
    s = s.replace("\\'", "'").replace('\\"', '"').replace("\\\\", "\\")
    s = s.replace("\\n", "\n")
    return s


# ライブラリの中の 英単語を まちがって ひろわないための 除外リスト
NG_EXACT = {
    "metaKey", "shiftKey", "altKey", "ctrlKey", "className", "innerHTML",
    "onChange", "onClick", "children", "useState", "createElement",
    "undefined", "function", "prototype", "constructor", "toString",
}


def is_english(s):
    """英語の文だけを 音声にします(日本語が 混ざっていたら 除外)"""
    if not s or len(s.strip()) < 2:
        return False
    # ひらがな・カタカナ・漢字が あったら 日本語
    if re.search(r"[\u3040-\u30ff\u4e00-\u9fff]", s):
        return False
    # 全角の空所記号(　)が ある文は 筆記問題なので 音声にしません
    if "\u3000" in s or "(\u3000)" in s:
        return False
    # プログラムの中の 語は 除外
    if s in NG_EXACT:
        return False
    # camelCase など プログラムっぽい 1語は 除外
    if " " not in s and re.match(r"^[a-z]+[A-Z]", s):
        return False
    # アルファベットが 入っていること
    return bool(re.search(r"[A-Za-z]{2,}", s))


def collect(html):
    """index.html の 中から 英語のテキストを あつめます"""
    items = {}   # id -> text (重複は 自動で ひとつに)

    def add(text, kind):
        text = text.strip()
        if not is_english(text):
            return
        # 模範解答の "A / B / C" は 1本の音声として そのまま読ませる
        i = js_hash(text)
        if i not in items:
            items[i] = {"id": i, "text": text, "kind": kind}

    # --- 単語・熟語 (["achieve","〜を達成する","動"] の 3つ組) ---
    # 品詞は 動/名/形/副/熟 のどれか(大文字小文字どちらのエスケープにも対応)
    pos = r'(?:\\u52[Dd]5|\\u540[Dd]|\\u5[Ff]62|\\u526[Ff]|\\u719[Ff])'
    pat = r'\["((?:[^"\\]|\\.)+?)","(?:[^"\\]|\\.)+?","' + pos + r'"\]'
    for m in re.finditer(pat, html):
        add(unescape_js(m.group(1)), "word")

    # --- 各データの英語フィールドを ひろう ---
    # passage / q / a / lines / prompt など
    for key in ["passage", "q", "a"]:
        for m in re.finditer(key + r':"((?:[^"\\]|\\.)*)"', html):
            add(unescape_js(m.group(1)), key)

    # lines:["...","..."] (会話リスニング)
    for m in re.finditer(r'lines:\[((?:"(?:[^"\\]|\\.)*",?)+)\]', html):
        for mm in re.finditer(r'"((?:[^"\\]|\\.)*)"', m.group(1)):
            add(unescape_js(mm.group(1)), "line")

    # c:[...] の 選択肢 (会話文・会話リスニングの 英語選択肢)
    for m in re.finditer(r'c:\[((?:"(?:[^"\\]|\\.)*",?){2,4})\]', html):
        for mm in re.finditer(r'"((?:[^"\\]|\\.)*)"', m.group(1)):
            add(unescape_js(mm.group(1)), "choice")

    return list(items.values())


def main():
    if not os.path.exists(HTML):
        print("\n[エラー] index.html が みつかりません: %s\n" % HTML)
        sys.exit(1)

    with open(HTML, encoding="utf-8") as f:
        html = f.read()

    items = collect(html)
    if not items:
        print("\n[エラー] 英語のテキストを 取り出せませんでした。\n")
        sys.exit(1)

    os.makedirs(OUTDIR, exist_ok=True)
    out = os.path.join(OUTDIR, "audio_manifest.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=1)

    kinds = {}
    for it in items:
        kinds[it["kind"]] = kinds.get(it["kind"], 0) + 1

    print("\n  音声にする文: %d 個" % len(items))
    for k, v in sorted(kinds.items(), key=lambda x: -x[1]):
        label = {"word": "単語・熟語", "passage": "音読パッセージ",
                 "q": "質問文", "a": "模範解答",
                 "line": "会話リスニング", "choice": "選択肢"}.get(k, k)
        print("    %-16s %4d" % (label, v))
    print("\n  ほぞん先: %s" % out)
    print("\n  つぎは  python tools/make_audio.py  を実行してください。\n")


if __name__ == "__main__":
    main()
