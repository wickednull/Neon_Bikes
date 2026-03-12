#!/usr/bin/env python3
"""
Neon Bikes - Light cycle arena game for the Hak5 WiFi Pineapple Pager
Display: 480x222 RGB565 via libpagerctl.so
Author: wickedNull
Controls:
  D-pad  - steer your bike
  A      - start / restart
  B      - quit
"""

import sys
import os
import random

if len(sys.argv) < 2:
    print("Usage: neon_bikes.py <lib_dir>")
    sys.exit(1)

LIB_DIR = sys.argv[1]
sys.path.insert(0, LIB_DIR)

try:
    from pagerctl import Pager
except ImportError as e:
    print(f"Failed to import pagerctl: {e}")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Display constants
# ---------------------------------------------------------------------------
SCREEN_W = 480
SCREEN_H = 222
CELL     = 4          # px per grid cell → 120 x 55 grid

# Speed: steps advanced per frame render. Higher = faster bikes.
# 1=slow, 2=normal, 3=fast, 4=very fast
STEPS_PER_FRAME = 3

GRID_W = SCREEN_W // CELL   # 120
GRID_H = SCREEN_H // CELL   # 55

# Directions (dx, dy)
UP    = ( 0, -1)
DOWN  = ( 0,  1)
LEFT  = (-1,  0)
RIGHT = ( 1,  0)
OPPOSITE = {UP: DOWN, DOWN: UP, LEFT: RIGHT, RIGHT: LEFT}

# Scorebar at top
SCOREBAR_H  = 10
PLAY_Y0     = (SCOREBAR_H // CELL) + 1   # top playfield row (cells)
PLAY_Y1     = GRID_H - 1                  # bottom (exclusive)
PLAY_X0     = 1
PLAY_X1     = GRID_W - 1

# ---------------------------------------------------------------------------
# Colours (RGB565)
# ---------------------------------------------------------------------------
def rgb(r, g, b):
    return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)

C_BG        = rgb(  0,   0,  10)
C_WALL      = rgb( 30,  30,  30)
C_SCORE_BG  = rgb( 10,  10,  10)
C_P1_HEAD   = rgb(  0, 255, 255)   # cyan
C_P1_TRAIL  = rgb(  0,  90, 130)
C_P2_HEAD   = rgb(255,  80,   0)   # orange
C_P2_TRAIL  = rgb(120,  40,   0)
C_WHITE     = rgb(255, 255, 255)
C_GREEN     = rgb(  0, 255,  80)
C_RED       = rgb(255,  50,  50)
C_YELLOW    = rgb(255, 220,   0)
C_TITLE     = rgb(  0, 210, 255)

# ---------------------------------------------------------------------------
# AI
# ---------------------------------------------------------------------------
def _open_neighbors(grid, x, y):
    """Count open cells immediately surrounding (x, y)."""
    count = 0
    for dx, dy in (UP, DOWN, LEFT, RIGHT):
        nx, ny = x + dx, y + dy
        if (PLAY_X0 <= nx < PLAY_X1 and PLAY_Y0 <= ny < PLAY_Y1
                and grid[ny][nx] == 0):
            count += 1
    return count


def ai_dir(grid, ax, ay, cur_dir):
    """Pick best direction using cheap 2-step lookahead."""
    best_score = -1
    best_dirs = []
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
            best_dirs = [d]
        elif score == best_score:
            best_dirs.append(d)
    return random.choice(best_dirs) if best_dirs else cur_dir


# ---------------------------------------------------------------------------
# Game state
# ---------------------------------------------------------------------------
class Game:
    def __init__(self):
        self.p1_score = 0
        self.p2_score = 0
        self.reset()

    def reset(self):
        self.grid    = [[0] * GRID_W for _ in range(GRID_H)]
        mid_y        = (PLAY_Y0 + PLAY_Y1) // 2
        q1x          = PLAY_X0 + (PLAY_X1 - PLAY_X0) // 4
        q3x          = PLAY_X1 - (PLAY_X1 - PLAY_X0) // 4
        self.p1x, self.p1y, self.p1d = q1x, mid_y, RIGHT
        self.p2x, self.p2y, self.p2d = q3x, mid_y, LEFT
        self.p1_alive = True
        self.p2_alive = True
        self.grid[self.p1y][self.p1x] = 1
        self.grid[self.p2y][self.p2x] = 2
        self.over   = False
        self.result = None   # 'p1', 'p2', 'draw'

    def step(self):
        if self.over:
            return

        # Move P1
        if self.p1_alive:
            nx, ny = self.p1x + self.p1d[0], self.p1y + self.p1d[1]
            if (nx < PLAY_X0 or nx >= PLAY_X1 or
                    ny < PLAY_Y0 or ny >= PLAY_Y1 or
                    self.grid[ny][nx] != 0):
                self.p1_alive = False
            else:
                self.p1x, self.p1y = nx, ny
                self.grid[ny][nx] = 1

        # Move P2 (AI picks direction first)
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


# ---------------------------------------------------------------------------
# Renderer
# ---------------------------------------------------------------------------
class Renderer:
    def __init__(self, p):
        self.p = p

    def cell(self, gx, gy, color):
        self.p.fill_rect(gx * CELL, gy * CELL, CELL, CELL, color)

    def walls(self):
        """Draw border walls."""
        p = self.p
        # top / bottom rows
        for x in range(GRID_W):
            self.cell(x, PLAY_Y0 - 1, C_WALL)
            self.cell(x, PLAY_Y1,     C_WALL)
        # left / right columns
        for y in range(PLAY_Y0, PLAY_Y1):
            self.cell(PLAY_X0 - 1, y, C_WALL)
            self.cell(PLAY_X1,     y, C_WALL)

    def scorebar(self, g):
        p = self.p
        p.fill_rect(0, 0, SCREEN_W, SCOREBAR_H, C_SCORE_BG)
        p.draw_text(4, 1, f"YOU {g.p1_score}", C_P1_HEAD, 1)
        p.draw_text_centered(1, "NEON BIKES", C_TITLE, 1)
        label = f"CPU {g.p2_score}"
        p.draw_text(SCREEN_W - p.text_width(label, 1) - 4, 1, label, C_P2_HEAD, 1)

    def full_draw(self, g):
        self.p.clear(C_BG)
        self.walls()
        for gy in range(PLAY_Y0, PLAY_Y1):
            for gx in range(PLAY_X0, PLAY_X1):
                v = g.grid[gy][gx]
                if v == 1:
                    self.cell(gx, gy, C_P1_TRAIL)
                elif v == 2:
                    self.cell(gx, gy, C_P2_TRAIL)
        self._heads(g)
        self.scorebar(g)

    def delta_draw(self, g, op1, op2):
        """Only repaint the two old head positions + two new heads + scorebar."""
        if op1 and g.p1_alive:
            self.cell(op1[0], op1[1], C_P1_TRAIL)
        if op2 and g.p2_alive:
            self.cell(op2[0], op2[1], C_P2_TRAIL)
        self._heads(g)
        self.scorebar(g)

    def _heads(self, g):
        if g.p1_alive:
            self.p.fill_rect(g.p1x * CELL - 1, g.p1y * CELL - 1,
                             CELL + 2, CELL + 2, C_P1_HEAD)
        if g.p2_alive:
            self.p.fill_rect(g.p2x * CELL - 1, g.p2y * CELL - 1,
                             CELL + 2, CELL + 2, C_P2_HEAD)

    def game_over(self, g):
        result = g.result
        if result == 'p1':
            msg, col = "YOU WIN!", C_GREEN
        elif result == 'p2':
            msg, col = "CPU WINS", C_RED
        else:
            msg, col = "  DRAW  ", C_YELLOW
        bx, by = SCREEN_W // 2 - 72, SCREEN_H // 2 - 20
        self.p.fill_rect(bx, by, 144, 42, rgb(8, 8, 8))
        self.p.draw_rect(bx, by, 144, 42, col)
        self.p.draw_text_centered(by + 5,  msg,             col,     2)
        self.p.draw_text_centered(by + 26, "A=Restart B=Quit", C_WHITE, 1)

    def title(self, p1s, p2s):
        p = self.p
        p.clear(C_BG)
        p.draw_text_centered(15,  "NEON BIKES",       C_TITLE,  4)
        p.draw_text_centered(56,  "LIGHT CYCLE ARENA", rgb(0,160,200), 2)
        p.draw_text_centered(82,  "YOU  vs  CPU",      C_WHITE,  1)
        p.draw_text_centered(96,  "D-PAD = STEER",     rgb(160,160,160), 1)
        p.draw_text_centered(108, "A = START   B = QUIT", rgb(160,160,160), 1)
        p.draw_text_centered(128, f"SCORE   YOU {p1s} : {p2s} CPU", C_WHITE, 1)
        p.draw_text_centered(150, "PRESS A TO PLAY",   C_GREEN,  1)


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------
def run():
    with Pager() as p:
        p.set_rotation(270)
        r = Renderer(p)
        g = Game()

        # --- Title screen ---
        r.title(g.p1_score, g.p2_score)
        p.flip()

        BTN_UP    = Pager.BTN_UP
        BTN_DOWN  = Pager.BTN_DOWN
        BTN_LEFT  = Pager.BTN_LEFT
        BTN_RIGHT = Pager.BTN_RIGHT
        BTN_A     = Pager.BTN_A
        BTN_B     = Pager.BTN_B

        while True:
            _, pressed, _ = p.poll_input()
            if pressed & BTN_B:
                return
            if pressed & BTN_A:
                break
            p.delay(50)

        # --- Main game loop ---
        while True:
            g.reset()
            r.full_draw(g)
            p.flip()

            op1 = op2 = None
            quit_to_title = False

            while not g.over:
                p.delay(30)

                _, pressed, _ = p.poll_input()

                # Steering
                if pressed & BTN_UP    and g.p1d != DOWN:  g.p1d = UP
                if pressed & BTN_DOWN  and g.p1d != UP:    g.p1d = DOWN
                if pressed & BTN_LEFT  and g.p1d != RIGHT: g.p1d = LEFT
                if pressed & BTN_RIGHT and g.p1d != LEFT:  g.p1d = RIGHT

                # Mid-game quit
                if pressed & BTN_B:
                    quit_to_title = True
                    break

                # Advance multiple steps per frame render
                for _ in range(STEPS_PER_FRAME):
                    if g.over:
                        break
                    op1 = (g.p1x, g.p1y) if g.p1_alive else None
                    op2 = (g.p2x, g.p2y) if g.p2_alive else None
                    g.step()
                    r.delta_draw(g, op1, op2)

                p.flip()

            if quit_to_title:
                r.title(g.p1_score, g.p2_score)
                p.flip()
                while True:
                    _, pressed, _ = p.poll_input()
                    if pressed & BTN_A: break
                    if pressed & BTN_B: return
                    p.delay(50)
                continue

            # --- Game over ---
            r.game_over(g)
            p.flip()

            while True:
                _, pressed, _ = p.poll_input()
                if pressed & BTN_A:
                    break   # restart
                if pressed & BTN_B:
                    # Back to title
                    r.title(g.p1_score, g.p2_score)
                    p.flip()
                    while True:
                        _, pressed, _ = p.poll_input()
                        if pressed & BTN_A: break
                        if pressed & BTN_B: return
                        p.delay(50)
                    break
                p.delay(50)


if __name__ == "__main__":
    try:
        run()
    except Exception as e:
        import traceback
        with open("/tmp/neon_bikes_crash.log", "w") as f:
            traceback.print_exc(file=f)
        sys.exit(0)
