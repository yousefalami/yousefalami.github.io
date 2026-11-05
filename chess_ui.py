"""Board UI for the chess page. The rules and the AI are in chess_engine.py."""
import random

from pyodide.ffi import create_proxy
from pyscript import document, window

from chess_engine import BLACK, WHITE, FILES, K, N, B, P, Q, R, Position, best_move

# Solid glyphs for both colours; CSS colours them. The variation selector keeps the
# black pawn from turning into an emoji on some platforms.
GLYPH = {P: "♟︎", N: "♞", B: "♝", R: "♜", Q: "♛", K: "♚"}

pos = Position()
sans = []               # move list in algebraic notation
human = {WHITE: True, BLACK: True}
level = 2
flipped = False
selected = -1
last = None             # last move, to highlight
legal = pos.legal_moves()
result = None           # None while playing, else the outcome tuple
thinking = False
pending = []            # promotion choices waiting for the player

board_el = document.getElementById("board")
status_el = document.getElementById("status")
moves_el = document.getElementById("moves")
promo_el = document.getElementById("promo")
promo_opts = document.getElementById("promo-opts")
undo_btn = document.getElementById("undo")
opp_el, level_el, side_el = (document.getElementById(i) for i in ("opp", "level", "side"))
row_level, row_side = document.getElementById("row-level"), document.getElementById("row-side")

cells = []  # the 64 board elements in screen order (top-left first)


def square_at(k):
    """Board square shown in screen cell k (0 = top-left)."""
    row, col = divmod(k, 8)
    return row * 8 + (7 - col) if flipped else (7 - row) * 8 + col


def build_board():
    for k in range(64):
        cell = document.createElement("div")
        cell.className = "sq"
        cell.dataset.k = str(k)
        cell.addEventListener("click", create_proxy(on_click))
        board_el.appendChild(cell)
        cells.append(cell)


def render():
    check_sq = pos.ksq[pos.turn] if pos.in_check() else -1
    targets = {m[1] for m in legal if m[0] == selected}
    for k, cell in enumerate(cells):
        s = square_at(k)
        f, r = s & 7, s >> 3
        p = pos.board[s]
        cls = "sq" + (" dk" if (f + r) % 2 == 0 else "")
        if p:
            cls += " pw" if p > 0 else " pb"
        if last and s in (last[0], last[1]):
            cls += " last"
        if s == selected:
            cls += " sel"
        if s == check_sq:
            cls += " chk"
        if s in targets:
            cls += " cap" if p else " tgt"
        cell.className = cls
        cell.textContent = GLYPH[abs(p)] if p else ""
        bottom = k >= 56
        left = k % 8 == 0
        if bottom:
            cell.setAttribute("data-file", FILES[f])
        else:
            cell.removeAttribute("data-file")
        if left:
            cell.setAttribute("data-rank", str(r + 1))
        else:
            cell.removeAttribute("data-rank")
    render_moves()
    render_status()


def render_moves():
    moves_el.replaceChildren()
    if not sans:
        span = document.createElement("span")
        span.className = "empty"
        span.textContent = "No moves yet"
        moves_el.appendChild(span)
        return
    for i in range(0, len(sans), 2):
        row = document.createElement("div")
        row.className = "mv"
        for text in (f"{i // 2 + 1}.", sans[i], sans[i + 1] if i + 1 < len(sans) else ""):
            span = document.createElement("span")
            span.textContent = text
            row.appendChild(span)
        moves_el.appendChild(row)
    moves_el.scrollTop = moves_el.scrollHeight


def render_status():
    name = {WHITE: "White", BLACK: "Black"}
    status_el.classList.toggle("over", result is not None)
    if result:
        reason, winner = result
        if winner:
            status_el.textContent = f"Checkmate. {name[winner]} wins!"
        else:
            status_el.textContent = f"Draw by {reason}." if reason != "stalemate" else "Stalemate. It's a draw."
    elif thinking:
        status_el.textContent = "Computer is thinking…"
    else:
        who = name[pos.turn] + " to move"
        if not (human[WHITE] and human[BLACK]):
            who = "Your move" if human[pos.turn] else who
        status_el.textContent = who + (" (check!)" if pos.in_check() else "")
    undo_btn.disabled = thinking or not sans


def refresh():
    global legal, result
    legal = pos.legal_moves()
    result = pos.outcome(legal)
    render()


def finish_move(m):
    global selected, last, thinking
    sans.append(pos.san(m, legal))
    pos.push(m)
    selected, last, thinking = -1, m, False
    refresh()
    if result is None and not human[pos.turn]:
        thinking = True
        render_status()
        undo_btn.disabled = True
        window.setTimeout(ai_proxy, 60)  # let the "thinking" text paint first


def ai_move(*_):
    if result is None and not human[pos.turn]:
        finish_move(best_move(pos, level))


ai_proxy = create_proxy(ai_move)


def on_click(event):
    global selected
    if result or thinking or not human[pos.turn]:
        return
    s = square_at(int(event.currentTarget.dataset.k))
    if selected >= 0:
        options = [m for m in legal if m[0] == selected and m[1] == s]
        if len(options) > 1:  # four promotion choices
            ask_promotion(options)
            return
        if options:
            finish_move(options[0])
            return
    if pos.board[s] * pos.turn > 0 and s != selected:
        selected = s
    else:
        selected = -1
    render()


def ask_promotion(options):
    global pending
    pending = options
    promo_opts.replaceChildren()
    for m in options:
        btn = document.createElement("button")
        btn.type = "button"
        btn.className = "pw" if pos.turn == WHITE else "pb"
        btn.textContent = GLYPH[m[2]]
        btn.setAttribute("aria-label", {Q: "Queen", R: "Rook", B: "Bishop", N: "Knight"}[m[2]])
        btn.addEventListener("click", create_proxy(lambda e, mv=m: choose_promotion(mv)))
        promo_opts.appendChild(btn)
    promo_el.style.display = "flex"


def choose_promotion(m):
    promo_el.style.display = "none"
    finish_move(m)


def cancel_promotion(event):
    global selected
    if event.target == promo_el:
        promo_el.style.display = "none"
        selected = -1
        render()


def sync_controls(*_):
    two = opp_el.value == "two"
    row_level.style.display = "none" if two else "flex"
    row_side.style.display = "none" if two else "flex"


def new_game(*_):
    global pos, sans, human, level, flipped, selected, last, thinking
    pos, sans, selected, last, thinking = Position(), [], -1, None, False
    level = int(level_el.value)
    if opp_el.value == "two":
        human = {WHITE: True, BLACK: True}
        flipped = False
    else:
        side = side_el.value if side_el.value != "random" else random.choice(["white", "black"])
        human = {WHITE: side == "white", BLACK: side == "black"}
        flipped = side == "black"
    refresh()
    if not human[pos.turn]:
        finish_move_ai_first()


def finish_move_ai_first():
    global thinking
    thinking = True
    render_status()
    window.setTimeout(ai_proxy, 60)


def undo(*_):
    global selected, last
    if thinking or not sans:
        return
    while sans:  # against the computer, take back its reply as well
        pos.pop()
        sans.pop()
        if human[pos.turn]:
            break
    selected = -1
    last = None
    refresh()


def flip(*_):
    global flipped
    flipped = not flipped
    render()


build_board()
sync_controls()
document.getElementById("new").addEventListener("click", create_proxy(new_game))
document.getElementById("undo").addEventListener("click", create_proxy(undo))
document.getElementById("flip").addEventListener("click", create_proxy(flip))
opp_el.addEventListener("change", create_proxy(sync_controls))
promo_el.addEventListener("click", create_proxy(cancel_promotion))
new_game()
