#!/usr/bin/env python3
# VTOS — Vibecoded Terminal Operating System
# Python terminal environment for Linux

import curses
import os
import sys
import time
import shutil
import socket
import subprocess
import platform
import ast
import operator
from pathlib import Path

try:
    import psutil
except ImportError:
    psutil = None

VERSION = "1.0"
HOME = Path.home()
CONFIG = HOME / ".config" / "vtos"
DATA = HOME / ".local" / "share" / "vtos"
NOTES = DATA / "notes.txt"

CONFIG.mkdir(parents=True, exist_ok=True)
DATA.mkdir(parents=True, exist_ok=True)

# ─────────────────────────────────────────────
# Colors
# ─────────────────────────────────────────────

THEMES = {
    "cyan": {
        "accent": curses.COLOR_CYAN,
        "secondary": curses.COLOR_BLUE,
    },
    "green": {
        "accent": curses.COLOR_GREEN,
        "secondary": curses.COLOR_CYAN,
    },
    "magenta": {
        "accent": curses.COLOR_MAGENTA,
        "secondary": curses.COLOR_BLUE,
    },
    "amber": {
        "accent": curses.COLOR_YELLOW,
        "secondary": curses.COLOR_RED,
    },
}

theme_name = "cyan"


def init_colors():
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_WHITE, -1)
    curses.init_pair(2, curses.COLOR_BLACK, curses.COLOR_CYAN)
    curses.init_pair(3, curses.COLOR_CYAN, -1)
    curses.init_pair(4, curses.COLOR_GREEN, -1)
    curses.init_pair(5, curses.COLOR_YELLOW, -1)
    curses.init_pair(6, curses.COLOR_RED, -1)
    curses.init_pair(7, curses.COLOR_MAGENTA, -1)
    curses.init_pair(8, curses.COLOR_BLUE, -1)


def accent():
    return 3 if theme_name == "cyan" else (
        4 if theme_name == "green" else
        7 if theme_name == "magenta" else 5
    )


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def safe_add(win, y, x, text, color=1):
    try:
        height, width = win.getmaxyx()
        if y < height and x < width:
            win.addstr(y, x, str(text)[:max(0, width - x - 1)],
                       curses.color_pair(color))
    except curses.error:
        pass


def center(win, y, text, color=1):
    try:
        _, width = win.getmaxyx()
        x = max(0, (width - len(str(text))) // 2)
        safe_add(win, y, x, text, color)
    except Exception:
        pass


def box(win, title="", color=None):
    if color is None:
        color = accent()

    try:
        win.attron(curses.color_pair(color))
        win.border()
        if title:
            safe_add(win, 0, 2, f" {title} ", color)
        win.attroff(curses.color_pair(color))
    except curses.error:
        pass


def wait_key(win, message="Press any key to continue"):
    h, w = win.getmaxyx()
    safe_add(win, h - 2, 2, message, 5)
    win.refresh()
    win.getch()


def clear(win):
    win.erase()
    win.refresh()


def header(win, title):
    win.erase()
    h, w = win.getmaxyx()

    safe_add(win, 0, 2, f" VTOS {VERSION} ", accent())
    safe_add(win, 0, max(2, w - len(title) - 4), title, 7)

    try:
        win.hline(1, 1, curses.ACS_HLINE, w - 2)
    except curses.error:
        pass


def prompt(win, message):
    h, w = win.getmaxyx()

    safe_add(win, h - 3, 2, message, 5)
    safe_add(win, h - 2, 2, "> ", 4)

    curses.echo()
    curses.curs_set(1)

    try:
        result = win.getstr(h - 2, 4, max(1, w - 6)).decode(
            "utf-8", errors="replace"
        )
    except Exception:
        result = ""

    curses.noecho()
    curses.curs_set(0)

    return result


def run_external(win, command):
    """Temporarily leave curses to run an external command."""
    try:
        curses.def_prog_mode()
        curses.endwin()

        subprocess.run(command, shell=True)

        input("\nPress Enter to return to VTOS...")
    except Exception as e:
        print(f"Error: {e}")
        input("Press Enter...")
    finally:
        curses.reset_prog_mode()
        curses.curs_set(0)
        win.clear()
        win.refresh()


def get_terminal_size(win):
    return win.getmaxyx()


def bar(value, maximum, length=20):
    if maximum <= 0:
        return "░" * length

    filled = int((value / maximum) * length)
    filled = min(length, max(0, filled))

    return "█" * filled + "░" * (length - filled)


# ─────────────────────────────────────────────
# Dashboard
# ─────────────────────────────────────────────

def dashboard(win):
    while True:
        win.erase()
        h, w = win.getmaxyx()

        center(win, 2, "██╗   ██╗████████╗ ██████╗ ███████╗", 3)
        center(win, 3, "██║   ██║╚══██╔══╝██╔═══██╗██╔════╝", 3)
        center(win, 4, "██║   ██║   ██║   ██║   ██║███████╗", 3)
        center(win, 5, "██║   ██║   ██║   ██║   ██║╚════██║", 3)
        center(win, 6, "╚██████╔╝   ██║   ╚██████╔╝███████║", 3)
        center(win, 7, " ╚═════╝    ╚═╝    ╚═════╝ ╚══════╝", 3)
        center(win, 8, "Vibecoded Terminal Operating System", 7)

        try:
            win.hline(10, 2, curses.ACS_HLINE, w - 4)
        except curses.error:
            pass

        center(win, 12, f"USER: {os.getenv('USER', 'user')}", 4)
        center(win, 13, f"HOST: {platform.node()}", 1)
        center(win, 14, f"OS: {platform.system()} {platform.release()}", 1)
        center(win, 15, f"PYTHON: {platform.python_version()}", 1)
        center(win, 16, f"TIME: {time.strftime('%H:%M:%S')}", 5)
        center(win, 17, f"DATE: {time.strftime('%d.%m.%Y')}", 5)

        center(win, 19, "Press any key to open VTOS", 4)
        center(win, 21, "UNICODE  •  COLOR  •  TERMINAL", 7)

        win.refresh()
        win.getch()
        return


# ─────────────────────────────────────────────
# File manager
# ─────────────────────────────────────────────

def file_manager(win):
    current = Path.cwd()
    selected = 0
    scroll = 0

    while True:
        win.erase()
        h, w = win.getmaxyx()

        safe_add(win, 0, 2, " FILE MANAGER ", accent())
        safe_add(win, 1, 2, str(current), 5)

        try:
            items = sorted(
                current.iterdir(),
                key=lambda p: (not p.is_dir(), p.name.lower())
            )
        except PermissionError:
            items = []

        entries = [Path("..")] + items
        selected = max(0, min(selected, len(entries) - 1))

        list_height = max(1, h - 5)

        if selected >= scroll + list_height:
            scroll = selected - list_height + 1
        if selected < scroll:
            scroll = selected

        for i, item in enumerate(entries[scroll:scroll + list_height]):
            idx = i + scroll
            y = 3 + i

            if item.name == "..":
                name = "↰  Parent directory"
                is_dir = True
            else:
                is_dir = item.is_dir()
                name = ("📁 " if is_dir else "📄 ") + item.name

            color = 2 if idx == selected else (4 if is_dir else 1)
            safe_add(win, y, 2, name, color)

        safe_add(win, h - 2, 2,
                 "↑↓ Navigate  ENTER Open  BACKSPACE Up  q Exit", 5)

        win.refresh()
        key = win.getch()

        if key in (ord("q"), 27):
            return

        elif key in (curses.KEY_UP, ord("k")):
            selected = max(0, selected - 1)

        elif key in (curses.KEY_DOWN, ord("j")):
            selected = min(len(entries) - 1, selected + 1)

        elif key in (curses.KEY_BACKSPACE, 127, 8):
            current = current.parent
            selected = 0
            scroll = 0

        elif key in (10, 13, curses.KEY_ENTER):
            item = entries[selected]

            if item.name == "..":
                current = current.parent
                selected = 0
                scroll = 0
                continue

            target = current / item

            if target.is_dir():
                current = target
                selected = 0
                scroll = 0

            else:
                try:
                    if target.stat().st_size > 2_000_000:
                        run_external(win, f"less {shlex_quote(str(target))}")
                    else:
                        text = target.read_text(errors="replace")
                        text_viewer(win, target.name, text)
                except Exception as e:
                    win.erase()
                    center(win, 5, f"Cannot open file: {e}", 6)
                    wait_key(win)


def shlex_quote(text):
    import shlex
    return shlex.quote(text)


# ─────────────────────────────────────────────
# Text viewer
# ─────────────────────────────────────────────

def text_viewer(win, title, text):
    lines = text.splitlines() or [""]
    offset = 0

    while True:
        win.erase()
        h, w = win.getmaxyx()

        safe_add(win, 0, 2, f" {title} ", accent())

        visible = max(1, h - 4)

        for i, line in enumerate(lines[offset:offset + visible]):
            safe_add(win, 2 + i, 1, line[:w - 2], 1)

        safe_add(win, h - 1, 2, "↑↓ Scroll  PgUp/PgDn  q Close", 5)
        win.refresh()

        key = win.getch()

        if key in (ord("q"), 27):
            return
        elif key in (curses.KEY_UP, ord("k")):
            offset = max(0, offset - 1)
        elif key in (curses.KEY_DOWN, ord("j")):
            offset = min(max(0, len(lines) - visible), offset + 1)
        elif key == curses.KEY_NPAGE:
            offset = min(max(0, len(lines) - visible), offset + visible)
        elif key == curses.KEY_PPAGE:
            offset = max(0, offset - visible)


# ─────────────────────────────────────────────
# System monitor
# ─────────────────────────────────────────────

def system_monitor(win):
    while True:
        win.erase()
        h, w = win.getmaxyx()

        safe_add(win, 0, 2, " SYSTEM MONITOR ", accent())
        safe_add(win, 1, 2, "Refresh: 1 sec | q: exit", 5)

        if psutil:
            cpu = psutil.cpu_percent(interval=0.4)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage("/")
            swap = psutil.swap_memory()

            safe_add(win, 3, 2, f"CPU      {cpu:5.1f}%  {bar(cpu, 100)}", 4)
            safe_add(win, 5, 2,
                     f"RAM      {memory.percent:5.1f}%  "
                     f"{bar(memory.percent, 100)}", 3)

            safe_add(win, 6, 2,
                     f"         {memory.used / 1024**3:.2f} / "
                     f"{memory.total / 1024**3:.2f} GB", 1)

            safe_add(win, 8, 2,
                     f"DISK     {disk.percent:5.1f}%  "
                     f"{bar(disk.percent, 100)}", 5)

            safe_add(win, 9, 2,
                     f"         {disk.used / 1024**3:.1f} / "
                     f"{disk.total / 1024**3:.1f} GB", 1)

            safe_add(win, 11, 2,
                     f"SWAP     {swap.percent:5.1f}%  "
                     f"{bar(swap.percent, 100)}", 7)

            safe_add(win, 13, 2, "TOP PROCESSES", 3)

            try:
                processes = sorted(
                    psutil.process_iter(
                        ["pid", "name", "memory_percent", "cpu_percent"]
                    ),
                    key=lambda p: p.info["memory_percent"] or 0,
                    reverse=True
                )

                for i, p in enumerate(processes[:max(1, h - 17)]):
                    info = p.info
                    name = (info["name"] or "?")[:24]
                    safe_add(
                        win, 14 + i, 2,
                        f"{info['pid']:>6} {name:<25} "
                        f"RAM {info['memory_percent'] or 0:5.1f}%",
                        1
                    )

            except Exception:
                pass

        else:
            center(win, 5, "Install python3-psutil for monitoring", 5)

        win.refresh()
        win.timeout(1000)
        key = win.getch()
        win.timeout(-1)

        if key in (ord("q"), 27):
            return


# ─────────────────────────────────────────────
# Network tools
# ─────────────────────────────────────────────

def network_app(win):
    while True:
        win.erase()
        h, w = win.getmaxyx()

        safe_add(win, 0, 2, " NETWORK ", accent())

        try:
            host = socket.gethostname()
            ip = socket.gethostbyname(host)
        except Exception:
            host, ip = "Unknown", "Unavailable"

        safe_add(win, 3, 3, f"Hostname: {host}", 4)
        safe_add(win, 4, 3, f"Local IP: {ip}", 3)

        options = [
            "1. Network configuration (nmtui)",
            "2. Ping Google",
            "3. Show IP addresses",
            "4. Show routing table",
            "5. Internet connectivity test",
            "q. Return",
        ]

        for i, item in enumerate(options):
            safe_add(win, 7 + i, 3, item, 1)

        win.refresh()
        key = win.getch()

        if key == ord("q"):
            return
        elif key == ord("1"):
            run_external(win, "nmtui")
        elif key == ord("2"):
            run_external(win, "ping -c 4 google.com")
        elif key == ord("3"):
            run_external(win, "ip addr")
        elif key == ord("4"):
            run_external(win, "ip route")
        elif key == ord("5"):
            run_external(win, "curl -I --max-time 5 https://google.com")


# ─────────────────────────────────────────────
# Calculator
# ─────────────────────────────────────────────

_ALLOWED_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def safe_calculate(expression):
    tree = ast.parse(expression, mode="eval")

    def evaluate(node):
        if isinstance(node, ast.Expression):
            return evaluate(node.body)

        if isinstance(node, ast.Constant) and isinstance(
                node.value, (int, float)):
            return node.value

        if isinstance(node, ast.BinOp):
            op = _ALLOWED_OPERATORS.get(type(node.op))
            if not op:
                raise ValueError("Operator not allowed")
            if isinstance(node.op, ast.Pow) and abs(
                    node.right.value if isinstance(
                        node.right, ast.Constant) else 100) > 100:
                raise ValueError("Power too large")
            return op(evaluate(node.left), evaluate(node.right))

        if isinstance(node, ast.UnaryOp):
            op = _ALLOWED_OPERATORS.get(type(node.op))
            if not op:
                raise ValueError("Operator not allowed")
            return op(evaluate(node.operand))

        raise ValueError("Invalid expression")

    return evaluate(tree)


def calculator(win):
    history = []

    while True:
        win.erase()
        h, w = win.getmaxyx()

        safe_add(win, 0, 2, " CALCULATOR ", accent())
        safe_add(win, 2, 2, "Operators: + - * / // % **", 5)

        for i, item in enumerate(history[-8:]):
            safe_add(win, 4 + i, 2, item, 1)

        expression = prompt(win, "Expression (q to exit): ")

        if expression.lower() == "q":
            return

        if not expression.strip():
            continue

        try:
            result = safe_calculate(expression)
            history.append(f"{expression} = {result}")
        except Exception as e:
            history.append(f"{expression} → Error: {e}")


# ─────────────────────────────────────────────
# Notes
# ─────────────────────────────────────────────

def notes_app(win):
    while True:
        win.erase()
        h, w = win.getmaxyx()

        safe_add(win, 0, 2, " VTOS NOTES ", accent())

        try:
            content = NOTES.read_text(errors="replace")
        except Exception:
            content = ""

        lines = content.splitlines()

        for i, line in enumerate(lines[:h - 5]):
            safe_add(win, 2 + i, 2, line[:w - 4], 1)

        safe_add(win, h - 2, 2,
                 "a Add line | c Clear | q Exit", 5)

        win.refresh()
        key = win.getch()

        if key == ord("q"):
            return

        elif key == ord("a"):
            new_line = prompt(win, "Write note: ")
            if new_line:
                with NOTES.open("a", encoding="utf-8") as f:
                    f.write(new_line + "\n")

        elif key == ord("c"):
            safe_add(win, h - 3, 2, "Clear notes? y/N", 6)
            win.refresh()

            if win.getch() in (ord("y"), ord("Y")):
                NOTES.write_text("", encoding="utf-8")


# ─────────────────────────────────────────────
# Application launcher
# ─────────────────────────────────────────────

def apps_app(win):
    while True:
        win.erase()
        h, w = win.getmaxyx()

        safe_add(win, 0, 2, " APPLICATION LAUNCHER ", accent())

        options = [
            ("Firefox", "firefox"),
            ("Chromium", "chromium"),
            ("File manager", "xdg-open ~"),
            ("Text editor", "xed"),
            ("LibreOffice", "libreoffice"),
            ("VLC", "vlc"),
            ("Steam", "steam"),
            ("Terminal", "x-terminal-emulator"),
        ]

        safe_add(win, 2, 2, "Installed applications (if available):", 5)

        for i, (name, cmd) in enumerate(options):
            safe_add(win, 4 + i, 2, f"{i + 1}. {name}", 1)

        safe_add(win, 14, 2, "c. Custom command    q. Return", 5)

        win.refresh()
        key = win.getch()

        if key == ord("q"):
            return

        elif key == ord("c"):
            command = prompt(win, "Command: ")
            if command:
                run_external(win, command)

        elif ord("1") <= key <= ord("8"):
            idx = key - ord("1")
            run_external(win, options[idx][1])


# ─────────────────────────────────────────────
# Shell
# ─────────────────────────────────────────────

def shell_app(win):
    run_external(win, os.environ.get("SHELL", "/bin/bash"))


# ─────────────────────────────────────────────
# Settings
# ─────────────────────────────────────────────

def settings_app(win):
    global theme_name

    themes = list(THEMES.keys())
    selected = themes.index(theme_name)

    while True:
        win.erase()
        h, w = win.getmaxyx()

        safe_add(win, 0, 2, " SETTINGS ", accent())
        safe_add(win, 2, 2, "Color themes:", 5)

        for i, theme in enumerate(themes):
            color = 2 if i == selected else 1
            safe_add(win, 4 + i, 4, f"{i + 1}. {theme.upper()}", color)

        safe_add(win, 10, 2, "↑↓ Select  ENTER Apply  q Exit", 5)

        win.refresh()
        key = win.getch()

        if key == ord("q"):
            return
        elif key in (curses.KEY_UP, ord("k")):
            selected = (selected - 1) % len(themes)
        elif key in (curses.KEY_DOWN, ord("j")):
            selected = (selected + 1) % len(themes)
        elif key in (10, 13, curses.KEY_ENTER):
            theme_name = themes[selected]
            save_settings()


def save_settings():
    (CONFIG / "settings.txt").write_text(theme_name, encoding="utf-8")


def load_settings():
    global theme_name

    try:
        saved = (CONFIG / "settings.txt").read_text().strip()
        if saved in THEMES:
            theme_name = saved
    except Exception:
        pass


# ─────────────────────────────────────────────
# System information
# ─────────────────────────────────────────────

def system_info(win):
    win.erase()
    h, w = win.getmaxyx()

    safe_add(win, 0, 2, " SYSTEM INFORMATION ", accent())

    information = [
        f"OS: {platform.system()} {platform.release()}",
        f"Distribution: {platform.platform()}",
        f"Hostname: {platform.node()}",
        f"Architecture: {platform.machine()}",
        f"Python: {platform.python_version()}",
        f"User: {os.getenv('USER', 'unknown')}",
        f"Shell: {os.getenv('SHELL', 'unknown')}",
        f"Terminal: {os.getenv('TERM', 'unknown')}",
        f"Current directory: {Path.cwd()}",
    ]

    if psutil:
        information.extend([
            f"CPU cores: {psutil.cpu_count(logical=False)} physical / "
            f"{psutil.cpu_count()} logical",
            f"RAM: {psutil.virtual_memory().total / 1024**3:.2f} GB",
        ])

    for i, line in enumerate(information):
        safe_add(win, 3 + i, 2, line, 1)

    wait_key(win)


# ─────────────────────────────────────────────
# Power menu
# ─────────────────────────────────────────────

def power_app(win):
    win.erase()
    h, w = win.getmaxyx()

    center(win, 3, "POWER OPTIONS", accent())

    options = [
        "1. Exit VTOS",
        "2. Reboot Linux",
        "3. Shut down Linux",
        "q. Cancel",
    ]

    for i, item in enumerate(options):
        center(win, 6 + i, item, 1)

    win.refresh()
    key = win.getch()

    if key == ord("1"):
        return "exit"

    if key in (ord("2"), ord("3")):
        center(win, 12, "Are you sure? Press y to confirm", 6)
        win.refresh()

        if win.getch() in (ord("y"), ord("Y")):
            curses.endwin()

            command = "sudo reboot" if key == ord("2") else "sudo poweroff"
            os.system(command)

            return "exit"

    return None


# ─────────────────────────────────────────────
# Main menu
# ─────────────────────────────────────────────

MENU = [
    ("⌂", "Desktop", dashboard),
    ("▤", "File Manager", file_manager),
    ("◉", "System Monitor", system_monitor),
    ("◎", "Network", network_app),
    ("∑", "Calculator", calculator),
    ("✎", "Notes", notes_app),
    ("▶", "Applications", apps_app),
    ("⌘", "Shell", shell_app),
    ("⚙", "Settings", settings_app),
    ("▣", "System Information", system_info),
    ("⏻", "Power", power_app),
]


def main(stdscr):
    global theme_name

    curses.curs_set(0)
    curses.noecho()
    curses.cbreak()
    stdscr.keypad(True)
    stdscr.timeout(-1)

    init_colors()
    load_settings()

    selected = 0

    while True:
        stdscr.erase()
        h, w = stdscr.getmaxyx()

        if h < 24 or w < 70:
            center(stdscr, 2, "VTOS needs at least 70x24 terminal size", 6)
            center(stdscr, 4, "Resize your terminal and press any key", 5)
            stdscr.refresh()
            stdscr.getch()
            continue

        # Top bar
        safe_add(stdscr, 0, 2, " VTOS ", accent())
        safe_add(stdscr, 0, 10, "Vibecoded Terminal Operating System", 7)
        safe_add(stdscr, 0, w - 21, time.strftime("%H:%M:%S"), 5)

        try:
            stdscr.hline(1, 1, curses.ACS_HLINE, w - 2)
        except curses.error:
            pass

        # Left menu
        menu_width = 29

        safe_add(stdscr, 2, 3, "APPLICATIONS", 5)

        for i, (icon, name, _) in enumerate(MENU):
            y = 4 + i

            text = f" {icon}  {name}"

            if i == selected:
                safe_add(stdscr, y, 2, "▶", 4)
                safe_add(stdscr, y, 4, text, 2)
            else:
                safe_add(stdscr, y, 4, text, 1)

        try:
            stdscr.vline(2, menu_width, curses.ACS_VLINE, h - 4)
        except curses.error:
            pass

        # Right information panel
        panel_x = menu_width + 3

        safe_add(stdscr, 3, panel_x, "SYSTEM OVERVIEW", 3)

        safe_add(stdscr, 5, panel_x,
                 f"USER      {os.getenv('USER', 'user')}", 1)
        safe_add(stdscr, 6, panel_x,
                 f"HOST      {platform.node()}", 1)
        safe_add(stdscr, 7, panel_x,
                 f"OS        {platform.system()}", 1)
        safe_add(stdscr, 8, panel_x,
                 f"RELEASE   {platform.release()}", 1)
        safe_add(stdscr, 9, panel_x,
                 f"PYTHON    {platform.python_version()}", 1)

        safe_add(stdscr, 11, panel_x, "QUICK STATUS", 3)

        if psutil:
            cpu = psutil.cpu_percent()
            mem = psutil.virtual_memory().percent

            safe_add(stdscr, 13, panel_x,
                     f"CPU   {bar(cpu, 100, 20)} {cpu:5.1f}%", 4)
            safe_add(stdscr, 15, panel_x,
                     f"RAM   {bar(mem, 100, 20)} {mem:5.1f}%", 3)

        safe_add(stdscr, 18, panel_x, "SHORTCUTS", 3)
        safe_add(stdscr, 20, panel_x, "↑ ↓  Navigate", 1)
        safe_add(stdscr, 21, panel_x, "ENTER  Launch", 1)
        safe_add(stdscr, 22, panel_x, "q  Exit VTOS", 1)

        # Bottom bar
        try:
            stdscr.hline(h - 2, 1, curses.ACS_HLINE, w - 2)
        except curses.error:
            pass

        safe_add(stdscr, h - 1, 2,
                 "VTOS  |  Unicode Terminal Environment", 7)
        safe_add(stdscr, h - 1, w - 18,
                 f"THEME: {theme_name.upper()}", accent())

        stdscr.refresh()
        key = stdscr.getch()

        if key in (ord("q"), 27):
            return

        elif key in (curses.KEY_UP, ord("k")):
            selected = (selected - 1) % len(MENU)

        elif key in (curses.KEY_DOWN, ord("j")):
            selected = (selected + 1) % len(MENU)

        elif key in (10, 13, curses.KEY_ENTER):
            app = MENU[selected][2]

            result = app(stdscr)

            if result == "exit":
                return

        elif ord("1") <= key <= ord("9"):
            idx = key - ord("1")
            if idx < len(MENU):
                MENU[idx][2](stdscr)

        elif key == ord("0"):
            MENU[9][2](stdscr)


# ─────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────

if __name__ == "__main__":
    try:
        main_screen = curses.wrapper(main)
    except KeyboardInterrupt:
        pass
    except Exception as error:
        print(f"\nVTOS error: {error}")
        print("Check terminal compatibility and Python installation.")