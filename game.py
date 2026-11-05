"""Snake, written in Python and run in the browser with PyScript (Pyodide).

The game rules live in SnakeGame and know nothing about the browser, so they
can be tested with plain Python. Everything below the "Browser UI" line only
runs when the `pyscript` module is available.
"""
import random
from collections import deque

COLS = ROWS = 20
DIRS = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}
OPPOSITE = {"up": "down", "down": "up", "left": "right", "right": "left"}


class SnakeGame:
    def __init__(self, cols=COLS, rows=ROWS, rng=None):
        self.cols, self.rows = cols, rows
        self.rng = rng or random.Random()
        self.reset()

    def reset(self):
        cx, cy = self.cols // 2, self.rows // 2
        self.snake = [(cx, cy), (cx - 1, cy), (cx - 2, cy)]  # head first
        self.direction = "right"
        self.queue = deque()  # buffered turns, so fast key taps are not lost
        self.score = 0
        self.alive = True
        self.won = False
        self.food = None
        self._place_food()

    def turn(self, name):
        """Queue a turn. Reversing straight into the neck is ignored."""
        if name not in DIRS or len(self.queue) >= 2:
            return
        last = self.queue[-1] if self.queue else self.direction
        if name != last and name != OPPOSITE[last]:
            self.queue.append(name)

    def step(self):
        if not self.alive:
            return
        if self.queue:
            self.direction = self.queue.popleft()
        dx, dy = DIRS[self.direction]
        hx, hy = self.snake[0]
        new = (hx + dx, hy + dy)
        grow = new == self.food
        # The tail cell is free to enter unless we are growing this step.
        body = self.snake if grow else self.snake[:-1]
        if not (0 <= new[0] < self.cols and 0 <= new[1] < self.rows) or new in body:
            self.alive = False
            return
        self.snake.insert(0, new)
        if grow:
            self.score += 1
            self._place_food()
        else:
            self.snake.pop()

    def _place_food(self):
        taken = set(self.snake)
        free = [(x, y) for x in range(self.cols) for y in range(self.rows) if (x, y) not in taken]
        if not free:  # board is full: the player won
            self.food, self.alive, self.won = None, False, True
        else:
            self.food = self.rng.choice(free)

    @property
    def tick_ms(self):
        """Delay between steps; the snake speeds up as the score grows."""
        return max(55, 140 - self.score * 3)


# ---------------------------------------------------------------- Browser UI
try:
    from pyscript import document, window
    from pyodide.ffi import create_proxy
except ImportError:  # plain Python (tests): only the game rules are available
    document = None

if document is not None:
    CELL = 24
    KEYS = {
        "ArrowUp": "up", "ArrowDown": "down", "ArrowLeft": "left", "ArrowRight": "right",
        "w": "up", "s": "down", "a": "left", "d": "right",
        "W": "up", "S": "down", "A": "left", "D": "right",
    }

    game = SnakeGame()
    state = "ready"  # ready | running | paused | over
    timer = None
    best = 0
    try:
        best = int(window.localStorage.getItem("snake-best") or 0)
    except Exception:
        pass

    canvas = document.getElementById("board")
    ctx = canvas.getContext("2d")
    overlay = document.getElementById("overlay")
    title_el = document.getElementById("overlay-title")
    hint_el = document.getElementById("overlay-hint")
    score_el = document.getElementById("score")
    best_el = document.getElementById("best")

    def setup_canvas():
        dpr = window.devicePixelRatio or 1
        size = COLS * CELL
        canvas.width = int(size * dpr)
        canvas.height = int(size * dpr)
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0)

    def css(name):
        style = window.getComputedStyle(document.documentElement)
        return style.getPropertyValue(name).strip()

    def draw():
        size = COLS * CELL
        ctx.fillStyle = css("--board")
        ctx.fillRect(0, 0, size, size)
        ctx.fillStyle = css("--grid")
        for i in range(1, COLS):  # subtle grid lines
            ctx.fillRect(i * CELL, 0, 1, size)
            ctx.fillRect(0, i * CELL, size, 1)
        if game.food:
            fx, fy = game.food
            ctx.fillStyle = css("--food")
            ctx.beginPath()
            ctx.arc(fx * CELL + CELL / 2, fy * CELL + CELL / 2, CELL * 0.34, 0, 6.2832)
            ctx.fill()
        for i, (x, y) in enumerate(game.snake):
            ctx.fillStyle = css("--head") if i == 0 else css("--snake")
            pad = 1 if i == 0 else 2
            ctx.fillRect(x * CELL + pad, y * CELL + pad, CELL - 2 * pad, CELL - 2 * pad)

    def update_scores():
        score_el.textContent = str(game.score)
        best_el.textContent = str(best)

    def show_overlay(title, hint):
        title_el.textContent = title
        hint_el.textContent = hint
        overlay.style.display = "flex"

    def hide_overlay():
        overlay.style.display = "none"

    def schedule():
        global timer
        timer = window.setTimeout(tick_proxy, game.tick_ms)

    def cancel():
        global timer
        if timer is not None:
            window.clearTimeout(timer)
            timer = None

    def tick(*_):
        global state, best
        game.step()
        draw()
        if game.score > best:
            best = game.score
            try:
                window.localStorage.setItem("snake-best", str(best))
            except Exception:
                pass
        update_scores()
        if not game.alive:
            state = "over"
            cancel()
            if game.won:
                show_overlay("بردی! 🎉", "کل صفحه پر شد. برای بازی دوباره Space یا ضربه بزن")
            else:
                show_overlay("باختی", f"امتیاز: {game.score}  ·  برای بازی دوباره Space یا ضربه بزن")
        else:
            schedule()

    tick_proxy = create_proxy(tick)

    def start():
        global state
        game.reset()
        state = "running"
        hide_overlay()
        update_scores()
        draw()
        cancel()
        schedule()

    def toggle_pause():
        global state
        if state == "running":
            state = "paused"
            cancel()
            show_overlay("مکث", "برای ادامه Space یا ضربه بزن")
        elif state == "paused":
            state = "running"
            hide_overlay()
            schedule()

    def primary_action():
        if state in ("ready", "over"):
            start()
        else:
            toggle_pause()

    def on_key(event):
        if event.key == " " or event.key == "Enter":
            event.preventDefault()
            primary_action()
        elif event.key in KEYS:
            event.preventDefault()
            if state == "running":
                game.turn(KEYS[event.key])

    touch = {"x": 0, "y": 0}

    def on_touch_start(event):
        t = event.touches.item(0)
        touch["x"], touch["y"] = t.clientX, t.clientY

    def on_touch_end(event):
        t = event.changedTouches.item(0)
        dx, dy = t.clientX - touch["x"], t.clientY - touch["y"]
        if abs(dx) < 24 and abs(dy) < 24:  # a tap, not a swipe
            primary_action()
        elif state == "running":
            if abs(dx) > abs(dy):
                game.turn("right" if dx > 0 else "left")
            else:
                game.turn("down" if dy > 0 else "up")

    def on_dpad(event):
        if state == "running":
            game.turn(event.currentTarget.dataset.dir)

    setup_canvas()
    document.addEventListener("keydown", create_proxy(on_key))
    canvas.addEventListener("touchstart", create_proxy(on_touch_start))
    canvas.addEventListener("touchend", create_proxy(on_touch_end))
    overlay.addEventListener("click", create_proxy(lambda e: primary_action()))
    for btn in document.querySelectorAll("[data-dir]"):
        btn.addEventListener("click", create_proxy(on_dpad))

    update_scores()
    draw()
    show_overlay("بازی مار", "برای شروع Space یا ضربه بزن  ·  حرکت: جهت‌نماها / WASD / کشیدن انگشت")
