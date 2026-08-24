import os
import random
import tomllib
from contextlib import asynccontextmanager, contextmanager
from datetime import date

import psycopg2
import psycopg2.pool
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# ---------------------------------------------------------------------------
# Paths & config
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
STATIC_DIR = os.path.join(BASE_DIR, "static")

with open(os.path.join(BASE_DIR, "config.toml"), "rb") as f:
    config = tomllib.load(f)

_creds = config["credentials"]
DB_CONFIG = {
    "host": _creds["host"],
    "dbname": _creds["dbname"],
    "user": _creds["username"],
    "password": _creds["password"],
}
FIRST_TRY_MESSAGES = {int(k): v for k, v in config.get("first_try_messages", {}).items()}

# ---------------------------------------------------------------------------
# In-memory game state
# ---------------------------------------------------------------------------
CURRENT_WORD: str | None = None   # set by admin via /updateword
CURRENT_HINT: str = ""
WORD_SET_DATE: date | None = None  # the date the current word was set
ADMIN_PIN = "76420"

# ---------------------------------------------------------------------------
# Colors
# ---------------------------------------------------------------------------
CORRECT = "#008000"    # green
PRESENT = "#c9b458"    # yellow
ABSENT = "#3a3a3c"     # dark gray
DEFAULT_KEYBOARD = "transparent"

# Keyboard rows in display order
KEYBOARD_ROWS = [
    "QWERTYUIOP",
    "ASDFGHJKL",
    "ZXCVBNM",
]


# ---------------------------------------------------------------------------
# Database pool + helpers
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.pool = psycopg2.pool.ThreadedConnectionPool(
        minconn=1,
        maxconn=5,
        **DB_CONFIG,
    )
    yield
    app.state.pool.closeall()


app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)


@contextmanager
def get_conn(request: Request):
    """Borrow a connection from the pool, return it on exit."""
    conn = request.app.state.pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        request.app.state.pool.putconn(conn)


def load_valid_words() -> set:
    words = set()
    with open(os.path.join(BASE_DIR, "WORDS.txt"), "r", encoding="utf-8") as f:
        for line in f:
            w = line.strip().upper()
            if w:
                words.add(w)
    return words


def fetch_current_word(conn) -> str:
    with conn.cursor() as cur:
        cur.execute("SELECT word_of_day FROM WORDLE LIMIT 1")
        row = cur.fetchone()
        return row[0].upper() if row and row[0] else ""


def fetch_attempts(conn, ip: str, target_date) -> list:
    """Return list of attempts (guess strings) for ip on the given date."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT attempt_1, attempt_2, attempt_3, attempt_4, attempt_5, attempt_6 "
            "FROM WORDLE WHERE ip_address = %s AND attempt_date = %s",
            (ip, target_date),
        )
        row = cur.fetchone()
    if not row:
        return []
    return [v for v in row if v is not None]


def record_guess(conn, ip: str, guess: str, target_date, word_of_day: str) -> None:
    """Insert a new row or fill the next attempt_N slot for ip on target_date."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT attempt_1, attempt_2, attempt_3, attempt_4, attempt_5, attempt_6 "
            "FROM WORDLE WHERE ip_address = %s AND attempt_date = %s",
            (ip, target_date),
        )
        row = cur.fetchone()
        if row is None:
            cur.execute(
                "INSERT INTO WORDLE "
                "(ip_address, attempts, attempt_1, attempt_date, word_of_day) "
                "VALUES (%s, 1, %s, %s, %s)",
                (ip, guess, target_date, word_of_day),
            )
        else:
            attempts = [v for v in row if v is not None]
            next_index = len(attempts) + 1
            if next_index > 6:
                return
            cur.execute(
                f"UPDATE WORDLE SET attempt_{next_index} = %s, attempts = %s "
                "WHERE ip_address = %s AND attempt_date = %s",
                (guess, next_index, ip, target_date),
            )


# ---------------------------------------------------------------------------
# Color logic (backend)
# ---------------------------------------------------------------------------
def color_guess(guess: str, answer: str) -> list:
    """Return list of (letter, color) for a single guess."""
    result = []
    answer_chars = list(answer)
    guess_chars = list(guess)
    # first pass: exact matches
    marks = [False] * len(guess_chars)
    for i, g in enumerate(guess_chars):
        if i < len(answer_chars) and g == answer_chars[i]:
            result.append((g, CORRECT))
            marks[i] = True
        else:
            result.append((g, None))  # placeholder, resolved below
    # second pass: present (yellow)
    remaining = [c for i, c in enumerate(answer_chars) if not (
        i < len(guess_chars) and guess_chars[i] == c
    )]
    for i, g in enumerate(guess_chars):
        if marks[i]:
            continue
        if g in remaining:
            result[i] = (g, PRESENT)
            remaining.remove(g)
        else:
            result[i] = (g, ABSENT)
    return result


def build_keyboard(attempts: list, answer: str) -> list:
    """Return keyboard rows; letters that have been tried are highlighted green."""
    tried = set()
    for attempt in attempts:
        tried.update(attempt)
    rows = []
    for row in KEYBOARD_ROWS:
        rows.append([(ch, CORRECT if ch in tried else DEFAULT_KEYBOARD) for ch in row])
    return rows


def get_streak(conn, ip: str) -> int:
    """Count consecutive days (ending today or yesterday) where the user won."""
    from datetime import timedelta
    streak = 0
    check_date = date.today()
    # If they haven't won today yet, start checking from yesterday
    with conn.cursor() as cur:
        cur.execute(
            "SELECT won FROM WORDLE WHERE ip_address = %s AND attempt_date = %s",
            (ip, check_date),
        )
        row = cur.fetchone()
    if row and row[0]:
        streak = 1
        check_date = check_date - timedelta(days=1)
    else:
        check_date = check_date - timedelta(days=1)

    while True:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT won FROM WORDLE WHERE ip_address = %s AND attempt_date = %s",
                (ip, check_date),
            )
            row = cur.fetchone()
        if row and row[0]:
            streak += 1
            check_date = check_date - timedelta(days=1)
        else:
            break
    return streak


def render_game(request: Request, ip: str, target_date,
                result_message: str = "", result_color: str = "",
                just_won: bool = False, invalid_guess: bool = False):
    answer = CURRENT_WORD or ""
    with get_conn(request) as conn:
        attempts = fetch_attempts(conn, ip, target_date)
        streak = get_streak(conn, ip)

    won = len(attempts) >= 1 and attempts[-1] == answer
    if won and not result_message:
        result_message = "You got it! 🎉"
        result_color = CORRECT

    attempts_display = [color_guess(a, answer) for a in attempts]
    keyboard_rows = build_keyboard(attempts, answer)
    show_rules = len(attempts) == 0

    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "attempts": attempts_display,
            "keyboard_rows": keyboard_rows,
            "show_rules": show_rules,
            "won": won,
            "result_message": result_message,
            "result_color": result_color,
            "hint": CURRENT_HINT,
            "correct_color": CORRECT,
            "absent_color": ABSENT,
            "streak": streak,
            "just_won": just_won,
            "invalid_guess": invalid_guess,
        },
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    if CURRENT_WORD is None or WORD_SET_DATE != date.today():
        return RedirectResponse(url="/updateword", status_code=302)
    ip = request.client.host if request.client else "unknown"
    return render_game(request, ip, date.today())


@app.post("/guess")
def guess(request: Request, guess: str = Form(...)):
    if CURRENT_WORD is None or WORD_SET_DATE != date.today():
        return RedirectResponse(url="/updateword", status_code=302)
    ip = request.client.host if request.client else "unknown"
    guess = guess.strip().upper()

    result_message = ""
    result_color = ""
    answer = CURRENT_WORD

    just_won = False
    invalid_guess = False

    with get_conn(request) as conn:
        valid_words = load_valid_words()
        attempts = fetch_attempts(conn, ip, date.today())

        if guess not in valid_words:
            result_message = "Not a valid word, try again!"
            result_color = "#e11d48"
            invalid_guess = True
        elif len(attempts) >= 6:
            pass  # out of tries, nothing recorded
        else:
            first_try = len(attempts) == 0
            record_guess(conn, ip, guess, date.today(), answer)
            if guess == answer:
                result_color = CORRECT
                just_won = True
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE WORDLE SET won = true "
                        "WHERE ip_address = %s AND attempt_date = %s",
                        (ip, date.today()),
                    )
                if first_try and FIRST_TRY_MESSAGES:
                    result_message = random.choice(list(FIRST_TRY_MESSAGES.values()))
                else:
                    result_message = "You got it! 🎉"

    return render_game(request, ip, date.today(), result_message, result_color,
                       just_won=just_won, invalid_guess=invalid_guess)


# In-memory admin auth (per-IP, resets daily)
ADMIN_AUTH_IPS: set[str] = set()
ADMIN_AUTH_DATE: date | None = None


def _check_daily_reset() -> None:
    """Reset auth IPs if the date has changed."""
    global ADMIN_AUTH_IPS, ADMIN_AUTH_DATE
    today = date.today()
    if ADMIN_AUTH_DATE != today:
        ADMIN_AUTH_IPS.clear()
        ADMIN_AUTH_DATE = today


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _is_admin(request: Request) -> bool:
    _check_daily_reset()
    return _client_ip(request) in ADMIN_AUTH_IPS


@app.get("/updateword", response_class=HTMLResponse)
def updateword_form(request: Request):
    _check_daily_reset()
    return templates.TemplateResponse(
        request,
        "updateword.html",
        {"authenticated": _is_admin(request), "error": ""},
    )


@app.post("/updateword")
def updateword_submit(request: Request,
                      pin: str = Form(""),
                      new_word: str = Form(""),
                      new_hint: str = Form("")):
    global CURRENT_WORD, CURRENT_HINT, WORD_SET_DATE

    _check_daily_reset()
    ip = _client_ip(request)

    # If this IP is not yet authenticated, check the PIN
    if ip not in ADMIN_AUTH_IPS:
        if pin.strip() == ADMIN_PIN:
            ADMIN_AUTH_IPS.add(ip)
            ADMIN_AUTH_DATE = date.today()
            # Re-render with the word form
            return templates.TemplateResponse(
                request,
                "updateword.html",
                {"authenticated": True, "error": ""},
            )
        else:
            return templates.TemplateResponse(
                request,
                "updateword.html",
                {"authenticated": False, "error": "Incorrect PIN. Try again."},
            )

    # Authenticated: set the word
    new_word = new_word.strip().upper()
    if len(new_word) != 5 or not new_word.isalpha():
        return templates.TemplateResponse(
            request,
            "updateword.html",
            {"authenticated": True, "error": "Word must be exactly 5 letters."},
        )

    CURRENT_WORD = new_word
    CURRENT_HINT = new_hint.strip()
    WORD_SET_DATE = date.today()

    return RedirectResponse(url="/", status_code=303)


@app.get("/changeword", response_class=HTMLResponse)
def changeword(request: Request):
    return RedirectResponse(url="/updateword", status_code=302)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)