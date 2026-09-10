# -*- coding: utf-8 -*-
"""
현행 대비 확정 도안 수정 위치 표기.
박스는 눈대중이 아니라 픽셀을 읽어 글자의 실제 경계에 맞춘다.
  빨강 = 변경·추가 (확정 도안) / 파랑 = 삭제 (현행 도안)
"""
from PIL import Image, ImageDraw, ImageFont
import numpy as np
import os, sys

BASE = r'c:\Users\BLUETREND\류호정\bt\bidding\부각포장지'
OLD = os.path.join(BASE, 'reference', 'img')
NEW = os.path.join(BASE, 'reference', '시안_260909_최종')
OUT = os.path.join(BASE, 'reference', '수정표기')
os.makedirs(OUT, exist_ok=True)

FONT = r'C:\Windows\Fonts\malgun.ttf'
FONTB = r'C:\Windows\Fonts\malgunbd.ttf'
RED = (214, 32, 42)
BLUE = (20, 90, 210)


def f(sz, bold=False):
    return ImageFont.truetype(FONTB if bold else FONT, sz)


# ── 픽셀 기반 자동 맞춤 ────────────────────────────────────────────
def _ink(im, box):
    """seed 영역 안에서 배경과 다른 픽셀(글자·선)의 불리언 마스크를 만든다."""
    g = np.asarray(im.convert('L').crop(box), dtype=np.int16)
    bg = int(np.bincount(g.ravel().clip(0, 255)).argmax())   # 최빈값 = 배경
    return np.abs(g - bg) > 45, bg


def _runs(on, gap):
    runs, st = [], None
    for i, v in enumerate(on):
        if v and st is None:
            st = i
        elif not v and st is not None:
            runs.append([st, i - 1]); st = None
    if st is not None:
        runs.append([st, len(on) - 1])
    out = []
    for r in runs:
        if out and r[0] - out[-1][1] <= gap:
            out[-1][1] = r[1]
        else:
            out.append(r)
    return out


def fit(im, seed, fitx=True, mode='center'):
    """
    seed 안의 실제 글자 경계로 박스를 좁힌다.
    표 괘선(가로로 거의 꽉 찬 행)은 제외한다.
      mode='center' — seed 중앙에 가장 가까운 글줄 하나만 잡는다
      mode='all'    — seed 안 글자 전체를 잡는다
    """
    x0, y0, x1, y1 = [int(v) for v in seed]
    m, _ = _ink(im, (x0, y0, x1, y1))
    h, w = m.shape
    rows = m.sum(axis=1)
    rows[rows >= w * 0.90] = 0                      # 괘선 제거
    frac = 0.020 if mode.startswith('line:') else 0.004
    on = rows >= max(2, int(w * frac))
    if not on.any():
        return seed

    runs = _runs(on, max(2, h // 120))
    if mode.startswith('line:'):
        i = int(mode.split(':')[1])
        if i >= len(runs):
            return seed
        r0, r1 = runs[i]
    elif mode == 'center' and runs:
        mid = h / 2
        r0, r1 = min(runs, key=lambda r: abs((r[0] + r[1]) / 2 - mid))
    else:
        r0, r1 = runs[0][0], runs[-1][1]

    if fitx:
        cols = m[r0:r1 + 1].sum(axis=0)
        ci = np.where(cols >= max(1, int((r1 - r0 + 1) * 0.05)))[0]
        if len(ci) == 0:
            ci = np.where(cols > 0)[0]
        nx0, nx1 = x0 + int(ci[0]), x0 + int(ci[-1])
    else:
        nx0, nx1 = x0, x1
    return (nx0, y0 + int(r0), nx1, y0 + int(r1))


# ── 표기 정의 ──────────────────────────────────────────────────────
# (번호, 라벨, seed(x0,y0,x1,y1) 비율, line index 또는 None)
SPECS = {
    '김부각_앞면': {
        'new': [(1, '영문 제품명 추가 — Gim Bugak / (Crispy Seaweed Chips)', (.055, .795, .310, .868), True, 'all', 12),
                (2, 'Made in Korea 추가', (.780, .845, .968, .892), True, 'all', 12)],
        'old': [],
    },
    '김부각_뒷면': {
        'new': [(3, '원재료명 — 「김[김(국내산)]38%」→「김(국내산) 38%」, 「백설탕(원당)100%」→「설탕(원당 100%),」',
                 (.140, .384, .715, .406), True, 'all', 10),
                (4, '나트륨 238g → 240mg', (.690, .406, .982, .434), False, 'center', 3),
                (5, '지방 16g / 30% → 17g / 31%', (.690, .480, .982, .507), False, 'center', 3),
                (6, '제조시설 문구 — 「새우를 사용하는」→「새우, 밀을 사용한」', (.055, .595, .700, .870), True, 'line:6', 6),
                (7, 'HACCP 마크 추가', (.752, .865, .878, .975), True, 'all', 10)],
        'old': [(8, '제품 부제 2줄 삭제됨 — 「통찹쌀죽을 발라 튀겨내 바삭하고 / 짭조름하면서도 달짝지근한 맛」',
                 (.200, .275, .800, .345), True, 'all', 12)],
    },
    '고추부각_앞면': {
        'new': [(9, '영문 제품명 추가 — Gochu Bugak / (Crispy Pepper Chips)', (.055, .795, .310, .868), True, 'all', 12),
                (10, 'Made in Korea 추가', (.780, .845, .968, .892), True, 'all', 12),
                (11, '열량 416 → 415kcal (전면에도 표기됨)', (.050, .876, .320, .928), True, 'all', 12)],
        'old': [],
    },
    '고추부각_뒷면': {
        'new': [(12, '원재료명 순서 변경 — 찹쌀 2번 → 4번 (고추·밀가루·옥수수전분·찹쌀 순), 콜론 뒤 띄어쓰기',
                 (.140, .384, .715, .432), True, 'all', 10),
                (13, '열량 416 → 415kcal', (.690, .320, .982, .372), False, 'all', 3),
                (14, '나트륨 295g → 290mg', (.690, .406, .982, .434), False, 'center', 3),
                (15, '제조시설 문구 — 「새우를 사용하는」→「새우, 밀을 사용한」', (.055, .595, .700, .870), True, 'line:6', 6),
                (16, 'HACCP 마크 추가', (.752, .865, .878, .975), True, 'all', 10)],
        'old': [(17, '제품 부제 2줄 삭제됨 — 「말린 고추에 찹쌀을 버무려 잘 튀겨 / 씹을수록 고추의 매콤한 맛이 솔솔」',
                 (.200, .265, .800, .335), True, 'all', 12)],
    },
}

PAIRS = [
    ('김부각_앞면', '현행_김부각_앞면.png', '김부각 패키지_앞면.jpg'),
    ('김부각_뒷면', '현행_김부각_뒷면.png', '김부각 패키지_뒷면.jpg'),
    ('고추부각_앞면', '현행_고추부각_앞면.png', '고추부각 패키지_앞면.jpg'),
    ('고추부각_뒷면', '현행_고추부각_뒷면.png', '고추부각 패키지_뒷면.jpg'),
]


def annotate(im, specs, color, tag, side):
    im = im.convert('RGB')
    W, H = im.size
    d = ImageDraw.Draw(im)
    lw = max(3, W // 500)
    for n, _lab, seed, fx, md, mp in specs:
        sd = (W * seed[0], H * seed[1], W * seed[2], H * seed[3])
        b = fit(im, sd, fitx=fx, mode=md)
        m = max(2, int(mp * W / 1338))
        b = (b[0] - m, b[1] - m, b[2] + m, b[3] + m)
        print('   #%-2d %s  x %.4f~%.4f  y %.4f~%.4f' %
              (n, side, b[0] / W, b[2] / W, b[1] / H, b[3] / H))
        d.rounded_rectangle(b, radius=max(6, W // 200), outline=color, width=lw)
        r = max(22, W // 60)
        cx, cy = max(r + 2, b[0] - int(r * 0.9)), max(r + 2, b[1] - int(r * 0.9))
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=color, outline='white', width=max(2, lw - 1))
        fnt = f(int(r * 1.15), True)
        s = str(n)
        tb = d.textbbox((0, 0), s, font=fnt)
        d.text((cx - (tb[2] - tb[0]) / 2 - tb[0], cy - (tb[3] - tb[1]) / 2 - tb[1]), s, font=fnt, fill='white')
    return im


def build(tag, oldf, newf):
    print(tag)
    a = Image.open(os.path.join(OLD, oldf))
    b = Image.open(os.path.join(NEW, newf))
    h = min(a.height, b.height, 2400)
    a = a.resize((int(a.width * h / a.height), h), Image.LANCZOS)
    b = b.resize((int(b.width * h / b.height), h), Image.LANCZOS)

    sp = SPECS[tag]
    a = annotate(a, sp['old'], BLUE, tag, '현행')
    b = annotate(b, sp['new'], RED, tag, '확정')

    items = [(n, lab, RED) for n, lab, *_ in sp['new']] + [(n, lab, BLUE) for n, lab, *_ in sp['old']]
    items.sort(key=lambda x: x[0])

    pad, gap, head, lh = 44, 64, 150, 58
    W = pad * 2 + a.width + gap + b.width
    H = head + h + 34 + lh * len(items) + 76 + pad
    cv = Image.new('RGB', (W, H), 'white')
    d = ImageDraw.Draw(cv)

    d.text((pad, 24), '%s — 현행 대비 수정 위치' % tag.replace('_', ' '), font=f(48, True), fill='black')
    d.rounded_rectangle((pad, 84, pad + 30, 114), radius=6, outline=RED, width=4)
    d.text((pad + 44, 82), '변경·추가 (확정 도안 기준)', font=f(30), fill='black')
    x2 = pad + 44 + int(d.textlength('변경·추가 (확정 도안 기준)', font=f(30))) + 60
    d.rounded_rectangle((x2, 84, x2 + 30, 114), radius=6, outline=BLUE, width=4)
    d.text((x2 + 44, 82), '삭제 (현행에는 있으나 확정 도안에 없음)', font=f(30), fill='black')

    cv.paste(a, (pad, head)); cv.paste(b, (pad + a.width + gap, head))
    d.text((pad + 6, head - 44), '현행', font=f(36, True), fill=(80, 80, 80))
    d.text((pad + a.width + gap + 6, head - 44), '확정 (2026-09-09)', font=f(36, True), fill=RED)
    d.rectangle((pad, head, pad + a.width, head + h), outline=(185, 185, 185), width=2)
    d.rectangle((pad + a.width + gap, head, pad + a.width + gap + b.width, head + h),
                outline=(185, 185, 185), width=2)

    y = head + h + 40
    d.text((pad, y), '수정 항목', font=f(40, True), fill='black')
    y += 62
    for n, lab, col in items:
        d.ellipse((pad, y + 6, pad + 42, y + 48), fill=col)
        fnt = f(27, True)
        tb = d.textbbox((0, 0), str(n), font=fnt)
        d.text((pad + 21 - (tb[2] - tb[0]) / 2 - tb[0], y + 27 - (tb[3] - tb[1]) / 2 - tb[1]),
               str(n), font=fnt, fill='white')
        d.text((pad + 62, y + 9), lab, font=f(34), fill='black')
        y += lh

    p = os.path.join(OUT, '260910_%s_수정표기.png' % tag)
    cv.save(p, quality=92)
    print('  ->', p, cv.size)
    return p


if __name__ == '__main__':
    only = sys.argv[1] if len(sys.argv) > 1 else None
    for tag, o, n in PAIRS:
        if only and only != tag:
            continue
        build(tag, o, n)
