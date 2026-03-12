#!/usr/bin/env python3
"""
Neon Bikes - Light cycle arena game for the Hak5 WiFi Pineapple Pager
Display: 480x222 RGB565 via libpagerctl.so
Author: wickedNull

Controls:
  D-pad  - steer your bike
  A (GREEN) - start / restart
  B (RED)   - quit / back to title
"""

import sys
import os
import random
import traceback

# ── lib path ────────────────────────────────────────────────────────────────
# payload.sh passes $PAYLOAD_DIR/lib as argv[1]
# We search that dir plus known fallbacks for pagerctl.py + libpagerctl.so

SEARCH_DIRS = []
if len(sys.argv) >= 2:
    SEARCH_DIRS.append(sys.argv[1])
SEARCH_DIRS += [
    os.path.join(os.path.dirname(__file__), "lib"),
    "/root/payloads/user/utilities/PAGERCTL",
    "/mmc/root/payloads/user/utilities/PAGERCTL",
]

LIB_DIR = None
for d in SEARCH_DIRS:
    if os.path.isfile(os.path.join(d, "pagerctl.py")) and \
       os.path.isfile(os.path.join(d, "libpagerctl.so")):
        LIB_DIR = d
        break

if LIB_DIR is None:
    print("ERROR: pagerctl.py / libpagerctl.so not found in any search path")
    print("Searched:", SEARCH_DIRS)
    sys.exit(1)

# Make sure the .so is findable at runtime
os.environ["LD_LIBRARY_PATH"] = (
    LIB_DIR + ":/mmc/usr/lib:/mmc/lib:" +
    os.environ.get("LD_LIBRARY_PATH", "")
)
sys.path.insert(0, LIB_DIR)

try:
    from pagerctl import Pager
except ImportError as e:
    print(f"ERROR: Failed to import pagerctl: {e}")
    traceback.print_exc()
    sys.exit(1)

# ── Display constants ────────────────────────────────────────────────────────
SCREEN_W = 480
SCREEN_H = 222
CELL     = 4          # px per grid cell  →  120 × 55 grid

GRID_W = SCREEN_W // CELL   # 120
GRID_H = SCREEN_H // CELL   #  55

# Directions (dx, dy)
UP    = ( 0, -1)
DOWN  = ( 0,  1)
LEFT  = (-1,  0)
RIGHT = ( 1,  0)
OPPOSITE = {UP: DOWN, DOWN: UP, LEFT: RIGHT, RIGHT: LEFT}

# Scorebar at top
SCOREBAR_H = 10
PLAY_Y0    = (SCOREBAR_H // CELL) + 1   # top playfield row (in cells)
PLAY_Y1    = GRID_H - 1                  # bottom (exclusive)
PLAY_X0    = 1
PLAY_X1    = GRID_W - 1

# ── Colours (RGB565 packed) ──────────────────────────────────────────────────
def rgb(r, g, b):
    return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)

C_BG        = rgb(  0,   0,  10)
C_WALL      = rgb( 30,  30,  30)
C_SCORE_BG  = rgb( 10,  10,  10)
C_P1_HEAD   = rgb(  0, 255, 255)   # cyan  (player)
C_P1_TRAIL  = rgb(  0,  90, 130)
C_P2_HEAD   = rgb(255,  80,   0)   # orange (CPU)
C_P2_TRAIL  = rgb(120,  40,   0)
C_WHITE     = rgb(255, 255, 255)
C_GREEN     = rgb(  0, 255,  80)
C_RED       = rgb(255,  50,  50)
C_YELLOW    = rgb(255, 220,   0)
C_TITLE     = rgb(  0, 210, 255)
C_SUBTITLE  = rgb(  0, 160, 200)
C_DIM       = rgb(160, 160, 160)

# ── AI helper ────────────────────────────────────────────────────────────────
def _flood(grid, sx, sy):
    """Count reachable empty cells from (sx, sy) via BFS."""
    if grid[sy][sx] != 0:
        return 0
    seen = {(sx, sy)}
    q = [(sx, sy)]
    while q:
        cx, cy = q.pop()
        for dx, dy in (UP, DOWN, LEFT, RIGHT):
            nx, ny = cx + dx, cy + dy
            if (PLAY_X0 <= nx < PLAY_X1 and PLAY_Y0 <= ny < PLAY_Y1
                    and grid[ny][nx] == 0 and (nx, ny) not in seen):
                seen.add((nx, ny))
                q.append((nx, ny))
    return len(seen)


def ai_dir(grid, ax, ay, cur_dir):
    """Pick direction with most open space; add slight randomness to avoid determinism."""
    candidates = []
    for d in (UP, DOWN, LEFT, RIGHT):
        if d == OPPOSITE[cur_dir]:
            continue
        nx, ny = ax + d[0], ay + d[1]
        if (PLAY_X0 <= nx < PLAY_X1 and PLAY_Y0 <= ny < PLAY_Y1
                and grid[ny][nx] == 0):
            candidates.append((_flood(grid, nx, ny), d))
    if not candidates:
        return cur_dir
    candidates.sort(reverse=True)
    top_space = candidates[0][0]
    good = [d for s, d in candidates if s >= top_space * 0.75]
    return random.choice(good)


# ── Game state ───────────────────────────────────────────────────────────────
class Game:
    def __init__(self):
        self.p1_score = 0
        self.p2_score = 0
        self.reset()

    def reset(self):
        self.grid = [[0] * GRID_W for _ in range(GRID_H)]
        mid_y = (PLAY_Y0 + PLAY_Y1) // 2
        q1x   = PLAY_X0 + (PLAY_X1 - PLAY_X0) // 4
        q3x   = PLAY_X1 - (PLAY_X1 - PLAY_X0) // 4
        self.p1x, self.p1y, self.p1d = q1x, mid_y, RIGHT
        self.p2x, self.p2y, self.p2d = q3x, mid_y, LEFT
        self.p1_alive = True
        self.p2_alive = True
        self.grid[self.p1y][self.p1x] = 1
        self.grid[self.p2y][self.p2x] = 2
        self.over   = False
        self.result = None   # 'p1' | 'p2' | 'draw'

    def step(self):
        if self.over:
            return

        if self.p1_alive:
            nx, ny = self.p1x + self.p1d[0], self.p1y + self.p1d[1]
            if (nx < PLAY_X0 or nx >= PLAY_X1 or
                    ny < PLAY_Y0 or ny >= PLAY_Y1 or
                    self.grid[ny][nx] != 0):
                self.p1_alive = False
            else:
                self.p1x, self.p1y = nx, ny
                self.grid[ny][nx] = 1

        if self.p2_alive:
            self.p2d = ai_dir(self.grid, self.p2x, self.p2y, self.p2d)
            nx, ny = self.p2x + self.p2d[0], self.p2y + self.p2d[1]
            if (nx < PLAY_X0 or nx >= PLAY_X1 or
                    ny < PLAY_Y0 or ny >= PLAY_Y1 or
                    self.grid[ny][nx] != 0):
                self.p2_alive = False
            else:
                self.p2x, self.p2y = nx, ny
                self.grid[ny][nx] = 2

        if not self.p1_alive and not self.p2_alive:
            self.over = True; self.result = 'draw'
        elif not self.p1_alive:
            self.over = True; self.result = 'p2'; self.p2_score += 1
        elif not self.p2_alive:
            self.over = True; self.result = 'p1'; self.p1_score += 1


# ── Renderer ─────────────────────────────────────────────────────────────────
class Renderer:
    def __init__(self, p):
        self.p = p

    def cell(self, gx, gy, color):
        self.p.fill_rect(gx * CELL, gy * CELL, CELL, CELL, color)

    def _walls(self):
        for x in range(GRID_W):
            self.cell(x, PLAY_Y0 - 1, C_WALL)
            self.cell(x, PLAY_Y1,     C_WALL)
        for y in range(PLAY_Y0, PLAY_Y1):
            self.cell(PLAY_X0 - 1, y, C_WALL)
            self.cell(PLAY_X1,     y, C_WALL)

    def _scorebar(self, g):
        p = self.p
        p.fill_rect(0, 0, SCREEN_W, SCOREBAR_H, C_SCORE_BG)
        p.draw_text(4, 1, f"YOU {g.p1_score}", C_P1_HEAD, 1)
        p.draw_text_centered(1, "NEON BIKES", C_TITLE, 1)
        label = f"CPU {g.p2_score}"
        p.draw_text(SCREEN_W - p.text_width(label, 1) - 4, 1, label, C_P2_HEAD, 1)

    def _heads(self, g):
        if g.p1_alive:
            self.p.fill_rect(g.p1x * CELL - 1, g.p1y * CELL - 1,
                             CELL + 2, CELL + 2, C_P1_HEAD)
        if g.p2_alive:
            self.p.fill_rect(g.p2x * CELL - 1, g.p2y * CELL - 1,
                             CELL + 2, CELL + 2, C_P2_HEAD)

    def full_draw(self, g):
        self.p.clear(C_BG)
        self._walls()
        for gy in range(PLAY_Y0, PLAY_Y1):
            for gx in range(PLAY_X0, PLAY_X1):
                v = g.grid[gy][gx]
                if v == 1:
                    self.cell(gx, gy, C_P1_TRAIL)
                elif v == 2:
                    self.cell(gx, gy, C_P2_TRAIL)
        self._heads(g)
        self._scorebar(g)

    def delta_draw(self, g, op1, op2):
        """Only repaint changed cells — much faster than full_draw every frame."""
        if op1 and g.p1_alive:
            self.cell(op1[0], op1[1], C_P1_TRAIL)
        if op2 and g.p2_alive:
            self.cell(op2[0], op2[1], C_P2_TRAIL)
        self._heads(g)
        self._scorebar(g)

    def game_over_overlay(self, g):
        result = g.result
        if result == 'p1':
            msg, col = "YOU WIN!", C_GREEN
        elif result == 'p2':
            msg, col = "CPU WINS", C_RED
        else:
            msg, col = "  DRAW  ", C_YELLOW
        bx = SCREEN_W // 2 - 72
        by = SCREEN_H // 2 - 20
        self.p.fill_rect(bx, by, 144, 42, rgb(8, 8, 8))
        self.p.draw_rect(bx, by, 144, 42, col)
        self.p.draw_text_centered(by + 5,  msg,              col,     2)
        self.p.draw_text_centered(by + 26, "A=Restart B=Menu", C_WHITE, 1)

    def title_screen(self, p1s, p2s):
        p = self.p
        p.clear(C_BG)
        p.draw_text_centered(10,  "NEON BIKES",        C_TITLE,    4)
        p.draw_text_centered(52,  "LIGHT CYCLE ARENA", C_SUBTITLE, 2)
        p.draw_text_centered(78,  "by wickedNull",     C_DIM,      1)
        p.draw_text_centered(96,  "YOU  vs  CPU",      C_WHITE,    1)
        p.draw_text_centered(110, "D-PAD = STEER",     C_DIM,      1)
        p.draw_text_centered(122, "A=START   B=QUIT",  C_DIM,      1)
        if p1s or p2s:
            p.draw_text_centered(142,
                f"SCORE   YOU {p1s} : {p2s} CPU", C_WHITE, 1)
        p.draw_text_centered(160, "PRESS A TO PLAY",   C_GREEN,    1)


# ── Input helpers ─────────────────────────────────────────────────────────────
def wait_for_a_or_b(p):
    """Block until A or B pressed. Returns True=A, False=B."""
    while True:
        _, pressed, _ = p.poll_input()
        if pressed & p.BTN_A:
            return True
        if pressed & p.BTN_B:
            return False
        p.delay(30)


# ── Main ──────────────────────────────────────────────────────────────────────
def run():
    try:
        p = Pager()
    except Exception as e:
        print(f"ERROR: Failed to open Pager: {e}")
        traceback.print_exc()
        sys.exit(1)

    try:
        # The Pager display is physically rotated 270° relative to the buffer
        p.set_rotation(270)

        r = Renderer(p)
        g = Game()

        # ── Title loop ──────────────────────────────────────────────────────
        while True:
            r.title_screen(g.p1_score, g.p2_score)
            p.flip()
            if not wait_for_a_or_b(p):
                return   # B = quit

            # ── Round loop ──────────────────────────────────────────────────
            g.reset()
            r.full_draw(g)
            p.flip()

            op1 = op2 = None
            quit_flag = False

            while not g.over:
                p.delay(60)   # ~16 FPS

                op1 = (g.p1x, g.p1y) if g.p1_alive else None
                op2 = (g.p2x, g.p2y) if g.p2_alive else None

                _, pressed, _ = p.poll_input()

                if pressed & p.BTN_UP    and g.p1d != DOWN:  g.p1d = UP
                if pressed & p.BTN_DOWN  and g.p1d != UP:    g.p1d = DOWN
                if pressed & p.BTN_LEFT  and g.p1d != RIGHT: g.p1d = LEFT
                if pressed & p.BTN_RIGHT and g.p1d != LEFT:  g.p1d = RIGHT
                if pressed & p.BTN_B:
                    quit_flag = True
                    break

                g.step()
                r.delta_draw(g, op1, op2)
                p.flip()

            if quit_flag:
                continue   # back to title loop

            # ── Game-over ───────────────────────────────────────────────────
            if g.result == 'p1':
                p.beep(880, 80)
                p.delay(90)
                p.beep(1100, 150)
            elif g.result == 'p2':
                p.beep(300, 200)
                p.vibrate(300)
            else:
                p.beep(500, 100)

            r.game_over_overlay(g)
            p.flip()

            # A = restart, B = title
            if wait_for_a_or_b(p):
                # restart — don't reset scores, loop back
                pass
            # either way fall through to title loop

    except Exception as e:
        print(f"RUNTIME ERROR: {e}")
        traceback.print_exc()
    finally:
        try:
            p.close()
        except Exception:
            pass


if __name__ == "__main__":
    run()
