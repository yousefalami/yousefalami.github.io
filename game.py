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

BONUS_EVERY = 5       # a golden bonus appears after this many normal foods
BONUS_LIFETIME = 45   # ...and stays for this many steps
BONUS_POINTS = 5
POINTS_PER_LEVEL = 5


class SnakeGame:
    def __init__(self, cols=COLS, rows=ROWS, rng=None, wrap=False):
        self.cols, self.rows = cols, rows
        self.rng = rng or random.Random()
        self.wrap = wrap  # True: the edges connect instead of being walls
        self.reset()

    def reset(self):
        cx, cy = self.cols // 2, self.rows // 2
        self.snake = [(cx, cy), (cx - 1, cy), (cx - 2, cy)]  # head first
        self.direction = "right"
        self.queue = deque()  # buffered turns, so fast key taps are not lost
        self.score = 0
        self.eaten = 0
        self.alive = True
        self.won = False
        self.event = None  # "eat" | "bonus" | "die" | "win" after each step
        self.food = None
        self.bonus = None
        self.bonus_left = 0
        self._place_food()

    @property
    def level(self):
        return 1 + self.score // POINTS_PER_LEVEL

    @property
    def tick_ms(self):
        """Delay between steps; the snake speeds up as the score grows."""
        return max(60, 140 - self.score * 2)

    def turn(self, name):
        """Queue a turn. Reversing straight into the neck is ignored."""
        if name not in DIRS or len(self.queue) >= 2:
            return
        last = self.queue[-1] if self.queue else self.direction
        if name != last and name != OPPOSITE[last]:
            self.queue.append(name)

    def step(self):
        self.event = None
        if not self.alive:
            return
        if self.queue:
            self.direction = self.queue.popleft()
        dx, dy = DIRS[self.direction]
        hx, hy = self.snake[0]
        nx, ny = hx + dx, hy + dy
        if self.wrap:
            nx, ny = nx % self.cols, ny % self.rows
        elif not (0 <= nx < self.cols and 0 <= ny < self.rows):
            return self._die()
        new = (nx, ny)
        grow = new == self.food or new == self.bonus
        # The tail cell is free to enter unless we are growing this step.
        body = self.snake if grow else self.snake[:-1]
        if new in body:
            return self._die()
        self.snake.insert(0, new)
        if not grow:
            self.snake.pop()

        if new == self.food:
            self.score += 1
            self.eaten += 1
            self.event = "eat"
            self._place_food()
            if self.eaten % BONUS_EVERY == 0 and self.bonus is None and not self.won:
                self._place_bonus()
        elif new == self.bonus:
            self.score += BONUS_POINTS
            self.event = "bonus"
            self.bonus = None
        if self.bonus is not None:
            self.bonus_left -= 1
            if self.bonus_left <= 0:
                self.bonus = None

    def _die(self):
        self.alive = False
        self.event = "die"

    def _free_cells(self):
        taken = set(self.snake)
        if self.food:
            taken.add(self.food)
        if self.bonus:
            taken.add(self.bonus)
        return [(x, y) for x in range(self.cols) for y in range(self.rows) if (x, y) not in taken]

    def _place_food(self):
        free = self._free_cells()
        if not free:  # board is full: the player won
            self.food, self.alive, self.won, self.event = None, False, True, "win"
        else:
            self.food = self.rng.choice(free)

    def _place_bonus(self):
        free = self._free_cells()
        if free:
            self.bonus = self.rng.choice(free)
            self.bonus_left = BONUS_LIFETIME


# ---------------------------------------------------------------- Browser UI
try:
    from pyscript import document, window
    from pyodide.ffi import create_proxy
except ImportError:  # plain Python (tests): only the game rules are available
    document = None

if document is not None:
    CELL = 24
    TWO_PI = 6.2832
    KEYS = {
        "ArrowUp": "up", "ArrowDown": "down", "ArrowLeft": "left", "ArrowRight": "right",
        "w": "up", "s": "down", "a": "left", "d": "right",
        "W": "up", "S": "down", "A": "left", "D": "right",
    }

    def storage_get(key, default=""):
        try:
            return window.localStorage.getItem(key) or default
        except Exception:
            return default

    def storage_set(key, value):
        try:
            window.localStorage.setItem(key, str(value))
        except Exception:
            pass

    state = "ready"  # ready | running | paused | over
    timer = None
    sound_on = storage_get("snake-sound", "1") == "1"
    game = SnakeGame(wrap=storage_get("snake-mode", "walls") == "wrap")

    def mode_key():
        return "wrap" if game.wrap else "walls"

    def load_best():
        return int(storage_get("snake-best-" + mode_key(), "0"))

    best = load_best()

    canvas = document.getElementById("board")
    ctx = canvas.getContext("2d")
    overlay = document.getElementById("overlay")
    title_el = document.getElementById("overlay-title")
    hint_el = document.getElementById("overlay-hint")
    score_el = document.getElementById("score")
    best_el = document.getElementById("best")
    level_el = document.getElementById("level")
    mode_btn = document.getElementById("mode")
    sound_btn = document.getElementById("sound")

    # ---- sound (tiny synthesized beeps, no audio files)
    audio = {"ctx": None}

    def beep(freq, dur=0.08, kind="square", delay=0.0, vol=0.05):
        if not sound_on:
            return
        try:
            if audio["ctx"] is None:
                Ctor = window.AudioContext or window.webkitAudioContext
                audio["ctx"] = Ctor.new()
            ac = audio["ctx"]
            osc, gain = ac.createOscillator(), ac.createGain()
            osc.type = kind
            osc.frequency.value = freq
            t0 = ac.currentTime + delay
            gain.gain.setValueAtTime(vol, t0)
            gain.gain.exponentialRampToValueAtTime(0.0001, t0 + dur)
            osc.connect(gain)
            gain.connect(ac.destination)
            osc.start(t0)
            osc.stop(t0 + dur)
        except Exception:
            pass

    def play(event):
        if event == "eat":
            beep(660, 0.07)
        elif event == "bonus":
            for i, f in enumerate((660, 880, 1320)):
                beep(f, 0.09, "triangle", delay=i * 0.07)
        elif event == "die":
            beep(160, 0.35, "sawtooth", vol=0.07)
        elif event == "win":
            for i, f in enumerate((523, 659, 784, 1047)):
                beep(f, 0.14, "triangle", delay=i * 0.1)

    # ---- drawing
    def setup_canvas():
        dpr = window.devicePixelRatio or 1
        size = COLS * CELL
        canvas.width = int(size * dpr)
        canvas.height = int(size * dpr)
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0)

    def css(name):
        style = window.getComputedStyle(document.documentElement)
        return style.getPropertyValue(name).strip()

    def rounded(x, y, w, h, r):
        ctx.beginPath()
        if hasattr(ctx, "roundRect"):
            ctx.roundRect(x, y, w, h, r)
        else:
            ctx.rect(x, y, w, h)
        ctx.fill()

    def draw_snake():
        n = len(game.snake)
        for i in range(n - 1, -1, -1):  # tail first, so the head is drawn on top
            x, y = game.snake[i]
            ctx.globalAlpha = max(0.55, 1 - i * 0.025)
            ctx.fillStyle = css("--head") if i == 0 else css("--snake")
            pad = 1 if i == 0 else 2
            rounded(x * CELL + pad, y * CELL + pad, CELL - 2 * pad, CELL - 2 * pad, 7 if i == 0 else 5)
        ctx.globalAlpha = 1
        # eyes, placed on the side the snake is facing
        hx, hy = game.snake[0]
        dx, dy = DIRS[game.direction]
        cx, cy = hx * CELL + CELL / 2, hy * CELL + CELL / 2
        for side in (-1, 1):
            ex = cx + dx * 5 - dy * side * 5
            ey = cy + dy * 5 + dx * side * 5
            ctx.fillStyle = "#ffffff"
            ctx.beginPath()
            ctx.arc(ex, ey, 3.2, 0, TWO_PI)
            ctx.fill()
            ctx.fillStyle = "#101010"
            ctx.beginPath()
            ctx.arc(ex + dx * 1.2, ey + dy * 1.2, 1.6, 0, TWO_PI)
            ctx.fill()

    def draw_food():
        if game.food:
            fx, fy = game.food
            cx, cy = fx * CELL + CELL / 2, fy * CELL + CELL / 2 + 1
            ctx.fillStyle = css("--food")
            ctx.beginPath()
            ctx.arc(cx, cy, CELL * 0.36, 0, TWO_PI)
            ctx.fill()
            ctx.fillStyle = "rgba(255,255,255,.55)"  # highlight
            ctx.beginPath()
            ctx.arc(cx - 3, cy - 3, 2.6, 0, TWO_PI)
            ctx.fill()
            ctx.fillStyle = css("--head")  # little leaf
            rounded(cx - 1, cy - CELL * 0.5, 5, 4, 2)
        if game.bonus:
            bx, by = game.bonus
            cx, cy = bx * CELL + CELL / 2, by * CELL + CELL / 2
            pulse = 1 + 0.12 * ((game.bonus_left % 6) / 6)
            ctx.fillStyle = css("--bonus")
            ctx.beginPath()
            ctx.arc(cx, cy, CELL * 0.36 * pulse, 0, TWO_PI)
            ctx.fill()
            ctx.strokeStyle = css("--bonus")  # ring shows the time left
            ctx.lineWidth = 2
            ctx.beginPath()
            ctx.arc(cx, cy, CELL * 0.5, -1.5708, -1.5708 + TWO_PI * game.bonus_left / BONUS_LIFETIME)
            ctx.stroke()

    def draw():
        size = COLS * CELL
        ctx.fillStyle = css("--board")
        ctx.fillRect(0, 0, size, size)
        ctx.fillStyle = css("--grid")
        for i in range(1, COLS):  # subtle grid lines
            ctx.fillRect(i * CELL, 0, 1, size)
            ctx.fillRect(0, i * CELL, size, 1)
        if not game.wrap:  # solid border shows that the walls are deadly
            ctx.strokeStyle = css("--wall")
            ctx.lineWidth = 4
            ctx.strokeRect(2, 2, size - 4, size - 4)
        draw_food()
        draw_snake()

    def update_hud():
        score_el.textContent = str(game.score)
        best_el.textContent = str(best)
        level_el.textContent = str(game.level)
        mode_btn.textContent = "Mode: " + ("Wrap-around" if game.wrap else "Walls")
        sound_btn.textContent = "Sound: " + ("On" if sound_on else "Off")
        mode_btn.disabled = state == "running"

    def show_overlay(title, hint):
        title_el.textContent = title
        hint_el.textContent = hint
        overlay.style.display = "flex"

    def hide_overlay():
        overlay.style.display = "none"

    # ---- game loop
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
        play(game.event)
        draw()
        if game.score > best:
            best = game.score
            storage_set("snake-best-" + mode_key(), best)
        if not game.alive:
            state = "over"
            cancel()
            if game.won:
                show_overlay("You win! 🎉", "You filled the whole board. Press Space or tap to play again")
            else:
                new_best = game.score > 0 and game.score == best
                msg = f"Score: {game.score}" + ("  ·  New best!" if new_best else "")
                show_overlay("Game over", msg + "\nPress Space or tap to play again")
        else:
            schedule()
        update_hud()

    tick_proxy = create_proxy(tick)

    def start():
        global state
        game.reset()
        state = "running"
        hide_overlay()
        cancel()
        draw()
        update_hud()
        beep(440, 0.06)
        schedule()

    def toggle_pause():
        global state
        if state == "running":
            state = "paused"
            cancel()
            show_overlay("Paused", "Press Space or tap to resume")
        elif state == "paused":
            state = "running"
            hide_overlay()
            schedule()
        update_hud()

    def primary_action():
        if state in ("ready", "over"):
            start()
        else:
            toggle_pause()

    def toggle_mode(*_):
        global best
        if state == "running":
            return
        game.wrap = not game.wrap
        storage_set("snake-mode", mode_key())
        best = load_best()
        game.reset()
        draw()
        update_hud()

    def toggle_sound(*_):
        global sound_on
        sound_on = not sound_on
        storage_set("snake-sound", "1" if sound_on else "0")
        update_hud()
        beep(660, 0.06)

    # ---- input
    def on_key(event):
        if event.key in (" ", "Enter", "p", "P"):
            event.preventDefault()
            primary_action()
        elif event.key in ("m", "M"):
            toggle_mode()
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

    def on_button(handler):
        def wrapper(event):
            event.currentTarget.blur()  # so Space does not re-click the button
            handler()
        return create_proxy(wrapper)

    def on_blur(*_):
        if state == "running":  # pause when the tab or window loses focus
            toggle_pause()

    setup_canvas()
    document.addEventListener("keydown", create_proxy(on_key))
    window.addEventListener("blur", create_proxy(on_blur))
    canvas.addEventListener("touchstart", create_proxy(on_touch_start))
    canvas.addEventListener("touchend", create_proxy(on_touch_end))
    overlay.addEventListener("click", create_proxy(lambda e: primary_action()))
    mode_btn.addEventListener("click", on_button(toggle_mode))
    sound_btn.addEventListener("click", on_button(toggle_sound))
    for btn in document.querySelectorAll("[data-dir]"):
        btn.addEventListener("click", create_proxy(on_dpad))

    draw()
    update_hud()
    show_overlay("Snake", "Press Space or tap to start\nArrow keys, WASD or swipe to move\nP pauses  ·  M switches mode")
