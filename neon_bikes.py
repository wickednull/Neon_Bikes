#!/usr/bin/env python3
"""
Neon Bikes - Light cycle arena game for the Hak5 WiFi Pineapple Pager
Display: 480x222 RGB565 via libpagerctl.so
Author: wickedNull
Controls:
  D-pad        - steer your bike
  A (GREEN)    - start / restart
  B (RED)      - quit / back to title
"""

import sys
import os
import random
import traceback

# -- lib path ------------------------------------------------------------------
SEARCH_DIRS = []
if len(sys.argv) >= 2:
    SEARCH_DIRS.append(sys.argv[1])
SEARCH_DIRS += [
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"),
    "/root/payloads/user/utilities/PAGERCTL",
    "/mmc/root/payloads/user/utilities/PAGERCTL",
]

LIB_DIR = None
for d in SEARCH_DIRS:
    if (os.path.isfile(os.path.join(d, "pagerctl.py")) and
            os.path.isfile(os.path.join(d, "libpagerctl.so"))):
        LIB_DIR = d
        break

if LIB_DIR is None:
    print("ERROR: pagerctl.py / libpagerctl.so not found")
    sys.exit(1)

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

# -- Display constants ---------------------------------------------------------
SCREEN_W = 480
SCREEN_H = 222
CELL     = 4        # px per grid cell → 120 x 55 grid

# Speed: game steps advanced per display frame. Higher = faster.
# 1=slow  2=medium  3=fast  4=very fast
STEPS_PER_FRAME = 1

GRID_W = SCREEN_W // CELL   # 120
GRID_H = SCREEN_H // CELL   #  55

UP    = ( 0, -1)
DOWN  = ( 0,  1)
LEFT  = (-1,  0)
RIGHT = ( 1,  0)
OPPOSITE = {UP: DOWN, DOWN: UP, LEFT: RIGHT, RIGHT: LEFT}

SCOREBAR_H = 10
PLAY_Y0    = (SCOREBAR_H // CELL) + 1
PLAY_Y1    = GRID_H - 1
PLAY_X0    = 1
PLAY_X1    = GRID_W - 1

# -- Colours -------------------------------------------------------------------
def rgb(r, g, b):
    return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)

C_BG       = rgb(  0,   0,  10)
C_WALL     = rgb( 30,  30,  30)
C_SCORE_BG = rgb( 10,  10,  10)
C_P1_HEAD  = rgb(  0, 255, 255)
C_P1_TRAIL = rgb(  0,  90, 130)
C_P2_HEAD  = rgb(255,  80,   0)
C_P2_TRAIL = rgb(120,  40,   0)
C_WHITE    = rgb(255, 255, 255)
C_GREEN    = rgb(  0, 255,  80)
C_RED      = rgb(255,  50,  50)
C_YELLOW   = rgb(255, 220,   0)
C_TITLE    = rgb(  0, 210, 255)
C_SUBTITLE = rgb(  0, 160, 200)
C_DIM      = rgb(160, 160, 160)

# -- AI ------------------------------------------------------------------------
def _open_neighbors(grid, x, y):
    count = 0
    for dx, dy in (UP, DOWN, LEFT, RIGHT):
        nx, ny = x + dx, y + dy
        if (PLAY_X0 <= nx < PLAY_X1 and PLAY_Y0 <= ny < PLAY_Y1
                and grid[ny][nx] == 0):
            count += 1
    return count

def ai_dir(grid, ax, ay, cur_dir):
    best_score = -1
    best_dirs  = []
    for d in (UP, DOWN, LEFT, RIGHT):
        if d == OPPOSITE[cur_dir]:
            continue
        nx, ny = ax + d[0], ay + d[1]
        if not (PLAY_X0 <= nx < PLAY_X1 and PLAY_Y0 <= ny < PLAY_Y1
                and grid[ny][nx] == 0):
            continue
        score = _open_neighbors(grid, nx, ny)
        for d2 in (UP, DOWN, LEFT, RIGHT):
            nx2, ny2 = nx + d2[0], ny + d2[1]
            if (PLAY_X0 <= nx2 < PLAY_X1 and PLAY_Y0 <= ny2 < PLAY_Y1
                    and grid[ny2][nx2] == 0):
                score += _open_neighbors(grid, nx2, ny2)
        if score > best_score:
            best_score = score
            best_dirs  = [d]
        elif score == best_score:
            best_dirs.append(d)
    return random.choice(best_dirs) if best_dirs else cur_dir

# -- Game state ----------------------------------------------------------------
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
        self.result = None

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

# -- Renderer ------------------------------------------------------------------
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
        lbl = f"CPU {g.p2_score}"
        p.draw_text(SCREEN_W - p.text_width(lbl, 1) - 4, 1, lbl, C_P2_HEAD, 1)

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
                if v == 1:   self.cell(gx, gy, C_P1_TRAIL)
                elif v == 2: self.cell(gx, gy, C_P2_TRAIL)
        self._heads(g)
        self._scorebar(g)

    def delta_draw(self, g, op1, op2):
        if op1 and g.p1_alive: self.cell(op1[0], op1[1], C_P1_TRAIL)
        if op2 and g.p2_alive: self.cell(op2[0], op2[1], C_P2_TRAIL)
        self._heads(g)
        self._scorebar(g)

    def game_over_overlay(self, g):
        if g.result == 'p1':   msg, col = "YOU WIN!", C_GREEN
        elif g.result == 'p2': msg, col = "CPU WINS", C_RED
        else:                  msg, col = "  DRAW  ", C_YELLOW
        bx, by = SCREEN_W // 2 - 72, SCREEN_H // 2 - 20
        self.p.fill_rect(bx, by, 144, 42, rgb(8, 8, 8))
        self.p.draw_rect(bx, by, 144, 42, col)
        self.p.draw_text_centered(by + 5,  msg,               col,     2)
        self.p.draw_text_centered(by + 26, "A=Restart  B=Menu", C_WHITE, 1)

    def title_screen(self, p1s, p2s):
        p = self.p
        p.clear(C_BG)
        p.draw_text_centered(10,  "NEON BIKES",         C_TITLE,    4)
        p.draw_text_centered(52,  "LIGHT CYCLE ARENA",  C_SUBTITLE, 2)
        p.draw_text_centered(78,  "by wickedNull",       C_SUBTITLE, 1)
        p.draw_text_centered(96,  "YOU  vs  CPU",        C_WHITE,    1)
        p.draw_text_centered(110, "D-PAD = STEER",       C_DIM,      1)
        p.draw_text_centered(122, "A=START   B=QUIT",    C_DIM,      1)
        if p1s or p2s:
            p.draw_text_centered(142,
                f"SCORE   YOU {p1s} : {p2s} CPU", C_WHITE, 1)
        p.draw_text_centered(160, "PRESS A TO PLAY",     C_GREEN,    1)

# -- Main ----------------------------------------------------------------------
def run():
    # Use the context manager — this is the official pattern from pagerctl docs.
    # __exit__ calls pager_cleanup() which releases the framebuffer and input
    # device cleanly. Without this the kernel driver stays locked and the
    # watchdog reboots the pager.
    with Pager() as p:
        p.set_rotation(270)

        # Cache class-level button constants once
        BTN_UP    = Pager.BTN_UP
        BTN_DOWN  = Pager.BTN_DOWN
        BTN_LEFT  = Pager.BTN_LEFT
        BTN_RIGHT = Pager.BTN_RIGHT
        BTN_A     = Pager.BTN_A
        BTN_B     = Pager.BTN_B

        r = Renderer(p)
        g = Game()

        # -- Title loop --------------------------------------------------------
        while True:
            r.title_screen(g.p1_score, g.p2_score)
            p.flip()

            # Wait for A (start) or B (quit)
            while True:
                _, pressed, _ = p.poll_input()
                if pressed & BTN_B:
                    return          # clean exit via context manager
                if pressed & BTN_A:
                    break
                p.delay(50)

            # -- Round loop ----------------------------------------------------
            g.reset()
            r.full_draw(g)
            p.flip()

            quit_to_title = False

            while not g.over:
                p.delay(50)  # game tick speed — tune here

                _, pressed, _ = p.poll_input()
                if pressed & BTN_UP    and g.p1d != DOWN:  g.p1d = UP
                if pressed & BTN_DOWN  and g.p1d != UP:    g.p1d = DOWN
                if pressed & BTN_LEFT  and g.p1d != RIGHT: g.p1d = LEFT
                if pressed & BTN_RIGHT and g.p1d != LEFT:  g.p1d = RIGHT
                if pressed & BTN_B:
                    quit_to_title = True
                    break

                # Multiple steps per frame = visual speed without extra flips
                for _ in range(STEPS_PER_FRAME):
                    if g.over:
                        break
                    op1 = (g.p1x, g.p1y) if g.p1_alive else None
                    op2 = (g.p2x, g.p2y) if g.p2_alive else None
                    g.step()
                    r.delta_draw(g, op1, op2)

                p.flip()

            if quit_to_title:
                continue        # back to title while-loop

            # -- Game over -----------------------------------------------------
            r.game_over_overlay(g)
            p.flip()

            while True:
                _, pressed, _ = p.poll_input()
                if pressed & BTN_A:
                    break           # restart — loop back to round
                if pressed & BTN_B:
                    quit_to_title = True
                    break
                p.delay(50)

            if quit_to_title:
                continue            # back to title while-loop
            # else: A was pressed → fall through, round loop restarts


if __name__ == "__main__":
    try:
        run()
    except Exception as e:
        with open("/tmp/neon_bikes_crash.log", "w") as f:
            traceback.print_exc(file=f)
        sys.exit(0)
