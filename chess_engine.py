"""A small chess engine in pure Python: full rules, move notation and a simple AI.

It knows nothing about the browser, so it can be tested on its own (see the
perft counts in the tests). The board UI lives in chess_ui.py.

Squares are numbered 0..63 with a1 = 0, b1 = 1, ... h1 = 7, a2 = 8, ... h8 = 63.
Pieces are signed integers: white is positive, black is negative.
A move is a tuple (from_square, to_square, promotion_piece_or_0).
"""
import random
import time

WHITE, BLACK = 1, -1
P, N, B, R, Q, K = 1, 2, 3, 4, 5, 6
FILES = "abcdefgh"
START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
LETTER = {N: "N", B: "B", R: "R", Q: "Q", K: "K"}


def square_name(s):
    return FILES[s & 7] + str((s >> 3) + 1)


def _on(f, r):
    return 0 <= f < 8 and 0 <= r < 8


# ---------------------------------------------------------------- lookup tables
KNIGHT_T, KING_T, ORTHO_RAYS, DIAG_RAYS = [], [], [], []
PAWN_ATT = {WHITE: [], BLACK: []}   # squares a pawn of that colour attacks from s
PAWN_FROM = {WHITE: [], BLACK: []}  # squares a pawn of that colour attacks s from
_KN = [(1, 2), (2, 1), (2, -1), (1, -2), (-1, -2), (-2, -1), (-2, 1), (-1, 2)]
_KG = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)]
_OR = [(1, 0), (-1, 0), (0, 1), (0, -1)]
_DG = [(1, 1), (1, -1), (-1, 1), (-1, -1)]


def _rays(f, r, dirs):
    out = []
    for df, dr in dirs:
        ray, ff, rr = [], f + df, r + dr
        while _on(ff, rr):
            ray.append(rr * 8 + ff)
            ff, rr = ff + df, rr + dr
        if ray:
            out.append(ray)
    return out


for _s in range(64):
    _f, _r = _s & 7, _s >> 3
    KNIGHT_T.append([(_r + dr) * 8 + _f + df for df, dr in _KN if _on(_f + df, _r + dr)])
    KING_T.append([(_r + dr) * 8 + _f + df for df, dr in _KG if _on(_f + df, _r + dr)])
    ORTHO_RAYS.append(_rays(_f, _r, _OR))
    DIAG_RAYS.append(_rays(_f, _r, _DG))
    for _c in (WHITE, BLACK):
        PAWN_ATT[_c].append([(_r + _c) * 8 + _f + df for df in (-1, 1) if _on(_f + df, _r + _c)])
        PAWN_FROM[_c].append([(_r - _c) * 8 + _f + df for df in (-1, 1) if _on(_f + df, _r - _c)])

# Castling rights bits: 1 = white kingside, 2 = white queenside, 4 = black kingside, 8 = black queenside.
CASTLE_KEEP = [15] * 64
CASTLE_KEEP[4], CASTLE_KEEP[7], CASTLE_KEEP[0] = 12, 14, 13
CASTLE_KEEP[60], CASTLE_KEEP[63], CASTLE_KEEP[56] = 3, 11, 7


class Position:
    def __init__(self, fen=START_FEN):
        self.set_fen(fen)

    # ---- setup / export
    def set_fen(self, fen):
        parts = fen.split()
        self.board = [0] * 64
        rank, file = 7, 0
        for ch in parts[0]:
            if ch == "/":
                rank, file = rank - 1, 0
            elif ch.isdigit():
                file += int(ch)
            else:
                piece = "pnbrqk".index(ch.lower()) + 1
                self.board[rank * 8 + file] = piece if ch.isupper() else -piece
                file += 1
        self.turn = WHITE if parts[1] == "w" else BLACK
        self.castling = sum(bit for ch, bit in zip("KQkq", (1, 2, 4, 8)) if ch in parts[2])
        self.ep = -1 if parts[3] == "-" else FILES.index(parts[3][0]) + 8 * (int(parts[3][1]) - 1)
        self.halfmove = int(parts[4]) if len(parts) > 4 else 0
        self.fullmove = int(parts[5]) if len(parts) > 5 else 1
        self.ksq = {WHITE: self.board.index(K), BLACK: self.board.index(-K)}
        self.stack = []
        self.keys = [self.key()]

    def to_fen(self):
        rows = []
        for rank in range(7, -1, -1):
            row, empty = "", 0
            for file in range(8):
                p = self.board[rank * 8 + file]
                if p == 0:
                    empty += 1
                    continue
                row += str(empty) if empty else ""
                empty = 0
                ch = "pnbrqk"[abs(p) - 1]
                row += ch.upper() if p > 0 else ch
            rows.append(row + (str(empty) if empty else ""))
        castle = "".join(ch for ch, bit in zip("KQkq", (1, 2, 4, 8)) if self.castling & bit) or "-"
        ep = "-" if self.ep < 0 else square_name(self.ep)
        return f"{'/'.join(rows)} {'w' if self.turn == WHITE else 'b'} {castle} {ep} {self.halfmove} {self.fullmove}"

    def key(self):
        return (tuple(self.board), self.turn, self.castling, self.ep)

    # ---- attacks and move generation
    def attacked(self, s, by):
        """Is square s attacked by a piece of colour `by`?"""
        b = self.board
        for t in PAWN_FROM[by][s]:
            if b[t] == by * P:
                return True
        for t in KNIGHT_T[s]:
            if b[t] == by * N:
                return True
        for t in KING_T[s]:
            if b[t] == by * K:
                return True
        rook, bishop, queen = by * R, by * B, by * Q
        for ray in ORTHO_RAYS[s]:
            for t in ray:
                p = b[t]
                if p:
                    if p == rook or p == queen:
                        return True
                    break
        for ray in DIAG_RAYS[s]:
            for t in ray:
                p = b[t]
                if p:
                    if p == bishop or p == queen:
                        return True
                    break
        return False

    def in_check(self):
        return self.attacked(self.ksq[self.turn], -self.turn)

    def pseudo_moves(self, captures_only=False):
        b, us, moves = self.board, self.turn, []
        promo_rank = 7 if us == WHITE else 0
        start_rank = 1 if us == WHITE else 6
        for s in range(64):
            p = b[s]
            if p * us <= 0:
                continue
            t = abs(p)
            if t == P:
                fwd = s + 8 * us
                if b[fwd] == 0:
                    if (fwd >> 3) == promo_rank:
                        for pr in (Q, R, B, N):
                            moves.append((s, fwd, pr))
                    elif not captures_only:
                        moves.append((s, fwd, 0))
                        if (s >> 3) == start_rank and b[fwd + 8 * us] == 0:
                            moves.append((s, fwd + 8 * us, 0))
                for to in PAWN_ATT[us][s]:
                    if b[to] * us < 0 or to == self.ep:
                        if (to >> 3) == promo_rank:
                            for pr in (Q, R, B, N):
                                moves.append((s, to, pr))
                        else:
                            moves.append((s, to, 0))
            elif t == N or t == K:
                for to in (KNIGHT_T[s] if t == N else KING_T[s]):
                    q = b[to]
                    if q * us <= 0 and (q or not captures_only):
                        moves.append((s, to, 0))
                if t == K and not captures_only:
                    self._castling_moves(s, us, moves)
            else:
                rays = []
                if t != B:
                    rays += ORTHO_RAYS[s]
                if t != R:
                    rays += DIAG_RAYS[s]
                for ray in rays:
                    for to in ray:
                        q = b[to]
                        if q == 0:
                            if not captures_only:
                                moves.append((s, to, 0))
                            continue
                        if q * us < 0:
                            moves.append((s, to, 0))
                        break
        return moves

    def _castling_moves(self, s, us, moves):
        b = self.board
        home = 4 if us == WHITE else 60
        if s != home:
            return
        ks, qs = (1, 2) if us == WHITE else (4, 8)
        rook = us * R
        them = -us
        if self.castling & ks and b[home + 1] == 0 and b[home + 2] == 0 and b[home + 3] == rook:
            if not self.attacked(home, them) and not self.attacked(home + 1, them):
                moves.append((home, home + 2, 0))
        if self.castling & qs and b[home - 1] == 0 and b[home - 2] == 0 and b[home - 3] == 0 and b[home - 4] == rook:
            if not self.attacked(home, them) and not self.attacked(home - 1, them):
                moves.append((home, home - 2, 0))

    def legal_moves(self, captures_only=False):
        us, res = self.turn, []
        for m in self.pseudo_moves(captures_only):
            self.make(m)
            if not self.attacked(self.ksq[us], -us):
                res.append(m)
            self.undo()
        return res

    # ---- making and unmaking moves
    def make(self, m):
        fr, to, pr = m
        b, us = self.board, self.turn
        p, cap, cap_sq = b[fr], b[to], to
        t = abs(p)
        if t == P and to == self.ep and (fr & 7) != (to & 7):  # en passant capture
            cap_sq = to - 8 * us
            cap = b[cap_sq]
            b[cap_sq] = 0
        self.stack.append((m, p, cap, cap_sq, self.castling, self.ep, self.halfmove))
        b[to] = us * pr if pr else p
        b[fr] = 0
        if t == K:
            self.ksq[us] = to
            if to - fr == 2:      # kingside: rook h -> f
                b[fr + 1], b[fr + 3] = b[fr + 3], 0
            elif fr - to == 2:    # queenside: rook a -> d
                b[fr - 1], b[fr - 4] = b[fr - 4], 0
        self.castling &= CASTLE_KEEP[fr] & CASTLE_KEEP[to]
        self.ep = (fr + to) // 2 if t == P and abs(to - fr) == 16 else -1
        self.halfmove = 0 if (t == P or cap) else self.halfmove + 1
        if us == BLACK:
            self.fullmove += 1
        self.turn = -us

    def undo(self):
        m, p, cap, cap_sq, castling, ep, half = self.stack.pop()
        fr, to, _ = m
        b = self.board
        self.turn = us = -self.turn
        if us == BLACK:
            self.fullmove -= 1
        b[fr] = p
        b[to] = 0
        b[cap_sq] = cap
        if abs(p) == K:
            self.ksq[us] = fr
            if to - fr == 2:
                b[fr + 3], b[fr + 1] = b[fr + 1], 0
            elif fr - to == 2:
                b[fr - 4], b[fr - 1] = b[fr - 1], 0
        self.castling, self.ep, self.halfmove = castling, ep, half

    # ---- game-level helpers (these also track repetition)
    def push(self, m):
        self.make(m)
        self.keys.append(self.key())

    def pop(self):
        self.undo()
        self.keys.pop()

    def insufficient_material(self):
        minors, bishops_on = [], set()
        for s, p in enumerate(self.board):
            t = abs(p)
            if t in (P, R, Q):
                return False
            if t == N or t == B:
                minors.append(t)
                if t == B:
                    bishops_on.add(((s & 7) + (s >> 3)) & 1)
        if len(minors) <= 1:
            return True
        return all(t == B for t in minors) and len(bishops_on) == 1  # bishops all on one colour

    def outcome(self, legal=None):
        """None while the game goes on, else (reason, winner) with winner WHITE, BLACK or 0."""
        legal = self.legal_moves() if legal is None else legal
        if not legal:
            return ("checkmate", -self.turn) if self.in_check() else ("stalemate", 0)
        if self.insufficient_material():
            return ("insufficient material", 0)
        if self.halfmove >= 100:
            return ("fifty-move rule", 0)
        if self.keys.count(self.keys[-1]) >= 3:
            return ("threefold repetition", 0)
        return None

    def san(self, m, legal=None):
        """Standard algebraic notation of a legal move in the current position."""
        fr, to, pr = m
        p = self.board[fr]
        t = abs(p)
        if t == K and abs(to - fr) == 2:
            text = "O-O" if to > fr else "O-O-O"
        else:
            capture = self.board[to] != 0 or (t == P and to == self.ep and (fr & 7) != (to & 7))
            if t == P:
                text = (FILES[fr & 7] + "x" if capture else "") + square_name(to)
                if pr:
                    text += "=" + LETTER[pr]
            else:
                legal = self.legal_moves() if legal is None else legal
                rivals = [o[0] for o in legal if o[1] == to and o[0] != fr and abs(self.board[o[0]]) == t]
                tag = ""
                if rivals:
                    if all((r & 7) != (fr & 7) for r in rivals):
                        tag = FILES[fr & 7]
                    elif all((r >> 3) != (fr >> 3) for r in rivals):
                        tag = str((fr >> 3) + 1)
                    else:
                        tag = square_name(fr)
                text = LETTER[t] + tag + ("x" if capture else "") + square_name(to)
        self.make(m)
        if self.attacked(self.ksq[self.turn], -self.turn):
            text += "#" if not self.legal_moves() else "+"
        self.undo()
        return text


def perft(pos, depth):
    """Count leaf positions; the standard way to verify a move generator."""
    if depth == 0:
        return 1
    total = 0
    for m in pos.legal_moves():
        pos.make(m)
        total += perft(pos, depth - 1)
        pos.undo()
    return total


# ------------------------------------------------------------------------ AI
VALUE = {P: 100, N: 320, B: 330, R: 500, Q: 900, K: 0}
MATE = 100000


def evaluate(pos):
    """Static score in centipawns from the side to move's point of view."""
    score, non_pawn = 0, 0
    for s, p in enumerate(pos.board):
        if not p:
            continue
        t = abs(p)
        if t == K:
            continue
        f, r = s & 7, s >> 3
        centre = min(f, 7 - f) + min(r, 7 - r)  # 0 at the edge .. 6 in the middle
        v = VALUE[t]
        if t == P:
            advanced = r if p > 0 else 7 - r
            v += 6 * advanced + (8 if f in (3, 4) and 1 < advanced < 6 else 0)
        else:
            non_pawn += VALUE[t]
            if t == N:
                v += 7 * centre
            elif t == B:
                v += 4 * centre
            elif t == Q:
                v += 1 * centre
            elif t == R:
                v += 6 if (r == 6 if p > 0 else r == 1) else 0
        score += v if p > 0 else -v
    endgame = non_pawn < 1400
    for colour in (WHITE, BLACK):
        ks = pos.ksq[colour]
        f, r = ks & 7, ks >> 3
        centre = min(f, 7 - f) + min(r, 7 - r)
        home = r if colour == WHITE else 7 - r
        k = 8 * centre if endgame else (14 if home == 0 else -12 * home) + (10 if f in (1, 2, 6) and home == 0 else 0)
        score += colour * k
    return score * pos.turn


class _Timeout(Exception):
    pass


class _Search:
    def __init__(self, pos, deadline):
        self.pos, self.deadline, self.nodes = pos, deadline, 0

    def order(self, moves):
        b = self.pos.board

        def score(m):
            fr, to, pr = m
            s = 0
            if b[to]:
                s += 10 * VALUE[abs(b[to])] - VALUE[abs(b[fr])] // 10 + 1000
            elif abs(b[fr]) == P and (fr & 7) != (to & 7):
                s += 1000 + 900
            if pr:
                s += VALUE[pr]
            return -s
        return sorted(moves, key=score)

    def tick(self):
        self.nodes += 1
        if not self.nodes & 127 and time.time() > self.deadline:
            raise _Timeout

    def quiesce(self, alpha, beta, depth):
        self.tick()
        stand = evaluate(self.pos)
        if stand >= beta:
            return stand
        alpha = max(alpha, stand)
        if depth >= 4:
            return stand
        pos = self.pos
        for m in self.order(pos.pseudo_moves(captures_only=True)):
            us = pos.turn
            pos.make(m)
            if pos.attacked(pos.ksq[us], -us):
                pos.undo()
                continue
            score = -self.quiesce(-beta, -alpha, depth + 1)
            pos.undo()
            if score >= beta:
                return score
            alpha = max(alpha, score)
        return alpha

    def negamax(self, depth, alpha, beta, ply):
        self.tick()
        pos = self.pos
        if depth <= 0:
            return self.quiesce(alpha, beta, 0)
        moves = pos.legal_moves()
        if not moves:
            return -MATE + ply if pos.in_check() else 0
        if pos.halfmove >= 100:
            return 0
        best = -MATE - 1
        for m in self.order(moves):
            pos.make(m)
            score = -self.negamax(depth - 1, -beta, -alpha, ply + 1)
            pos.undo()
            if score > best:
                best = score
            alpha = max(alpha, score)
            if alpha >= beta:
                break
        return best


# level -> (maximum depth, seconds per move)
LEVELS = {1: (1, 0.3), 2: (2, 1.0), 3: (4, 2.5)}


def best_move(pos, level=2, rng=random):
    """Pick a move for the side to move. Higher levels search deeper within a time limit."""
    max_depth, seconds = LEVELS[level]
    moves = pos.legal_moves()
    if len(moves) == 1:
        return moves[0]
    base = len(pos.stack)
    search = _Search(pos, time.time() + seconds)
    if level == 1:  # beginner: pick randomly among reasonable moves
        search.deadline = float("inf")
        scored = []
        for m in moves:
            pos.make(m)
            scored.append((-search.negamax(0, -MATE, MATE, 1), m))
            pos.undo()
        top = max(s for s, _ in scored)
        return rng.choice([m for s, m in scored if s >= top - 90])
    best, root = moves[0], search.order(moves)
    for depth in range(1, max_depth + 1):
        try:
            alpha, found, ordered = -MATE - 1, None, []
            for m in root:
                pos.make(m)
                score = -search.negamax(depth - 1, -MATE, -alpha, 1)
                pos.undo()
                ordered.append((score, m))
                if score > alpha:
                    alpha, found = score, m
        except _Timeout:
            while len(pos.stack) > base:  # put back the half-searched line
                pos.undo()
            break
        best = found
        root = [m for _, m in sorted(ordered, key=lambda x: -x[0])]
        if alpha > MATE - 100:  # forced mate found, no need to look deeper
            break
    return best
