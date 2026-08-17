#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ストア用のスクリーンショットを 作ります。

つかいかた:
    python tools/make_store_shots.py

しくみ:
    1. 下じきの画像（scsho_format.png）から マゼンタ #FF00FF の 場所を さがす
    2. そこに 本物の スクショを はめこむ
    3. 上の あいている ところに キャッチコピーを 描く

なぜ この やりかたか:
    画像生成AIに 日本語を 描かせると 書きまちがえます
    （実際に「大問」が「大間」に なりました）。
    文字は フォントで 描けば まちがいません。
    下じきを 1枚だけ 使いまわすので、8枚の 見た目も そろいます。

    マゼンタの 画素だけを 差しかえるので、
    下の バッジが スマホに かさなっている ところも そのまま 残ります。
"""
import os
import sys

try:
    from PIL import Image, ImageDraw, ImageFont, ImageFilter
    import numpy as np
except ImportError:
    print("\n[エラー] pillow と numpy が いります:  pip install pillow numpy\n")
    sys.exit(1)

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SHOTS = os.path.join(ROOT, "store_shots")
OUT = os.path.join(SHOTS, "final")
TEMPLATE = os.path.join(SHOTS, "scsho_format.png")

# スクショのうち アプリが 写っている ところ
# （上の ステータスバーと 下の ナビゲーションバーは のぞく）
APP_TOP = 118
APP_BOTTOM = 2268       # ここから下は ナビゲーションバー（◁ ○ ☰）

BG = "#FBF7EE"          # アプリの 背景色。すきまを うめるのに つかう
INK = "#3B2A06"         # 見出しの 文字色
SUB = "#8A6A28"         # そえ書きの 文字色

FONT_CANDIDATES = [
    r"C:\Windows\Fonts\YuGothB.ttc",
    r"C:\Windows\Fonts\meiryob.ttc",
    r"C:\Windows\Fonts\msgothic.ttc",
]

# 文字を 置く ところ（スマホの 枠は y=400 あたりから 始まる）
TEXT_TOP = 40
TEXT_BOTTOM = 392
MARGIN_X = 40
MAIN_MAX = 104          # 見出しの 最大の 大きさ。ストアの 一覧でも 読めるように
MAIN_MIN = 62
SUB_SIZE = 50

# (もとのスクショ, 出す名前, メインコピー, サブコピー)
JOBS = [
    ("02_menu.png", "01_menu",
     "単語から面接まで、これ一つで", "732問をぜんぶ収録"),
    ("01_home_top.png", "02_home",
     "試験日までの毎日を、ひと目で", "今どこまで身についたかが分かる"),
    ("03_word.png", "03_word",
     "4択でテンポよく、単語300語", "連続正解でコンボが伸びる"),
    ("04_cloze_wrong.png", "04_explain",
     "間違えたときこそ、力がつく", "なぜ違うのかまで解説"),
    ("07_hint.png", "05_hint",
     "覚え方まで、390語ぶん", "語源やイメージで記憶に残す"),
    ("05_listening.png", "06_listening",
     "音声2078本、ぜんぶ端末の中に", "電波がなくても聞ける"),
    ("06_writing.png", "07_writing",
     "配点最大の英作文を、型で覚える", "意見論述とEメール返信"),
    ("08_interview.png", "08_interview",
     "二次面接も、本番と同じ流れで", "黙読→音読→質問→自己評価"),
]


def load_font(px):
    for p in FONT_CANDIDATES:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, px)
            except Exception:
                continue
    print("[エラー] 日本語フォントが 見つかりません")
    sys.exit(1)


def screen_quad(img):
    """画面（マゼンタ）の 4すみと マスクを もとめます。

    スマホが 奥ゆきほうこうに かたむいている ため、画面は
    長方形では なく 台形に なります。
    左右・上下の ふちに それぞれ 直線を あてはめ、
    その 交点を 4すみと します。
    こうすると 生成AIの ぼやけた ふちに 引きずられず、
    まっすぐな 辺に なります。"""
    a = np.array(img.convert("RGB")).astype(int)
    r, g, b = a[:, :, 0], a[:, :, 1], a[:, :, 2]
    m = (r > 100) & (b > 100) & (g < r * 0.80) & (g < b * 0.80)
    if not m.any():
        print("[エラー] マゼンタの 領域が 見つかりません")
        sys.exit(1)

    ys, xs = np.where(m)
    y0, y1 = ys.min(), ys.max()
    x0, x1 = xs.min(), xs.max()

    # 角の 丸みに かからないよう、上下・左右の 端 8% を のぞいて 直線を あてる
    def fit(points):
        p = np.array(points, dtype=float)
        return np.polyfit(p[:, 0], p[:, 1], 1)     # 傾き, 切片

    my = int((y1 - y0) * 0.08)
    lefts, rights = [], []
    for y in range(y0 + my, y1 - my):
        row = np.where(m[y])[0]
        if len(row) > 20:
            lefts.append((y, row.min()))
            rights.append((y, row.max()))
    mx = int((x1 - x0) * 0.08)
    tops, bottoms = [], []
    for x in range(x0 + mx, x1 - mx):
        col = np.where(m[:, x])[0]
        if len(col) > 20:
            tops.append((x, col.min()))
            bottoms.append((x, col.max()))

    al, bl = fit(lefts)        # x = al*y + bl
    ar, br = fit(rights)
    at, bt = fit(tops)         # y = at*x + bt
    ab, bb = fit(bottoms)

    def cross(a_v, b_v, a_h, b_h):
        """縦の辺 x=a_v*y+b_v と 横の辺 y=a_h*x+b_h の 交点。"""
        y = (a_h * b_v + b_h) / (1 - a_h * a_v)
        return (a_v * y + b_v, y)

    quad = [cross(al, bl, at, bt),      # 左上
            cross(ar, br, at, bt),      # 右上
            cross(ar, br, ab, bb),      # 右下
            cross(al, bl, ab, bb)]      # 左下

    # 4すみを むすんだ 形を マスクに する（辺は まっすぐ）
    poly = Image.new("L", img.size, 0)
    ImageDraw.Draw(poly).polygon([(round(x), round(y)) for x, y in quad], fill=255)
    # ぼやけた ふちが のこらないよう、マゼンタの 外には はみ出さない
    grown = Image.fromarray((m * 255).astype("uint8"), "L").filter(ImageFilter.MaxFilter(9))
    mask = Image.fromarray((np.array(poly) & np.array(grown)).astype("uint8"), "L")
    return quad, mask


def perspective_coeffs(dst, src):
    """dst(出力の4点) を src(入力の4点) に うつす 係数を もとめます。
    PIL の PERSPECTIVE は 出力→入力の むきで 指定します。"""
    A, B = [], []
    for (dx, dy), (sx, sy) in zip(dst, src):
        A.append([dx, dy, 1, 0, 0, 0, -sx * dx, -sx * dy])
        A.append([0, 0, 0, dx, dy, 1, -sy * dx, -sy * dy])
        B += [sx, sy]
    A = np.array(A, dtype=float)
    B = np.array(B, dtype=float)
    return np.linalg.solve(A, B) if A.shape[0] == 8 else np.linalg.lstsq(A, B, rcond=None)[0]


def magenta_mask(img):
    """はめこむ 場所を きめます。

    マゼンタの 形を そのまま つかうと、生成AIの ぼかしのせいで
    ふちが ガタガタに なります。そこで:
      1. 各行・各列の 端を 集めて「まん中の値」で まっすぐな 長方形を きめる
         （角の 丸みや バッジで ずれた 行は 少数なので 影響しない）
      2. その 長方形の 内がわに ある 非マゼンタ = バッジ を くりぬく
    こうすると 外がわは まっすぐ、バッジは そのまま 残ります。"""
    a = np.array(img.convert("RGB")).astype(int)
    r, g, b = a[:, :, 0], a[:, :, 1], a[:, :, 2]
    m = (r > 110) & (b > 110) & (g < r * 0.78) & (g < b * 0.78)
    if not m.any():
        print("[エラー] マゼンタの 領域が 見つかりません")
        sys.exit(1)

    lefts, rights, tops, bottoms = [], [], [], []
    for y in range(m.shape[0]):
        row = np.where(m[y])[0]
        if len(row) > 50:
            lefts.append(row.min())
            rights.append(row.max())
    for x in range(m.shape[1]):
        col = np.where(m[:, x])[0]
        if len(col) > 50:
            tops.append(col.min())
            bottoms.append(col.max())

    # 外がわ寄りの 値を とる。まん中の値だと 内に 寄りすぎて
    # マゼンタが すじ状に のこる。角の 丸みや バッジで
    # 極端に ずれた 少数の 行は percentile で 無視する。
    l = int(np.percentile(lefts, 3))
    rt = int(np.percentile(rights, 97)) + 1
    t = int(np.percentile(tops, 3))
    bt = int(np.percentile(bottoms, 97)) + 1
    box = (l, t, rt, bt)

    # まっすぐな 角丸長方形
    rect = Image.new("L", img.size, 0)
    ImageDraw.Draw(rect).rounded_rectangle(
        [box[0], box[1], box[2] - 1, box[3] - 1], radius=26, fill=255)

    # 長方形の じゅうぶん 内がわに ある 非マゼンタ = バッジ
    inner = rect.filter(ImageFilter.MinFilter(17))          # 8画素 内がわ
    occl = np.array(inner) > 0
    occl = occl & (~m)
    occl_img = Image.fromarray((occl * 255).astype("uint8"), mode="L")
    occl_img = occl_img.filter(ImageFilter.MaxFilter(9))    # ふちの 中間色まで 消す

    final = np.array(rect) & (~np.array(occl_img))
    return Image.fromarray(final.astype("uint8"), mode="L"), box


def wipe_leftover_magenta(img):
    """はめこんだ あとに のこった 紫の すじを 消します。

    生成AIの ふちは ぼけているので、まっすぐな 長方形では
    どうしても 1〜2画素 とりこぼします。
    のこった ところに まわりの 色を にじませて 目立たなく します。"""
    for _ in range(8):
        a = np.array(img).astype(int)
        r, g, b = a[:, :, 0], a[:, :, 1], a[:, :, 2]
        left = (r > 100) & (b > 100) & (g < r * 0.80) & (g < b * 0.80)
        if not left.any():
            break
        m = Image.fromarray((left * 255).astype("uint8"), mode="L")
        m = m.filter(ImageFilter.MaxFilter(3))      # ふちの 中間色も 対象に
        img.paste(img.filter(ImageFilter.GaussianBlur(4)), (0, 0), m)
    return img


def fit_shot(path, box_w, box_h):
    """スクショを 画面の 大きさに 合わせます。
    横幅を そろえ、足りない ぶんは アプリの 背景色で うめます。
    横を 切ると 中身が 欠けるので、そちらは しません。"""
    im = Image.open(path).convert("RGB")
    im = im.crop((0, APP_TOP, im.width, APP_BOTTOM))
    k = box_w / im.width
    new_h = max(1, int(round(im.height * k)))
    im = im.resize((box_w, new_h), Image.LANCZOS)
    canvas = Image.new("RGB", (box_w, box_h), BG)
    if new_h <= box_h:
        canvas.paste(im, (0, 0))            # 上ぞろえ。下に すきま
    else:
        canvas.paste(im.crop((0, 0, box_w, box_h)), (0, 0))  # 下を すこし 切る
    return canvas


def wrap_to_width(draw, text, font, max_w):
    """はみ出すなら 意味の 切れめで 折りかえします。

    切れめが 見つかったら、その 場所で 折るのを 優先します。
    幅に 収まるかは 見ません。収まらなければ 呼び出しもとが
    文字を 小さくして やりなおすためです。
    ここで 幅を 見てしまうと、大きい 文字のとき 切れめが 却下され、
    文字数の まん中で 機械的に 折れてしまいます
    （「配点最大の英作」＋「文を、型で覚える」のように なる）。"""
    if draw.textlength(text, font=font) <= max_w:
        return [text]
    for sep in ["、", "，", "。"]:
        i = text.find(sep)
        if 0 < i < len(text) - 1:
            return [text[: i + 1], text[i + 1:]]
    for sep in ["を", "も", "は", "で", "の"]:
        i = text.rfind(sep, 1, len(text) - 1)
        if i > 0:
            return [text[: i + 1], text[i + 1:]]
    mid = len(text) // 2
    return [text[:mid], text[mid:]]


def draw_center(draw, text, font, cy, fill):
    """まん中ぞろえで 描きます。読みやすいよう うすい 白ふちを つけます。"""
    w = draw.textlength(text, font=font)
    x = (1080 - w) / 2
    for dx, dy in ((-4,0),(4,0),(0,-4),(0,4),(-3,-3),(3,3),(-3,3),(3,-3),(-4,-4),(4,4)):
        draw.text((x + dx, cy + dy), text, font=font, fill="#FFFFFF")
    draw.text((x, cy), text, font=font, fill=fill)


def put_text(img, main, sub):
    d = ImageDraw.Draw(img)
    max_w = 1080 - MARGIN_X * 2

    # 入るかぎり 大きく。高さも はみ出さないように 見る
    avail_h = TEXT_BOTTOM - TEXT_TOP
    size = MAIN_MAX
    while size > MAIN_MIN:
        f = load_font(size)
        lines = wrap_to_width(d, main, f, max_w)
        h = int(size * 1.28) * len(lines) + 16 + int(SUB_SIZE * 1.2)
        if all(d.textlength(t, font=f) <= max_w for t in lines) and h <= avail_h:
            break
        size -= 2
    fm = load_font(size)
    lines = wrap_to_width(d, main, fm, max_w)

    fs = load_font(SUB_SIZE)
    lh = int(size * 1.28)
    total = lh * len(lines) + 16 + int(SUB_SIZE * 1.2)
    y = TEXT_TOP + max(0, ((TEXT_BOTTOM - TEXT_TOP) - total) // 2)

    for t in lines:
        draw_center(d, t, fm, y, INK)
        y += lh
    draw_center(d, sub, fs, y + 10, SUB)
    return img


def main():
    if not os.path.exists(TEMPLATE):
        print("[エラー] %s が ありません" % TEMPLATE)
        sys.exit(1)
    os.makedirs(OUT, exist_ok=True)

    base = Image.open(TEMPLATE).convert("RGB")
    quad, mask = screen_quad(base)
    # 台形を おおう 大きさで スクショを 用意してから ゆがめる
    bw = int(round(max(quad[1][0] - quad[0][0], quad[2][0] - quad[3][0])))
    bh = int(round(max(quad[3][1] - quad[0][1], quad[2][1] - quad[1][1])))
    print("\n  下じき: %dx%d" % (base.width, base.height))
    print("  画面の4すみ: " + " ".join("(%d,%d)" % (round(x), round(y)) for x, y in quad))
    print("  上辺 %d / 下辺 %d ← 台形\n"
          % (round(quad[1][0] - quad[0][0]), round(quad[2][0] - quad[3][0])))

    for src, name, main_c, sub_c in JOBS:
        p = os.path.join(SHOTS, src)
        if not os.path.exists(p):
            print("  [とばす] %s が ありません" % src)
            continue
        img = base.copy()
        shot = fit_shot(p, bw, bh)
        # スクショの 4すみ を 台形の 4すみ へ
        coeffs = perspective_coeffs(quad, [(0, 0), (bw, 0), (bw, bh), (0, bh)])
        warped = shot.transform(base.size, Image.PERSPECTIVE, coeffs,
                                Image.BICUBIC, fillcolor=BG)
        img.paste(warped, (0, 0), mask)
        img = wipe_leftover_magenta(img)    # すじ状に のこった 紫を 消す
        put_text(img, main_c, sub_c)
        out = os.path.join(OUT, name + ".png")
        img.save(out)
        print("  %-14s <- %-20s %s" % (name + ".png", src, main_c))

    print("\n  %s に 出しました。\n" % OUT)


if __name__ == "__main__":
    main()
