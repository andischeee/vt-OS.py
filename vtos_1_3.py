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
import json
import calendar as calendar_module
import datetime as datetime_module
import shlex
from pathlib import Path

try:
    import psutil
except ImportError:
    psutil = None

VERSION = "1.3"
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
    "amber": {"accent": curses.COLOR_YELLOW, "secondary": curses.COLOR_RED},
    "red": {"accent": curses.COLOR_RED, "secondary": curses.COLOR_YELLOW},
    "blue": {"accent": curses.COLOR_BLUE, "secondary": curses.COLOR_CYAN},
    "white": {"accent": curses.COLOR_WHITE, "secondary": curses.COLOR_MAGENTA},
}

theme_name = "cyan"
SETTINGS = {"theme":"cyan", "time_format":"24h", "date_format":"%d.%m.%Y",
            "timezone":"local", "refresh_rate":1, "show_seconds":True, "confirm_external":True, "dashboard_extra":True}


def init_colors():
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_WHITE, -1)
    curses.init_pair(2, curses.COLOR_BLACK, THEMES.get(theme_name, THEMES["cyan"])["accent"])
    curses.init_pair(3, curses.COLOR_CYAN, -1)
    curses.init_pair(4, curses.COLOR_GREEN, -1)
    curses.init_pair(5, curses.COLOR_YELLOW, -1)
    curses.init_pair(6, curses.COLOR_RED, -1)
    curses.init_pair(7, curses.COLOR_MAGENTA, -1)
    curses.init_pair(8, curses.COLOR_BLUE, -1)
    curses.init_pair(9, THEMES.get(theme_name, THEMES["cyan"])["accent"], -1)
    curses.init_pair(10, THEMES.get(theme_name, THEMES["cyan"])["accent"], -1)


def accent():
    return 9

def refresh_theme_pairs():
    theme = THEMES.get(theme_name, THEMES["cyan"])
    try:
        curses.init_pair(2, curses.COLOR_BLACK, theme["accent"])
        curses.init_pair(9, theme["accent"], -1)
        curses.init_pair(10, theme["accent"], -1)
    except curses.error:
        pass


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
    status_bar(win)
    win.refresh()
    win.getch()


def clear(win):
    win.erase()
    status_bar(win)
    win.refresh()


def header(win, title):
    win.erase()
    h, w = win.getmaxyx()

    safe_add(win, 0, 2, f" Vibecoded Terminal Operating System {VERSION} ", accent())
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
        if SETTINGS.get("confirm_external",True):
            if prompt(win,"Run external command? y/N: ").strip().lower()!="y": return
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
        status_bar(win)
        win.refresh()


def get_terminal_size(win):
    return win.getmaxyx()


def bar(value, maximum, length=20):
    if maximum <= 0:
        return "░" * length

    filled = int((value / maximum) * length)
    filled = min(length, max(0, filled))

    return "█" * filled + "░" * (length - filled)




def apply_timezone():
    zone = SETTINGS.get("timezone", "local")
    if zone == "local": os.environ.pop("TZ", None)
    else: os.environ["TZ"] = zone
    if hasattr(time, "tzset"): time.tzset()

def clock_text():
    fmt = ("%I:%M:%S %p" if SETTINGS["time_format"] == "12h" else "%H:%M:%S") if SETTINGS.get("show_seconds", True) else ("%I:%M %p" if SETTINGS["time_format"] == "12h" else "%H:%M")
    return time.strftime(fmt)

def date_text():
    try: return time.strftime(SETTINGS["date_format"])
    except Exception: return time.strftime("%d.%m.%Y")

def timed_key(win):
    win.timeout(max(250, int(1000 * SETTINGS.get("refresh_rate", 1))))
    try: key = win.getch()
    finally: win.timeout(-1)
    return key

def status_bar(win):
    # No persistent bottom bar in VTOS 1.2; app-local hints are drawn by each app.
    return

def calendar_app(win):
    today=datetime_module.date.today(); shown=today.replace(day=1); selected_day=today.day
    while True:
        win.erase(); h,w=win.getmaxyx(); safe_add(win,0,2," CALENDAR ",accent())
        center(win,2,shown.strftime("%B %Y"),accent()); center(win,4,"Mo Tu We Th Fr Sa Su",5)
        weeks=calendar_module.monthcalendar(shown.year,shown.month)
        for r,week in enumerate(weeks):
            y=6+r
            if y>=h-5: break
            x=max(2,(w-20)//2)
            for c,d in enumerate(week):
                if d:
                    col=2 if (shown.year==today.year and shown.month==today.month and d==today.day) else (accent() if d==selected_day else 1)
                    safe_add(win,y,x+c*3,f"{d:2}",col)
        center(win,h-5,f"Selected: {shown.strftime('%d.%m.%Y')} | Today: {today.strftime('%d.%m.%Y')}",4)
        center(win,h-3,"←/→ month  ↑/↓ day  t today  q exit",5)
        status_bar(win); win.refresh(); key=timed_key(win)
        if key in (ord('q'),27): return
        if key in (curses.KEY_LEFT,ord('h')): shown=(shown-datetime_module.timedelta(days=1)).replace(day=1); selected_day=min(selected_day,calendar_module.monthrange(shown.year,shown.month)[1])
        elif key in (curses.KEY_RIGHT,ord('l')): shown=(shown+datetime_module.timedelta(days=32)).replace(day=1); selected_day=min(selected_day,calendar_module.monthrange(shown.year,shown.month)[1])
        elif key==ord('t'): shown=today.replace(day=1); selected_day=today.day
        elif key==curses.KEY_UP: selected_day=max(1,selected_day-7)
        elif key==curses.KEY_DOWN: selected_day=min(calendar_module.monthrange(shown.year,shown.month)[1],selected_day+7)

def process_manager(win):
    if not psutil:
        win.erase(); center(win,4,"Install python3-psutil",5); wait_key(win); return
    selected=0; offset=0
    while True:
        win.erase(); h,w=win.getmaxyx()
        safe_add(win,0,2," PROCESS MANAGER ",accent()); safe_add(win,1,2,"↑↓ select | k terminate | PgUp/PgDn scroll | q exit",5)
        procs=[]
        for proc in psutil.process_iter(["pid","name","memory_percent","cpu_percent"]):
            try: procs.append(proc.info)
            except (psutil.NoSuchProcess,psutil.AccessDenied): pass
        procs.sort(key=lambda p:p.get("memory_percent") or 0,reverse=True)
        selected=min(selected,max(0,len(procs)-1)); visible=max(1,h-5)
        offset=max(0,min(offset,max(0,len(procs)-visible)))
        if selected<offset: offset=selected
        if selected>=offset+visible: offset=selected-visible+1
        safe_add(win,2,2,f"{'PID':>7} {'PROCESS':<27} {'CPU':>7} {'RAM':>7}",accent())
        for i,p in enumerate(procs[offset:offset+visible]):
            idx=i+offset
            line=f"{p.get('pid',0):>7} {str(p.get('name') or '?')[:27]:<27} {p.get('cpu_percent') or 0:6.1f}% {p.get('memory_percent') or 0:6.1f}%"
            safe_add(win,3+i,2,line,2 if idx==selected else 1)
        status_bar(win); win.refresh(); key=timed_key(win)
        if key in (ord("q"),27): return
        elif key==curses.KEY_UP: selected=max(0,selected-1)
        elif key==curses.KEY_DOWN: selected=min(max(0,len(procs)-1),selected+1)
        elif key==curses.KEY_NPAGE: selected=min(max(0,len(procs)-1),selected+visible)
        elif key==curses.KEY_PPAGE: selected=max(0,selected-visible)
        elif key==ord("k") and procs:
            p=procs[selected]; safe_add(win,h-2,2,f"Terminate {p['name']} PID {p['pid']}? y/N",6); win.refresh()
            if win.getch() in (ord("y"),ord("Y")):
                try: psutil.Process(p["pid"]).terminate()
                except Exception as e: safe_add(win,h-2,2,str(e)[:w-4],6); win.refresh(); time.sleep(1)

def disk_usage_app(win):
    offset=0
    while True:
        win.erase(); h,w=win.getmaxyx(); safe_add(win,0,2," DISK & APPLICATION STORAGE ",accent())
        rows=[]
        try:
            for part in (psutil.disk_partitions(all=False) if psutil else []):
                try:
                    d=psutil.disk_usage(part.mountpoint)
                    rows.append((f"{part.mountpoint:<18} {d.percent:5.1f}% {d.used/1024**3:.1f}/{d.total/1024**3:.1f} GiB", "", False))
                    rows.append((bar(d.percent,100,18), "", True))
                except (PermissionError,OSError): continue
        except Exception: pass
        rows += [("", "", False), ("INSTALLED PACKAGE SIZE (apt/dpkg)", "", False)]
        if shutil.which("dpkg-query"):
            try:
                output=subprocess.check_output(["dpkg-query","-W","-f=${Installed-Size}\t${binary:Package}\n"],text=True,stderr=subprocess.DEVNULL)
                packages=[]
                for line in output.splitlines():
                    bits=line.split("\t",1)
                    if len(bits)==2:
                        try: packages.append((int(bits[0]),bits[1]))
                        except ValueError: pass
                packages.sort(reverse=True)
                rows += [(f"{size/1024:7.1f} MiB  {name}", "", False) for size,name in packages[:100]]
            except Exception: rows.append(("Unable to read dpkg package sizes", "", False))
        else: rows.append(("dpkg-query not found", "", False))
        visible=max(1,h-4); offset=max(0,min(offset,max(0,len(rows)-visible)))
        for i,row in enumerate(rows[offset:offset+visible]):
            line,drive_bar,is_drive=row
            safe_add(win,2+i,2,line[:w-4],5 if is_drive else 1)
        safe_add(win,h-1,2,"↑↓ scroll | PgUp/PgDn | q return",5); win.refresh(); key=timed_key(win)
        if key in (ord("q"),27): return
        elif key==curses.KEY_UP: offset=max(0,offset-1)
        elif key==curses.KEY_DOWN: offset=min(max(0,len(rows)-visible),offset+1)
        elif key==curses.KEY_NPAGE: offset=min(max(0,len(rows)-visible),offset+visible)
        elif key==curses.KEY_PPAGE: offset=max(0,offset-visible)


def text_editor(win):
    raw=prompt(win,"File path: ").strip()
    if not raw: return
    path=Path(raw).expanduser()
    if not path.is_absolute(): path=Path.cwd()/path
    try: lines=path.read_text(encoding="utf-8",errors="replace").splitlines() if path.exists() else [""]
    except Exception as e:
        win.erase(); center(win,4,f"Cannot open: {e}",6); wait_key(win); return
    while True:
        win.erase(); h,w=win.getmaxyx(); safe_add(win,0,2,f" TEXT EDITOR — {path.name} ",accent())
        for i,line in enumerate(lines[:max(1,h-5)]): safe_add(win,2+i,2,line[:w-4],1)
        safe_add(win,h-2,2,"a append line | s save | q exit",5); status_bar(win); win.refresh()
        key=timed_key(win)
        if key in (ord("q"),27): return
        elif key==ord("a"): lines.append(prompt(win,"Text: "))
        elif key==ord("s"):
            try:
                path.parent.mkdir(parents=True,exist_ok=True); path.write_text("\\n".join(lines)+"\\n",encoding="utf-8")
                safe_add(win,h-2,2,"Saved.",4); win.refresh(); time.sleep(.5)
            except Exception as e: safe_add(win,h-2,2,f"Save error: {e}"[:w-4],6); win.refresh(); time.sleep(1)

def file_search(win):
    query=prompt(win,"Filename contains: ").strip()
    if not query: return
    found=[]
    for base,dirs,files in os.walk(Path.cwd()):
        dirs[:]=[d for d in dirs if d not in {".git","__pycache__",".cache"}]
        for name in dirs+files:
            if query.casefold() in name.casefold():
                found.append(str(Path(base)/name))
                if len(found)>=300: break
        if len(found)>=300: break
    text_viewer(win,"FILE SEARCH","\\n".join(found) if found else "No matches found.")


# ─────────────────────────────────────────────
# Dashboard
# ─────────────────────────────────────────────

def dashboard(win):
    logo_art = [
        '                           █████          █████          ',
        '                                                         ',
        '                           █████             █████       ',
        '                                                         ',
        '█████        █████  ██████████████████          █████    ',
        '                                                         ',
        '  █████     █████          █████                    █████',
        '                                                         ',
        '   █████  █████            █████                █████    ',
        '                                                         ',
        '     ████████              █████             █████       ',
        '                                                         ',
        '       █████                ██████████    █████          ',
    ]
    base=1+len(logo_art)
    try:
        win.keypad(True)
    except Exception:
        pass
    offset=0
    while True:
        win.erase(); h,w=win.getmaxyx()
        for row, art_line in enumerate(logo_art): center(win,1+row,art_line,accent())
        center(win,base+2,f"Vibecoded Terminal Operating System | Version {VERSION}",accent())
        try: win.hline(base+4,2,curses.ACS_HLINE,w-4)
        except curses.error: pass
        content=["", "— ABOUT SYSTEM —",
            f"User: {os.getenv('USER','user')}",
            f"Host: {platform.node()}",
            f"OS / Distribution: {platform.platform()}",
            f"Architecture: {platform.machine()}",
            f"Python: {platform.python_version()}",
            f"Shell: {os.getenv('SHELL','unknown')}",
            f"Terminal: {os.getenv('TERM','unknown')}",
            f"Current directory: {Path.cwd()}"]
        if psutil:
            content += [f"CPU: {platform.processor() or 'Unknown'} | {psutil.cpu_count(logical=False) or '?'} physical / {psutil.cpu_count() or '?'} logical",
                f"RAM installed: {psutil.virtual_memory().total/1024**3:.2f} GB"]
        try:
            du=shutil.disk_usage('/')
            content += [f"Root disk: {du.used/1024**3:.1f} GB used / {du.total/1024**3:.1f} GB total"]
        except Exception: pass
        content += ["", "GitHub: https://github.com/andischeee/vt-OS.py"]
        top=base+6
        available=max(1,h-top-2)
        max_offset=max(0,len(content)-available)
        offset=max(0,min(offset,max_offset))
        for i,line in enumerate(content[offset:offset+available]):
            safe_add(win,top+i,3,line,accent() if line.startswith("—") or line.startswith("GitHub:") else 1)
        safe_add(win,h-2,2,"↑↓ scroll | PgUp/PgDn | q / ESC return",5)
        win.refresh(); key=timed_key(win)
        if key in (ord('q'),27): return
        elif key==curses.KEY_UP: offset=max(0,offset-1)
        elif key==curses.KEY_DOWN: offset=min(max_offset,offset+1)
        elif key==curses.KEY_NPAGE: offset=min(max_offset,offset+available)
        elif key==curses.KEY_PPAGE: offset=max(0,offset-available)


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

        status_bar(win)

        win.refresh()
        key = timed_key(win)

        if key == 27:
            return
        elif key == ord("q"):
            return None

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
        status_bar(win)
        win.refresh()

        key = timed_key(win)

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
    process_offset=0
    while True:
        win.erase()
        h, w = win.getmaxyx()

        safe_add(win, 0, 2, " SYSTEM MONITOR ", accent())
        safe_add(win, 1, 2, f"Refresh: {SETTINGS.get('refresh_rate', 1)} sec | ↑↓ scroll processes | q: exit", 5)

        if psutil:
            cpu = psutil.cpu_percent(interval=None)
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

                visible=max(1,h-17); process_offset=max(0,min(process_offset,max(0,len(processes)-visible)))
                for i, p in enumerate(processes[process_offset:process_offset+visible]):
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

        status_bar(win)

        win.refresh()
        win.timeout(max(250, int(1000 * SETTINGS.get("refresh_rate", 1))))
        key = win.getch()
        win.timeout(-1)
        win.timeout(-1)

        if key in (ord("q"), 27):
            return
        elif key==curses.KEY_DOWN: process_offset+=1
        elif key==curses.KEY_UP: process_offset=max(0,process_offset-1)
        elif key==curses.KEY_NPAGE: process_offset+=max(1,h-17)
        elif key==curses.KEY_PPAGE: process_offset=max(0,process_offset-max(1,h-17))


# ─────────────────────────────────────────────
# Network tools
# ─────────────────────────────────────────────

def monitor_hub(win):
    modes = [("System Monitor", system_monitor), ("Process Manager", process_manager), ("Disk & Installed Apps", disk_usage_app)]
    selected = 0
    while True:
        win.erase(); h,w=win.getmaxyx()
        safe_add(win,0,2," SYSTEM CENTER ",accent())
        safe_add(win,2,2,"←→ select module | ENTER open | q return",5)
        for i,(name,fn) in enumerate(modes):
            safe_add(win,4+i,3,("▶ " if i==selected else "  ")+name,2 if i==selected else 1)
        status_bar(win); win.refresh()
        key=timed_key(win)
        if key in (ord("q"),27): return
        if key in (curses.KEY_LEFT,curses.KEY_UP): selected=(selected-1)%len(modes)
        elif key in (curses.KEY_RIGHT,curses.KEY_DOWN): selected=(selected+1)%len(modes)
        elif key in (10,13,curses.KEY_ENTER): modes[selected][1](win)

def games_app(win):
    try: win.keypad(True)
    except Exception: pass
    games=[("Snake",snake_app),("2048",game_2048)]
    selected=0
    while True:
        win.erase(); h,w=win.getmaxyx(); safe_add(win,0,2," GAMES ",accent())
        safe_add(win,2,2,"↑↓ select | ENTER play | q return",5)
        for i,(name,fn) in enumerate(games): safe_add(win,4+i,3,("▶ " if i==selected else "  ")+name,2 if i==selected else 1)
        safe_add(win,h-2,2,"VTOS Games",5); win.refresh(); key=timed_key(win)
        if key in (ord('q'),27): return
        elif key==curses.KEY_UP: selected=max(0,selected-1)
        elif key==curses.KEY_DOWN: selected=min(len(games)-1,selected+1)
        elif key in (10,13,curses.KEY_ENTER) and games[selected][1]: games[selected][1](win)


def snake_app(win):
    import random
    try: win.keypad(True)
    except Exception: pass
    h,w=win.getmaxyx()
    presets=[("Small",22,10),("Medium",32,14),("Large",min(48,w-8),min(20,h-9))]
    selected=0; field_idx=1; speed_idx=1; food_idx=0
    speeds=[150,115,85,60]; food_counts=[1,2,3]
    record_file=DATA/"snake_record.json"
    try: record=int(json.loads(record_file.read_text()).get("record",0))
    except Exception: record=0
    def settings_menu():
        nonlocal selected,field_idx,speed_idx,food_idx
        while True:
            win.erase(); safe_add(win,0,2," SNAKE SETTINGS ",accent())
            opts=[("Field size",presets[field_idx][0]),("Speed",["Slow","Normal","Fast","Very fast"][speed_idx]),("Food count",str(food_counts[food_idx])),("Start game","ENTER")]
            for i,(label,value) in enumerate(opts): safe_add(win,4+i,3,f"{label:<16}: {value}",2 if i==selected else 1)
            safe_add(win,h-2,2,"↑↓ choose option | ←→ adjust | ENTER start | q games menu",5); win.refresh(); k=timed_key(win)
            if k in (ord('q'),27): return False
            if k==curses.KEY_UP: selected=max(0,selected-1)
            elif k==curses.KEY_DOWN: selected=min(3,selected+1)
            elif k in (curses.KEY_LEFT,curses.KEY_RIGHT):
                direction=-1 if k==curses.KEY_LEFT else 1
                if selected==0: field_idx=(field_idx+direction)%len(presets)
                elif selected==1: speed_idx=(speed_idx+direction)%len(speeds)
                elif selected==2: food_idx=(food_idx+direction)%len(food_counts)
            elif k in (10,13,curses.KEY_ENTER) and selected==3: return True
    while settings_menu():
        _,field_w,field_h=presets[field_idx]
        field_w=max(14,min(field_w,w-8)); field_h=max(8,min(field_h,h-9))
        def make_food(body, foods):
            free=[(yy,xx) for yy in range(1,field_h-1) for xx in range(1,field_w-1) if (yy,xx) not in body]
            random.shuffle(free); return free[:foods]
        snake=[(field_h//2,field_w//2),(field_h//2,field_w//2-1),(field_h//2,field_w//2-2)]
        direction=(0,1); foods=make_food(snake,food_counts[food_idx]); score=0; gameover=False
        while not gameover:
            win.erase(); safe_add(win,0,2," SNAKE ",accent()); safe_add(win,1,2,f"Score {score} | Record {record} | ←↑↓→ move | q quit",5)
            # Visible enclosure: + corners, - horizontal edges, | vertical edges.
            safe_add(win,3,3,"+"+"-"*(field_w-2)+"+",accent())
            safe_add(win,3+field_h-1,3,"+"+"-"*(field_w-2)+"+",accent())
            for yy in range(1,field_h-1):
                safe_add(win,3+yy,3,"|",accent())
                safe_add(win,3+yy,3+field_w-1,"|",accent())
            for yy,xx in snake: safe_add(win,3+yy,3+xx,"█",accent())
            for yy,xx in foods: safe_add(win,3+yy,3+xx,"●",5)
            win.refresh(); win.timeout(int(speeds[speed_idx]*(1.65 if direction[0] else 1.0))); k=win.getch(); win.timeout(-1)
            if k in (ord('q'),27): gameover=True; break
            dirs={curses.KEY_UP:(-1,0),curses.KEY_DOWN:(1,0),curses.KEY_LEFT:(0,-1),curses.KEY_RIGHT:(0,1)}
            if k in dirs and dirs[k]!=( -direction[0],-direction[1]): direction=dirs[k]
            head=(snake[0][0]+direction[0],snake[0][1]+direction[1]); eating=head in foods
            hit=head[0]<=0 or head[0]>=field_h-1 or head[1]<=0 or head[1]>=field_w-1 or head in (snake if eating else snake[:-1])
            if hit:
                gameover=True
                break
            snake.insert(0,head)
            if eating:
                score+=10; foods.remove(head)
                if not foods: foods=make_food(snake,food_counts[food_idx])
                if score>record:
                    record=score
                    try: record_file.write_text(json.dumps({"record":record}),encoding="utf-8")
                    except Exception: pass
            else: snake.pop()
        if score>record: record=score
        win.erase(); center(win,4,"GAME OVER" if score else "GAME ENDED",6); center(win,6,f"Score: {score} | Record: {record}",5)
        center(win,8,"ENTER — restart with settings | q — games menu",1); win.refresh()
        while True:
            k=timed_key(win)
            if k in (ord('q'),27): break
            if k in (10,13,curses.KEY_ENTER): break
        if k in (ord('q'),27): break


def game_2048(win):
    import random
    size=4; board=[[0]*size for _ in range(size)]; score=0
    def spawn():
        empty=[(r,c) for r in range(size) for c in range(size) if not board[r][c]]
        if empty:
            r,c=random.choice(empty); board[r][c]=4 if random.random()<0.1 else 2
    def move(direction):
        nonlocal score
        changed=False
        for i in range(size):
            line=[board[i][j] for j in range(size)] if direction in ('left','right') else [board[j][i] for j in range(size)]
            if direction in ('right','down'): line.reverse()
            compact=[v for v in line if v]; merged=[]; j=0
            while j<len(compact):
                if j+1<len(compact) and compact[j]==compact[j+1]: merged.append(compact[j]*2); score+=compact[j]*2; j+=2
                else: merged.append(compact[j]); j+=1
            merged += [0]*(size-len(merged))
            if direction in ('right','down'): merged.reverse()
            old=[board[i][j] for j in range(size)] if direction in ('left','right') else [board[j][i] for j in range(size)]
            if merged!=old: changed=True
            if direction in ('left','right'):
                board[i]=merged
            else:
                for j,v in enumerate(merged): board[j][i]=v
        return changed
    spawn(); spawn()
    while True:
        win.erase(); h,w=win.getmaxyx(); safe_add(win,0,2," 2048 ",accent()); safe_add(win,1,2,f"Score {score} | Arrow keys move | q exit",5)
        for r in range(size):
            for c in range(size):
                val=board[r][c]; safe_add(win,4+r*3, max(2,(w-25)//2+c*7),f"{val or '.':^5}",accent() if val>=128 else 2 if val else 1)
        safe_add(win,h-2,2,"Merge identical tiles to reach 2048",5); win.refresh(); k=timed_key(win)
        if k in (ord('q'),27): return
        dirs={curses.KEY_LEFT:'left',curses.KEY_RIGHT:'right',curses.KEY_UP:'up',curses.KEY_DOWN:'down'}
        if k in dirs and move(dirs[k]): spawn()


def network_app(win):
    options=[("Network configuration (nmtui)","nmtui"),("Ping Google","ping -c 4 google.com"),("Show IP addresses","ip addr"),("Routing table","ip route"),("Internet connectivity test","curl -I --max-time 5 https://google.com"),("DNS lookup","getent hosts example.com")]
    selected=0
    while True:
        win.erase(); h,w=win.getmaxyx(); safe_add(win,0,2," NETWORK ",accent())
        try: host=socket.gethostname(); ip=socket.gethostbyname(host)
        except Exception: host,ip="Unknown","Unavailable"
        safe_add(win,2,3,f"Hostname: {host}",4); safe_add(win,3,3,f"Local IP: {ip}",3)
        for i,(name,cmd) in enumerate(options): safe_add(win,6+i,3,("▶ " if i==selected else "  ")+name,2 if i==selected else 1)
        safe_add(win,h-2,2,"↑↓/←→ select | ENTER run | q return",5)
        status_bar(win); win.refresh(); key=timed_key(win)
        if key in (ord("q"),27): return
        if key in (curses.KEY_UP,curses.KEY_LEFT): selected=(selected-1)%len(options)
        elif key in (curses.KEY_DOWN,curses.KEY_RIGHT): selected=(selected+1)%len(options)
        elif key in (10,13,curses.KEY_ENTER): run_external(win,options[selected][1])

_ALLOWED_OPERATORS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod, ast.Pow: operator.pow,
    ast.USub: operator.neg, ast.UAdd: operator.pos,
}

def safe_calculate(expression):
    import math
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
            if isinstance(node.op, ast.Pow) and abs(evaluate(node.right)) > 100:
                raise ValueError("Power too large")
            return op(evaluate(node.left), evaluate(node.right))

        if isinstance(node, ast.UnaryOp):
            op = _ALLOWED_OPERATORS.get(type(node.op))
            if not op:
                raise ValueError("Operator not allowed")
            return op(evaluate(node.operand))

        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            funcs={"sqrt":math.sqrt,"sin":math.sin,"cos":math.cos,"tan":math.tan,
                   "asin":math.asin,"acos":math.acos,"atan":math.atan,"log":math.log,
                   "log10":math.log10,"ln":math.log,"abs":abs,"round":round,
                   "ceil":math.ceil,"floor":math.floor,"factorial":math.factorial}
            fn=funcs.get(node.func.id)
            if fn is None or node.keywords: raise ValueError("Function not allowed")
            args=[evaluate(a) for a in node.args]
            if node.func.id=="factorial" and (not args or args[0]<0 or int(args[0])!=args[0] or args[0]>100): raise ValueError("factorial expects integer 0..100")
            return fn(*args)
        if isinstance(node, ast.Name) and node.id in ("pi","e"):
            return math.pi if node.id=="pi" else math.e
        raise ValueError("Invalid expression")

    return evaluate(tree)


def calculator(win):
    history = []

    while True:
        win.erase()
        h, w = win.getmaxyx()

        safe_add(win, 0, 2, " CALCULATOR ", accent())
        safe_add(win, 2, 2, "+ | - | * | / | // | % | **   ||   sqrt | sin | cos | tan | asin | acos | atan | log | ln | abs | round | ceil | floor | factorial   ||   pi | e", 5)

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

        status_bar(win)

        win.refresh()
        key = timed_key(win)

        if key == ord("q"):
            return

        elif key == ord("a"):
            new_line = prompt(win, "Write note: ")
            if new_line:
                with NOTES.open("a", encoding="utf-8") as f:
                    f.write(new_line + "\n")

        elif key == ord("c"):
            safe_add(win, h - 3, 2, "Clear notes? y/N", 6)
            status_bar(win)
            win.refresh()

            if win.getch() in (ord("y"), ord("Y")):
                NOTES.write_text("", encoding="utf-8")


# ─────────────────────────────────────────────
# Application launcher
# ─────────────────────────────────────────────

APP_CONFIG=CONFIG/"apps.json"
DEFAULT_APPS=[("Firefox","firefox"),("Chromium","chromium"),("File manager","xdg-open ~"),("Text editor","xed"),("LibreOffice","libreoffice"),("VLC","vlc"),("Steam","steam"),("Terminal","x-terminal-emulator")]
def apps_app(win):
    try: options=json.loads(APP_CONFIG.read_text(encoding="utf8"))
    except Exception: options=[list(x) for x in DEFAULT_APPS]
    selected=0; offset=0
    while True:
        win.erase(); h,w=win.getmaxyx(); safe_add(win,0,2," APPLICATIONS ",accent()); safe_add(win,2,2,"↑↓ select | ENTER launch | a add | d delete | q return",accent())
        visible=max(1,h-8); offset=max(0,min(offset, max(0,len(options)-visible)))
        for i,(name,cmd) in enumerate(options[offset:offset+visible]):
            idx=i+offset; safe_add(win,4+i,2,("▶ " if idx==selected else "  ")+name,2 if idx==selected else 1)
        safe_add(win,h-3,2,f"{len(options)} apps | {selected+1 if options else 0}/{len(options)}",4); status_bar(win); win.refresh(); key=timed_key(win)
        if key in (ord('q'),27): return
        if key==curses.KEY_UP: selected=max(0,selected-1); offset=max(0,offset-1 if selected<offset else offset)
        elif key==curses.KEY_DOWN: selected=min(len(options)-1,selected+1) if options else 0; offset=selected if selected>=offset+visible else offset
        elif key in (10,13,curses.KEY_ENTER) and options: run_external(win,options[selected][1])
        elif key==ord('a'):
            name=prompt(win,"Application name: ").strip(); cmd=prompt(win,"Command: ").strip()
            if name and cmd: options.append([name,cmd]); APP_CONFIG.write_text(json.dumps(options,indent=2),encoding="utf8"); selected=len(options)-1
        elif key==ord('d') and options:
            if prompt(win,f"Delete {options[selected][0]}? y/N: ").lower()=='y': options.pop(selected); selected=min(selected,max(0,len(options)-1)); APP_CONFIG.write_text(json.dumps(options,indent=2),encoding="utf8")

def stopwatch_app(win):
    try: win.keypad(True)
    except Exception: pass
    running=False; started=0.0; elapsed=0.0
    while True:
        win.erase(); h,w=win.getmaxyx(); now=time.monotonic()
        current=elapsed+(now-started if running else 0)
        hours=int(current//3600); mins=int((current%3600)//60); secs=int(current%60); millis=int((current-int(current))*1000)
        safe_add(win,0,2," STOPWATCH ",accent()); center(win,4,f"{hours:02d}:{mins:02d}:{secs:02d}.{millis:03d}",accent())
        center(win,7,"s start/stop | r reset | q return",5); win.refresh()
        win.timeout(30 if running else max(250,int(1000*SETTINGS.get("refresh_rate",1))))
        try: k=win.getch()
        finally: win.timeout(-1)
        if k in (ord('q'),27): return
        elif k==ord('s'):
            if running: elapsed+=now-started; running=False
            else: started=now; running=True
        elif k==ord('r'): elapsed=0; started=now if running else 0


def shell_app(win):
    run_external(win, os.environ.get("SHELL", "/bin/bash"))


# ─────────────────────────────────────────────
# Settings
# ─────────────────────────────────────────────

def settings_app(win):
    global theme_name
    choices=[("Theme","theme"),("Clock format","time_format"),("Date format","date_format"),("Timezone","timezone"),("Refresh interval","refresh_rate"),("Show seconds","show_seconds"), ("System time","system_time"),("Confirm external commands","confirm_external"),("Desktop system details","dashboard_extra") ]
    selected=0
    while True:
        win.erase(); h,w=win.getmaxyx(); safe_add(win,0,2," SETTINGS ",accent())
        values={"theme":theme_name,"time_format":SETTINGS["time_format"],"date_format":SETTINGS["date_format"],"timezone":SETTINGS["timezone"],"refresh_rate":f'{SETTINGS["refresh_rate"]} sec',"show_seconds":"On" if SETTINGS.get("show_seconds",True) else "Off","system_time":"Set manually (sudo)","confirm_external":"On" if SETTINGS.get("confirm_external",True) else "Off","dashboard_extra":"On" if SETTINGS.get("dashboard_extra",True) else "Off"}
        visible=max(1,h-7); offset=max(0,min(selected,max(0,len(choices)-visible)))
        for i,(label,keyname) in enumerate(choices[offset:offset+visible]):
            idx=i+offset; safe_add(win,3+i,3,f"{label:<18}: {values[keyname]}",2 if idx==selected else 1)
        safe_add(win,h-3,2,"↑↓ select | ←→ / Enter change | q return",5)
        safe_add(win,h-2,2,"Theme changes all accent/highlight colors. Timezone only affects VTOS display.",7)
        win.refresh(); key=timed_key(win)
        if key in (ord("q"),27): return
        if key==curses.KEY_UP: selected=max(0,selected-1); continue
        if key==curses.KEY_DOWN: selected=min(len(choices)-1,selected+1); continue
        if key not in (curses.KEY_LEFT,curses.KEY_RIGHT,10,13,curses.KEY_ENTER): continue
        name=choices[selected][1]
        direction=-1 if key==curses.KEY_LEFT else 1
        if name=="theme":
            vals=list(THEMES); idx=vals.index(theme_name); theme_name=vals[(idx+direction)%len(vals)]; SETTINGS["theme"]=theme_name; refresh_theme_pairs()
        elif name=="time_format": SETTINGS["time_format"]="12h" if SETTINGS["time_format"]=="24h" else "24h"
        elif name=="date_format":
            vals=["%d.%m.%Y","%Y-%m-%d","%m/%d/%Y","%A, %d %B %Y"]; idx=vals.index(SETTINGS["date_format"]) if SETTINGS["date_format"] in vals else 0; SETTINGS["date_format"]=vals[(idx+direction)%len(vals)]
        elif name=="timezone":
            vals=["local","Europe/Kyiv","Europe/London","Europe/Paris","America/New_York","Asia/Tokyo","UTC"]; idx=vals.index(SETTINGS["timezone"]) if SETTINGS["timezone"] in vals else 0; SETTINGS["timezone"]=vals[(idx+direction)%len(vals)]; apply_timezone()
        elif name=="refresh_rate": SETTINGS["refresh_rate"]=0.5 if SETTINGS["refresh_rate"]>=2 else round(SETTINGS["refresh_rate"]+0.5,1)
        elif name=="show_seconds": SETTINGS["show_seconds"]=not SETTINGS.get("show_seconds",True)
        elif name=="confirm_external": SETTINGS["confirm_external"]=not SETTINGS.get("confirm_external",True)
        elif name=="dashboard_extra": SETTINGS["dashboard_extra"]=not SETTINGS.get("dashboard_extra",True)
        elif name=="system_time":
            value=prompt(win,"System time YYYY-MM-DD HH:MM:SS (blank cancels): ").strip()
            if value: run_external(win,"sudo timedatectl set-time "+shlex.quote(value))
        save_settings()


def save_settings():
    SETTINGS["theme"]=theme_name; curses.init_pair(2,curses.COLOR_BLACK,THEMES[theme_name]["accent"])
    (CONFIG/"settings.json").write_text(json.dumps(SETTINGS,indent=2),encoding="utf-8")


def load_settings():
    global theme_name
    try:
        data=json.loads((CONFIG/"settings.json").read_text(encoding="utf-8"))
        if isinstance(data,dict): SETTINGS.update({k:v for k,v in data.items() if k in SETTINGS})
    except Exception:
        try:
            old=(CONFIG/"settings.txt").read_text().strip()
            if old in THEMES: SETTINGS["theme"]=old
        except Exception: pass
    if SETTINGS["theme"] not in THEMES: SETTINGS["theme"]="cyan"
    if SETTINGS["time_format"] not in ("12h","24h"): SETTINGS["time_format"]="24h"
    theme_name=SETTINGS["theme"]; refresh_theme_pairs(); apply_timezone()


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
    options=[("Return to menu",None),("Exit VTOS","exit"),("Reboot Linux","reboot"),("Shut down Linux","poweroff")]
    selected=0
    while True:
        win.erase(); h,w=win.getmaxyx(); center(win,3,"POWER OPTIONS",accent())
        for i,(label,_) in enumerate(options): center(win,6+i,label,2 if i==selected else 1)
        center(win,h-3,"↑↓ select | Enter confirm | q return",5); win.refresh(); key=timed_key(win)
        if key in (ord("q"),27): return None
        elif key==curses.KEY_UP: selected=(selected-1)%len(options)
        elif key==curses.KEY_DOWN: selected=(selected+1)%len(options)
        elif key in (10,13,curses.KEY_ENTER):
            action=options[selected][1]
            if action is None: return None
            if action=="exit": return "exit"
            center(win,12,"Confirm? y/N",6); win.refresh(); confirm=timed_key(win)
            if confirm in (ord("y"),ord("Y")):
                curses.endwin(); os.system("sudo reboot" if action=="reboot" else "sudo poweroff"); return "exit"


# ─────────────────────────────────────────────
# Main menu
# ─────────────────────────────────────────────

MENU = [
    ("⌂", "Desktop", dashboard),
    ("▤", "File Manager", file_manager),
    ("◉", "System Center", monitor_hub),
    ("◎", "Network", network_app),
    ("∑", "Calculator", calculator),
    ("✎", "Notes", notes_app),
    ("▶", "Applications", apps_app),
    ("⌘", "Shell", shell_app),
    ("◷", "Stopwatch", stopwatch_app),
    ("⚙", "Settings", settings_app),
    
    ("▦", "Calendar", calendar_app),
    
    
    ("✎", "Text Editor", text_editor),
    ("⌕", "File Search", file_search),
    ("🎮", "Games", games_app),
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
    refresh_theme_pairs()

    selected = 0
    cpu_history=[]
    if psutil: psutil.cpu_percent(interval=None)

    while True:
        stdscr.erase()
        h, w = stdscr.getmaxyx()

        if h < 27 or w < 70:
            center(stdscr, 2, "VTOS needs at least 70x27 terminal size", 6)
            center(stdscr, 4, "Resize your terminal and press any key", 5)
            stdscr.refresh()
            stdscr.getch()
            continue

        # Top bar appears only on the home screen (not inside launched applications).
        safe_add(stdscr, 0, 2, " Vibecoded Terminal Operating System ", accent())
        safe_add(stdscr, 0, 42, f"Version {VERSION}", accent())
        safe_add(stdscr, 0, max(2,w-29), f"{date_text()}  {clock_text()}", accent())

        try:
            stdscr.hline(1, 1, curses.ACS_HLINE, w - 2)
        except curses.error:
            pass

        # Left menu
        menu_width = 29

        safe_add(stdscr, 2, 3, "APPLICATIONS", accent())

        for i, (icon, name, _) in enumerate(MENU):
            y = 4 + i

            text = f" {icon}  {name}"

            if i == selected:
                safe_add(stdscr, y, 2, "▶", accent())
                safe_add(stdscr, y, 4, text, 2)
            else:
                safe_add(stdscr, y, 4, text, 1)

        try:
            stdscr.vline(2, menu_width, curses.ACS_VLINE, h - 4)
        except curses.error:
            pass

        # Right information panel
        panel_x = menu_width + 3

        safe_add(stdscr, 2, panel_x, "SYSTEM OVERVIEW", accent())

        safe_add(stdscr, 4, panel_x,
                 f"USER      {os.getenv('USER', 'user')}", 1)
        safe_add(stdscr, 5, panel_x,
                 f"HOST      {platform.node()}", 1)
        safe_add(stdscr, 6, panel_x,
                 f"OS        {platform.system()}", 1)
        safe_add(stdscr, 7, panel_x,
                 f"RELEASE   {platform.release()}", 1)
        safe_add(stdscr, 8, panel_x,
                 f"PYTHON    {platform.python_version()}", 1)

        safe_add(stdscr, 10, panel_x, "QUICK STATUS", accent())

        if psutil:
            cpu_now = psutil.cpu_percent(interval=None)
            cpu_history.append(cpu_now); cpu_history=cpu_history[-5:]
            cpu = sum(cpu_history)/len(cpu_history)
            mem = psutil.virtual_memory().percent

            safe_add(stdscr, 12, panel_x,
                     f"CPU   {bar(cpu, 100, 16)} {cpu:5.1f}%", 4)
            safe_add(stdscr, 14, panel_x,
                     f"RAM   {bar(mem, 100, 16)} {mem:5.1f}%", 3)
            # Quick Status rows: separated by one blank line for readability.
            try:
                battery=psutil.sensors_battery()
                if battery:
                    batt_pct=max(0,min(100,float(battery.percent)))
                    batt_color=4 if batt_pct>50 else (5 if batt_pct>=20 else 6)
                    plug=" AC" if battery.power_plugged else ""
                    safe_add(stdscr, 16, panel_x,
                             f"BAT   {bar(batt_pct,100,16)} {batt_pct:4.0f}%{plug}", batt_color)
            except Exception:
                pass

            try:
                disk=shutil.disk_usage('/')
                used_pct=disk.used/disk.total*100 if disk.total else 0
                safe_add(stdscr, 18, panel_x,
                         f"DISK  {bar(used_pct,100,16)} {used_pct:4.0f}%", 5)
            except Exception:
                pass

            try:
                uptime_s=max(0,int(time.time()-psutil.boot_time()))
                up_d, rem=divmod(uptime_s,86400)
                up_h, up_m=divmod(rem//60,60)
                uptime_text=(f"{up_d}d {up_h}h {up_m}m" if up_d else f"{up_h}h {up_m}m")
                safe_add(stdscr, 20, panel_x, f"UPTIME  {uptime_text}", 1)
                safe_add(stdscr, 22, panel_x, f"PROCESSES {len(psutil.pids())}", 1)
            except Exception:
                pass

        safe_add(stdscr, 23, panel_x, "SHORTCUTS", accent())
        safe_add(stdscr, 24, panel_x, "↑ ↓ / J K   Navigate", accent())
        safe_add(stdscr, 25, panel_x, "ENTER       Launch", accent())
        safe_add(stdscr, 26, panel_x, "POWER       Exit", accent())

        stdscr.refresh()
        key = timed_key(stdscr)

        if key == 27:
            continue
        elif key == ord("q"):
            continue

        elif key in (curses.KEY_UP, ord("k")):
            selected = (selected - 1) % len(MENU)

        elif key in (curses.KEY_DOWN, ord("j")):
            selected = (selected + 1) % len(MENU)

        elif key in (10, 13, curses.KEY_ENTER):
            app = MENU[selected][2]

            result = app(stdscr)

            if result == "exit":
                return



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