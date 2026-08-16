#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Android の アプリアイコンを 作ります。

つかいかた:
    python tools/make_icons.py            ← プレビューだけ 作る
    python tools/make_icons.py --install  ← android/ の アイコンを 差しかえる

もとの デザイン:
    index.html の PWA マニフェストに 入っている SVG と 同じ 絵柄です。
    山とグラフ、右上に のびる 矢印、下に「準2」。

なぜ スクリプトに するか:
    アイコンは 5段階の 解像度ぶん 必要で、手で 縮小すると
    大きさが そろわなくなります。デザインを 直したく なったら
    数値を かえて もう一度 走らせれば ぜんぶ 作りなおせます。

アダプティブアイコンの きまり:
    Android 8以降の ホーム画面は「背景」と「前景」の 2枚を
    重ねて、端末ごとの 形(丸・角丸・しずく など)に 切りぬきます。
    108dp のうち **中央 72dp しか 見える 保証が ありません**。
    そのため 前景は SAFE_RATIO の 内がわに 収めます。
    外がわに はみ出すと 端末に よっては 切れます。
"""
import os
import sys

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("\n[エラー] Pillow が 入っていません:  pip install pillow\n")
    sys.exit(1)

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RES = os.path.join(ROOT, "android", "app", "src", "main", "res")
PREVIEW = os.path.join(ROOT, "icon_preview")

# ---- 色（アプリ本体と そろえています）----------------------------
BG = "#FBF7EE"          # 生成りの 背景
HILL_BACK = "#FFE3B0"   # 山（うしろ）
HILL_FRONT = "#FFD183"  # 山（手まえ）
ARROW = "#F59E0B"       # 矢印
TEXT_COLOR = "#B45309"  # 「準2」の 文字

# ---- 文字 --------------------------------------------------------
TEXT = "準2"
TEXT_SIZE = 88          # デザイン空間(512)での 大きさ。index.html の SVG と 同じ
TEXT_BASELINE = 470     # 同上。山と 文字が 重ならない 位置
# ※ 下にずらしても 切れません。下の make_foreground() が
#    絵柄の 実際の 範囲を 測って 安全圏に 収めるためです
FONT_CANDIDATES = [
    r"C:\Windows\Fonts\YuGothB.ttc",
    r"C:\Windows\Fonts\meiryob.ttc",
    r"C:\Windows\Fonts\msgothic.ttc",
]

# ---- アダプティブアイコンの 安全圏 -------------------------------
SAFE_RATIO = 0.66       # 108dp のうち 72dp ≒ 0.667。すこし 余裕を みます

SS = 4                  # なめらかに するための 拡大倍率
D = 512                 # デザイン空間の 一辺

# 解像度ごとの 大きさ
LEGACY = {"mdpi": 48, "hdpi": 72, "xhdpi": 96, "xxhdpi": 144, "xxxhdpi": 192}
FOREGROUND = {"mdpi": 108, "hdpi": 162, "xhdpi": 216, "xxhdpi": 324, "xxxhdpi": 432}
PLAY_STORE = 512


def load_font(px):
    for p in FONT_CANDIDATES:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, px)
            except Exception:
                continue
    print("[エラー] 日本語フォントが 見つかりません")
    sys.exit(1)


def draw_artwork(dr, s):
    """絵柄だけを 描きます（背景は 描きません）。s は 拡大率。"""
    def P(pts):
        return [(x * s, y * s) for x, y in pts]

    # 山（うしろ）
    dr.polygon(P([(56, 384), (188, 232), (268, 300), (344, 176), (456, 384)]),
               fill=HILL_BACK)
    # 山（手まえ・濃いほう）
    dr.polygon(P([(344, 176), (300, 226), (336, 258), (456, 384)]),
               fill=HILL_FRONT)
    # 矢印の 軸
    dr.line(P([(344, 176), (344, 120)]), fill=ARROW, width=int(12 * s))
    # 矢印の あたま
    dr.polygon(P([(344, 122), (400, 140), (344, 158)]), fill=ARROW)
    # 「準2」
    f = load_font(int(TEXT_SIZE * s))
    dr.text((256 * s, TEXT_BASELINE * s), TEXT, font=f,
            fill=TEXT_COLOR, anchor="ms")


def artwork_layer():
    """絵柄だけの 透明な 画像と、その 中身の 範囲を かえします。"""
    img = Image.new("RGBA", (D * SS, D * SS), (0, 0, 0, 0))
    draw_artwork(ImageDraw.Draw(img), SS)
    return img, img.getbbox()


def rounded_mask(size, radius_ratio=112 / 512):
    m = Image.new("L", (size * SS, size * SS), 0)
    ImageDraw.Draw(m).rounded_rectangle(
        [0, 0, size * SS - 1, size * SS - 1],
        radius=int(size * SS * radius_ratio), fill=255)
    return m


def circle_mask(size):
    m = Image.new("L", (size * SS, size * SS), 0)
    ImageDraw.Draw(m).ellipse([0, 0, size * SS - 1, size * SS - 1], fill=255)
    return m


def make_legacy(size, shape):
    """むかしの 端末用（Android 7以下）。絵柄を いっぱいに 描きます。"""
    big = size * SS
    img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    bg = Image.new("RGBA", (big, big), BG)
    art, _ = artwork_layer()
    art = art.resize((big, big), Image.LANCZOS)
    bg.alpha_composite(art)
    mask = circle_mask(size) if shape == "round" else rounded_mask(size)
    img.paste(bg, (0, 0), mask)
    return img.resize((size, size), Image.LANCZOS)


def make_foreground(size):
    """アダプティブの 前景。絵柄を 中央 SAFE_RATIO に 収めます。"""
    big = size * SS
    img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    art, bbox = artwork_layer()
    art = art.crop(bbox)                      # 余白を 落とす
    safe = int(big * SAFE_RATIO)
    w, h = art.size
    k = min(safe / w, safe / h)               # 縦横比を たもって 収める
    art = art.resize((max(1, int(w * k)), max(1, int(h * k))), Image.LANCZOS)
    img.alpha_composite(art, ((big - art.width) // 2, (big - art.height) // 2))
    return img.resize((size, size), Image.LANCZOS)


def preview_masked(fg_size=432):
    """端末が どう 切りぬくかを 試した 見本を 作ります。"""
    fg = make_foreground(fg_size)
    out = {}
    for name, mk in (("circle", circle_mask), ("squircle", rounded_mask)):
        base = Image.new("RGBA", (fg_size * SS, fg_size * SS), BG)
        base.alpha_composite(fg.resize((fg_size * SS, fg_size * SS), Image.LANCZOS))
        m = mk(fg_size) if name == "circle" else rounded_mask(fg_size, 0.22)
        cut = Image.new("RGBA", (fg_size * SS, fg_size * SS), (0, 0, 0, 0))
        cut.paste(base, (0, 0), m)
        out[name] = cut.resize((fg_size, fg_size), Image.LANCZOS)
    return out


def main():
    install = "--install" in sys.argv
    os.makedirs(PREVIEW, exist_ok=True)

    # プレビュー（実物大 と 切りぬき見本）
    for name, img in preview_masked().items():
        p = os.path.join(PREVIEW, "adaptive_%s.png" % name)
        img.save(p)
        print("  プレビュー: %s" % os.path.basename(p))

    make_legacy(192, "square").resize((192, 192), Image.LANCZOS).save(
        os.path.join(PREVIEW, "legacy_square.png"))
    print("  プレビュー: legacy_square.png")

    # ホーム画面での 見えかた（48dp 相当）も 出す
    preview_masked()["circle"].resize((96, 96), Image.LANCZOS).save(
        os.path.join(PREVIEW, "home_size_96px.png"))
    print("  プレビュー: home_size_96px.png（ホーム画面のおおよその大きさ）")

    make_legacy(PLAY_STORE, "square").save(os.path.join(PREVIEW, "playstore_512.png"))
    print("  プレビュー: playstore_512.png（ストア掲載用）")

    if not install:
        print("\n  %s を 見てください。" % PREVIEW)
        print("  よければ  python tools/make_icons.py --install  で 差しかえます。\n")
        return

    print("\n  android/ の アイコンを 差しかえます")
    for d, size in LEGACY.items():
        folder = os.path.join(RES, "mipmap-" + d)
        make_legacy(size, "square").save(os.path.join(folder, "ic_launcher.png"))
        make_legacy(size, "round").save(os.path.join(folder, "ic_launcher_round.png"))
        make_foreground(FOREGROUND[d]).save(
            os.path.join(folder, "ic_launcher_foreground.png"))
        print("    mipmap-%-8s 通常%dpx / 丸%dpx / 前景%dpx"
              % (d, size, size, FOREGROUND[d]))

    # 背景色を アプリと そろえる（Capacitor の 初期値は 白）
    bgxml = os.path.join(RES, "values", "ic_launcher_background.xml")
    with open(bgxml, "w", encoding="utf-8", newline="\n") as f:
        f.write('<?xml version="1.0" encoding="utf-8"?>\n<resources>\n'
                '    <color name="ic_launcher_background">%s</color>\n'
                "</resources>\n" % BG)
    print("    背景色を %s に しました" % BG)
    print("\n  できました。\n")


if __name__ == "__main__":
    main()
