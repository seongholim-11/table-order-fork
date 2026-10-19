"""매장 테이블 배치도를 비스듬히 내려다본(아이소메트릭) SVG 평면도로 그린다.

테이블 좌표가 DB에 없어서 번호 순서대로 홀(칸막이로 나뉜 줄)과 테라스에 자동으로 놓는다.
제안이 있는 테이블만 주황색으로 강조하고, 선택된 테이블에는 핀을 붙인다.
"""

from html import escape

A, B, H = 28, 14, 26  # 한 칸의 가로 반폭·세로 반높이·높이 1단위의 픽셀 (2:1 아이소메트릭)
COLS = 5              # 홀 한 줄에 놓는 테이블 수
PITCH_U, PITCH_V = 1.9, 1.7  # 테이블 사이 간격(칸 단위)
TABLE_U, TABLE_V, TABLE_H = 1.1, 0.7, 0.32
WALL_H = 2.6
FLOOR, WOOD, GREEN = "#d9d6d0", "#e4c796", "#2f6b3a"


def _shade(hex_color: str, factor: float) -> str:
    """색을 어둡게(factor<1) 해서 옆면 색을 만든다."""
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
    return "#%02x%02x%02x" % (int(r * factor), int(g * factor), int(b * factor))


def _layout(total: int):
    """테이블 번호별 (u, v, 구역) 위치를 정한다. 구역은 'hall' 또는 'terrace'."""
    terrace_n = min(6, total // 5)
    hall_n = total - terrace_n
    places = {}
    for i in range(hall_n):
        row, col = divmod(i, COLS)
        places[i + 1] = (0.7 + col * PITCH_U, 1.0 + row * PITCH_V + (row // 2) * 0.5, "hall")  # 두 줄마다 칸막이 자리를 비운다
    hall_rows = -(-hall_n // COLS)
    hall_v_end = 1.0 + hall_rows * PITCH_V + ((hall_rows - 1) // 2) * 0.5 + 0.3
    for j in range(terrace_n):
        row, col = divmod(j, 3)
        places[hall_n + j + 1] = (0.7 + (COLS - 3 + col) * PITCH_U, hall_v_end + 0.6 + row * PITCH_V, "terrace")
    width = 0.7 + COLS * PITCH_U
    depth = hall_v_end + (0.6 + (-(-terrace_n // 3)) * PITCH_V + 0.3 if terrace_n else 0)
    return places, width, depth, hall_v_end, terrace_n


def table_map_svg(total: int, highlighted: set, selected=None) -> str:
    """배치도 SVG 문자열. highlighted: 제안이 있는 테이블 번호들, selected: 지금 보고 있는 테이블 번호."""
    places, W, D, hall_end, terrace_n = _layout(max(total, max(highlighted, default=0), 1))
    ox, oy = D * A + 10, WALL_H * H + 10  # 그림 전체를 화면 안으로 옮기는 값

    def p(u, v, z=0):
        """칸 좌표(u,v)·높이 z → 화면 좌표."""
        return f"{ox + (u - v) * A:.1f},{oy + (u + v) * B - z * H:.1f}"

    def poly(points, fill, extra=""):
        return f'<polygon points="{" ".join(points)}" fill="{fill}" {extra}/>'

    def box(u, v, du, dv, h, top, z0=0.0, extra=""):
        """직육면체: 윗면과 보이는 두 옆면(앞-왼쪽, 앞-오른쪽)."""
        z1 = z0 + h
        left = poly([p(u, v + dv, z0), p(u + du, v + dv, z0), p(u + du, v + dv, z1), p(u, v + dv, z1)], _shade(top, .82), extra)
        right = poly([p(u + du, v, z0), p(u + du, v + dv, z0), p(u + du, v + dv, z1), p(u + du, v, z1)], _shade(top, .68), extra)
        up = poly([p(u, v, z1), p(u + du, v, z1), p(u + du, v + dv, z1), p(u, v + dv, z1)], top, extra)
        return left + right + up

    out = []
    # 바닥, 테라스 나무 바닥
    out.append(poly([p(0, 0), p(W, 0), p(W, D), p(0, D)], FLOOR))
    if terrace_n:
        out.append(poly([p(W - 3 * PITCH_U - 0.3, hall_end), p(W, hall_end), p(W, D), p(W - 3 * PITCH_U - 0.3, D)], WOOD))
        out.append(f'<text x="{p(W - 1.6 * PITCH_U, hall_end + 0.35).split(",")[0]}" y="{p(W - 1.6 * PITCH_U, hall_end + 0.35).split(",")[1]}" '
                   f'text-anchor="middle" font-size="10" fill="#8a6a3b">테라스</text>')
    # 뒤쪽 벽과 왼쪽 벽 (하얀 벽)
    out.append(poly([p(0, 0), p(W, 0), p(W, 0, WALL_H), p(0, 0, WALL_H)], "#f4f3f0", 'stroke="#c9c6c0"'))
    out.append(poly([p(0, 0), p(0, D), p(0, D, WALL_H), p(0, 0, WALL_H)], "#e7e5e0", 'stroke="#c9c6c0"'))
    # 주방 카운터(초록)
    out.append(box(0.4, 0.15, 2.8, 0.55, 0.9, GREEN))
    out.append(f'<text x="{p(1.8, 0.45, 0.95).split(",")[0]}" y="{p(1.8, 0.45, 0.95).split(",")[1]}" text-anchor="middle" '
               f'font-size="10" fill="#fff">주방</text>')

    # 칸막이(초록 낮은 벽)와 테이블·의자는 뒤에서 앞 순서로 겹쳐 그린다
    items = []
    for row_end_v in sorted({round(v - 0.45, 2) for (u, v, zone) in places.values() if zone == "hall" and round((v - 1.0) / PITCH_V) % 2 == 0 and v > 1.0}):
        for col in range(COLS):  # 칸막이는 테이블 칸 폭만큼씩 잘라 그려 순서가 어긋나지 않게 한다
            u0 = 0.4 + col * PITCH_U
            items.append((u0 + PITCH_U / 2 + row_end_v, box(u0, row_end_v, PITCH_U, 0.12, 0.6, GREEN)))
    for number, (u, v, _zone) in places.items():
        on, picked = number in highlighted, number == selected
        top = "#ff7a1a" if on else "#e8d2ae"
        glow = 'stroke="#c2410c" stroke-width="2.5"' if picked else ""
        chairs = "".join(box(u + cu, v + cv, 0.26, 0.26, 0.28, "#9a6b45")
                         for cv in (-0.34, TABLE_V + 0.08) for cu in (0.12, 0.72))
        label = p(u + TABLE_U / 2, v + TABLE_V / 2, TABLE_H + 0.02)
        lx, ly = label.split(",")
        text = (f'<text x="{lx}" y="{float(ly) + 3:.1f}" text-anchor="middle" font-size="9" font-weight="700" '
                f'fill="{"#fff" if on else "#5b4630"}">{number}</text>')
        pin = ""
        if picked:  # 선택한 테이블 위에 핀 표시
            px, py = p(u + TABLE_U / 2, v + TABLE_V / 2, TABLE_H + 1.2).split(",")
            pin = (f'<circle cx="{px}" cy="{py}" r="9" fill="#c2410c"/>'
                   f'<text x="{px}" y="{float(py) + 4:.1f}" text-anchor="middle" font-size="11">💡</text>')
        items.append((u + v + TABLE_U / 2 + TABLE_V / 2, f"<g>{chairs}{box(u, v, TABLE_U, TABLE_V, TABLE_H, top, 0.0, glow)}{text}{pin}</g>"))
    out += [svg for _key, svg in sorted(items, key=lambda x: x[0])]

    width, height = (W + D) * A + 20, (W + D) * B + WALL_H * H + 20
    label = f"매장 테이블 배치도. 제안이 있는 테이블: {', '.join(map(str, sorted(highlighted))) or '없음'}"
    return (f'<svg viewBox="0 0 {width:.0f} {height:.0f}" xmlns="http://www.w3.org/2000/svg" role="img" '
            f'aria-label="{escape(label)}" style="width:100%;height:auto;background:#eceae6;border-radius:12px">'
            + "".join(out) + "</svg>")
