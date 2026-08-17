#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ストアの フィーチャーグラフィック（1024x500）を 作ります。

つかいかた:
    python tools/make_feature_graphic.py

しくみは make_store_shots.py と 同じです。
下じき（fg_format.png）の マゼンタに 本物の スクショを はめこみ、
左の あきに アプリ名を フォントで 描きます。

文字を 画像生成AIに 描かせないのは、日本語を 書きまちがえるためです。
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from PIL import Image, ImageDraw, ImageFilter          # noqa: E402
import numpy as np                                     # noqa: E402
from make_store_shots import (                         # noqa: E402
    perspective_coeffs, load_font,
    wipe_leftover_magenta, APP_TOP, APP_BOTTOM, BG, INK, SUB,
)


def rotated_rect_quad(img):
    """画面（マゼンタ）の 4すみと マスクを もとめます。

    この 下じきは 上から 見おろした 配置で、端末が すこし
    回転して います（台形では なく 回転した 長方形）。
    そこで 少しずつ 回してみて、いちばん 面積の 小さい
    長方形が おさまる 角度を さがし、その 4すみを つかいます。
    辺の 直線あてはめでは、回転した 形の 上辺と 横辺を
    区別できず、4すみが ずれます。"""
    a = np.array(img.convert("RGB")).astype(int)
    r, g, b = a[:, :, 0], a[:, :, 1], a[:, :, 2]
    m = (r > 100) & (b > 100) & (g < r * 0.80) & (g < b * 0.80)
    if not m.any():
        print("[エラー] マゼンタの 領域が 見つかりません")
        sys.exit(1)

    ys, xs = np.where(m)
    pts = np.stack([xs, ys], axis=1).astype(float)

    best = None
    for deg in np.arange(-25, 25, 0.25):
        t = np.deg2rad(deg)
        rot = np.array([[np.cos(t), -np.sin(t)], [np.sin(t), np.cos(t)]])
        q = pts @ rot.T
        w = q[:, 0].max() - q[:, 0].min()
        h = q[:, 1].max() - q[:, 1].min()
        if best is None or w * h < best[0]:
            best = (w * h, deg, q[:, 0].min(), q[:, 0].max(),
                    q[:, 1].min(), q[:, 1].max())

    _, deg, x0, x1, y0, y1 = best
    t = np.deg2rad(deg)
    back = np.array([[np.cos(t), np.sin(t)], [-np.sin(t), np.cos(t)]])
    corners = np.array([[x0, y0], [x1, y0], [x1, y1], [x0, y1]]) @ back.T
    quad = [(float(p[0]), float(p[1])) for p in corners]

    poly = Image.new("L", img.size, 0)
    ImageDraw.Draw(poly).polygon([(round(x), round(y)) for x, y in quad], fill=255)
    grown = Image.fromarray((m * 255).astype("uint8"), "L").filter(ImageFilter.MaxFilter(9))
    mask = Image.fromarray(
        (np.array(poly) | (np.array(grown) & 255)).astype("uint8"), "L")
    return quad, mask, deg

ROOT = os.path.dirname(HERE)
SHOTS = os.path.join(ROOT, "store_shots")
TEMPLATE = os.path.join(SHOTS, "fg_format.png")
SRC_SHOT = os.path.join(SHOTS, "02_menu.png")
OUT = os.path.join(SHOTS, "final", "feature_graphic.png")

APP_NAME = "英検準2級 反復トレ"
TAGLINE = "単語から二次面接まで、732問"

# 文字を 置く ところ（左のあき）。四辺の 端は 切られることが あるので
# 大事なものは 中央寄りに おきます。
TEXT_L, TEXT_R = 60, 600
NAME_SIZE = 74
TAG_SIZE = 34


def draw_with_edge(d, text, font, x, y, fill):
    for dx, dy in ((-3, 0), (3, 0), (0, -3), (0, 3), (-2, -2), (2, 2), (-2, 2), (2, -2)):
        d.text((x + dx, y + dy), text, font=font, fill="#FFFFFF")
    d.text((x, y), text, font=font, fill=fill)


def main():
    for p in (TEMPLATE, SRC_SHOT):
        if not os.path.exists(p):
            print("[エラー] %s が ありません" % p)
            sys.exit(1)

    base = Image.open(TEMPLATE).convert("RGB")
    if base.size != (1024, 500):
        print("[注意] サイズが %s です。Play は 1024x500 を もとめます" % (base.size,))

    quad, mask, deg = rotated_rect_quad(base)
    # 回転して いるので、辺の 長さは 座標の 引き算では なく 距離で 測る
    def dist(p, q):
        return ((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2) ** 0.5
    bw = int(round(dist(quad[0], quad[1])))
    bh = int(round(dist(quad[1], quad[2])))
    print("\n  下じき: %dx%d" % base.size)
    print("  画面の4すみ: " + " ".join("(%d,%d)" % (round(x), round(y)) for x, y in quad))
    print("  かたむき: %.1f度 / はめこむ 大きさ: %dx%d" % (deg, bw, bh))

    # スクショを 画面の 大きさに 合わせる（横幅ぞろえ・足りない分は 背景色）
    im = Image.open(SRC_SHOT).convert("RGB").crop((0, APP_TOP, 1080, APP_BOTTOM))
    k = bw / im.width
    im = im.resize((bw, max(1, int(round(im.height * k)))), Image.LANCZOS)
    canvas = Image.new("RGB", (bw, bh), BG)
    canvas.paste(im.crop((0, 0, bw, min(bh, im.height))), (0, 0))

    coeffs = perspective_coeffs(quad, [(0, 0), (bw, 0), (bw, bh), (0, bh)])
    warped = canvas.transform(base.size, Image.PERSPECTIVE, coeffs,
                              Image.BICUBIC, fillcolor=BG)
    img = base.copy()
    img.paste(warped, (0, 0), mask)
    img = wipe_leftover_magenta(img)

    # 左の あきに アプリ名
    d = ImageDraw.Draw(img)
    max_w = TEXT_R - TEXT_L
    size = NAME_SIZE
    while size > 40 and d.textlength(APP_NAME, font=load_font(size)) > max_w:
        size -= 2
    fn = load_font(size)
    ft = load_font(TAG_SIZE)
    nh, th = size, TAG_SIZE
    total = nh + 22 + th
    y = (500 - total) // 2
    cx = (TEXT_L + TEXT_R) / 2

    w = d.textlength(APP_NAME, font=fn)
    draw_with_edge(d, APP_NAME, fn, cx - w / 2, y, INK)
    w2 = d.textlength(TAGLINE, font=ft)
    draw_with_edge(d, TAGLINE, ft, cx - w2 / 2, y + nh + 22, SUB)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    img.save(OUT)
    print("\n  %s に 出しました。\n" % OUT)


if __name__ == "__main__":
    main()
