# yousefalami.github.io

Personal site of Yousef Alami, hosted on GitHub Pages: **https://yousefalami.github.io/**

It is a small collection of games written in **Python** that run directly in the browser with
[PyScript](https://pyscript.net) (Pyodide). There is no server and no build step: the Python files
are served as they are and executed on the visitor's machine.

## What is here

| Page | What it is |
| --- | --- |
| [`index.html`](index.html) + [`game.py`](game.py) | **Snake.** Walls or wrap-around mode, golden bonus food, levels, sound, a player name and a local leaderboard. |
| [`chess.html`](chess.html) + [`chess_ui.py`](chess_ui.py) + [`chess_engine.py`](chess_engine.py) | **Chess.** Full rules, move list in algebraic notation, a computer opponent with three levels, or two players on one device. |
| [`tests/`](tests) | Unit tests for the Snake rules and the chess engine. They are not part of the published site. |

### How the code is organised

- The game rules are plain Python with no browser dependency (`SnakeGame` in `game.py`, `Position` and
  `best_move` in `chess_engine.py`), so they can be tested with ordinary Python.
- Only the UI part imports `pyscript`; in `game.py` it is guarded so the file can also be imported
  outside the browser.
- The chess move generator is checked with standard perft counts (start position, "Kiwipete" and
  three other well-known test positions).

## Tests

The tests use only Python's standard library. From the repository root:

```bash
python3 -m unittest discover -s tests -v
```

They cover the Snake rules and score history, and the chess engine: perft counts, move notation,
checkmate / stalemate / draw detection, and the computer opponent (finds a mate in one, takes a
hanging queen, leaves the position unchanged after searching).

## Run it locally

PyScript fetches the `.py` files over HTTP, so opening `index.html` by double-clicking (a `file://`
address) does not work. Start a tiny server instead:

```bash
python3 -m http.server 8000
```

Then open <http://localhost:8000>. The first load takes a few seconds while Python starts, and the
page needs internet access to download PyScript from its CDN.

## Notes

- Scores and the saved player name are stored in the visitor's own browser (`localStorage`). They are
  not shared between devices.
- The computer's thinking time in chess is limited (up to 2.5 s at the strongest level), and the page
  is unresponsive while it thinks.

## License

[MIT](LICENSE) © 2026 Yousef Alami
