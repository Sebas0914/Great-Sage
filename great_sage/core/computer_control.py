"""Windows computer-control primitives for Great Sage.

Uses the native Win32 SendInput API instead of an unrestricted shell.  This
lets Great Sage operate the user's desktop (mouse, keyboard and windows)
without turning model output into arbitrary PowerShell/cmd execution.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import time
from typing import Iterable


user32 = ctypes.windll.user32

INPUT_MOUSE = 0
INPUT_KEYBOARD = 1

MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
MOUSEEVENTF_WHEEL = 0x0800
MOUSEEVENTF_ABSOLUTE = 0x8000
MOUSEEVENTF_VIRTUALDESK = 0x4000
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004

WHEEL_DELTA = 120
WM_CLOSE = 0x0010
SW_RESTORE = 9


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", ctypes.c_long),
        ("dy", ctypes.c_long),
        ("mouseData", ctypes.c_ulong),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.c_void_p),
    ]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", ctypes.c_ushort),
        ("wScan", ctypes.c_ushort),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.c_void_p),
    ]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", ctypes.c_ulong),
        ("wParamL", ctypes.c_ushort),
        ("wParamH", ctypes.c_ushort),
    ]


class _INPUTUNION(ctypes.Union):
    _fields_ = [
        ("mi", MOUSEINPUT),
        ("ki", KEYBDINPUT),
        ("hi", HARDWAREINPUT),
    ]


class INPUT(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [
        ("type", ctypes.c_ulong),
        ("u", _INPUTUNION),
    ]


user32.SendInput.argtypes = (ctypes.c_uint, ctypes.POINTER(INPUT), ctypes.c_int)
user32.SendInput.restype = ctypes.c_uint


def _send(items: Iterable[INPUT]) -> None:
    batch = list(items)
    if not batch:
        return
    arr = (INPUT * len(batch))(*batch)
    sent = user32.SendInput(len(batch), arr, ctypes.sizeof(INPUT))
    if sent != len(batch):
        raise RuntimeError(
            "Windows blocked synthetic input (SendInput sent %d/%d). "
            "The target application may be running at a higher integrity level."
            % (sent, len(batch))
        )


def _mouse(flags: int, data: int = 0, dx: int = 0, dy: int = 0) -> INPUT:
    return INPUT(
        type=INPUT_MOUSE,
        mi=MOUSEINPUT(dx, dy, data, flags, 0, None),
    )


def mouse_position() -> tuple[int, int]:
    p = wt.POINT()
    if not user32.GetCursorPos(ctypes.byref(p)):
        raise RuntimeError("Could not read the mouse position.")
    return int(p.x), int(p.y)


def move_mouse(x: int, y: int, duration: float = 0.0) -> str:
    """Move the cursor to absolute desktop coordinates.

    A short duration is implemented as several native moves so an agent can
    visibly travel to a control instead of teleporting to it.
    """
    x, y = int(x), int(y)
    if duration <= 0:
        _move_absolute(x, y)
        return "Mouse moved to (%d, %d)." % (x, y)

    sx, sy = mouse_position()
    steps = max(2, min(80, int(duration * 80)))
    delay = max(0.0, float(duration) / steps)
    for i in range(1, steps + 1):
        f = i / steps
        _move_absolute(round(sx + (x - sx) * f), round(sy + (y - sy) * f))
        if delay:
            time.sleep(delay)
    return "Mouse moved to (%d, %d)." % (x, y)


def _move_absolute(x: int, y: int) -> None:
    # SendInput absolute coordinates cover the virtual desktop.  SM_XVIRTUALSCREEN
    # etc. are required for multi-monitor layouts with negative coordinates.
    left = user32.GetSystemMetrics(76)
    top = user32.GetSystemMetrics(77)
    width = max(1, user32.GetSystemMetrics(78) - 1)
    height = max(1, user32.GetSystemMetrics(79) - 1)
    nx = round((x - left) * 65535 / width)
    ny = round((y - top) * 65535 / height)
    _send([_mouse(MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE |
                  MOUSEEVENTF_VIRTUALDESK, dx=nx, dy=ny)])


def click_mouse(button: str = "left", clicks: int = 1, interval: float = 0.08) -> str:
    button = (button or "left").lower().strip()
    flags = {
        "left": (MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP),
        "right": (MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP),
        "middle": (MOUSEEVENTF_MIDDLEDOWN, MOUSEEVENTF_MIDDLEUP),
    }.get(button)
    if flags is None:
        raise ValueError("button must be left, right or middle")
    clicks = max(1, min(int(clicks), 3))
    for n in range(clicks):
        _send([_mouse(flags[0]), _mouse(flags[1])])
        if n + 1 < clicks:
            time.sleep(max(0.0, float(interval)))
    return "%s click%s sent." % (button, "s" if clicks != 1 else "")


def scroll_mouse(clicks: int) -> str:
    clicks = max(-20, min(int(clicks), 20))
    if clicks:
        _send([_mouse(MOUSEEVENTF_WHEEL, data=clicks * WHEEL_DELTA)])
    return "Scrolled %d wheel step%s." % (clicks, "" if abs(clicks) == 1 else "s")


_SPECIAL_KEYS = {
    "backspace": 0x08, "tab": 0x09, "enter": 0x0D, "return": 0x0D,
    "shift": 0x10, "ctrl": 0x11, "control": 0x11, "alt": 0x12,
    "pause": 0x13, "capslock": 0x14, "esc": 0x1B, "escape": 0x1B,
    "space": 0x20, "pageup": 0x21, "pagedown": 0x22, "end": 0x23,
    "home": 0x24, "left": 0x25, "up": 0x26, "right": 0x27, "down": 0x28,
    "insert": 0x2D, "delete": 0x2E, "win": 0x5B,
    "lwin": 0x5B, "rwin": 0x5C, "apps": 0x5D,
    "f1": 0x70, "f2": 0x71, "f3": 0x72, "f4": 0x73, "f5": 0x74,
    "f6": 0x75, "f7": 0x76, "f8": 0x77, "f9": 0x78, "f10": 0x79,
    "f11": 0x7A, "f12": 0x7B,
}


def _vk(key: str) -> int:
    k = str(key).lower().strip()
    if k in _SPECIAL_KEYS:
        return _SPECIAL_KEYS[k]
    if len(k) == 1:
        return ord(k.upper())
    raise ValueError("Unknown key %r. Use a key name such as Enter, Tab, F5 or a single character." % key)


def press_key(key: str) -> str:
    vk = _vk(key)
    _send([
        INPUT(type=INPUT_KEYBOARD,
              ki=KEYBDINPUT(vk, 0, 0, 0, None)),
        INPUT(type=INPUT_KEYBOARD,
              ki=KEYBDINPUT(vk, 0, KEYEVENTF_KEYUP, 0, None)),
    ])
    return "Pressed %s." % key


def hotkey(keys: str) -> str:
    names = [k.strip() for k in str(keys).replace("+", " ").split() if k.strip()]
    if not names:
        raise ValueError("No keys supplied.")
    vks = [_vk(k) for k in names]
    events = [
        INPUT(type=INPUT_KEYBOARD, ki=KEYBDINPUT(vk, 0, 0, 0, None))
        for vk in vks
    ]
    events.extend(
        INPUT(type=INPUT_KEYBOARD, ki=KEYBDINPUT(vk, 0, KEYEVENTF_KEYUP, 0, None))
        for vk in reversed(vks)
    )
    _send(events)
    return "Hotkey %s sent." % "+".join(names)


def type_text(text: str, interval: float = 0.0) -> str:
    text = str(text)
    if len(text) > 4000:
        raise ValueError("type_text is limited to 4000 characters per call.")
    for ch in text:
        code = ord(ch)
        _send([
            INPUT(type=INPUT_KEYBOARD,
                  ki=KEYBDINPUT(0, code, KEYEVENTF_UNICODE, 0, None)),
            INPUT(type=INPUT_KEYBOARD,
                  ki=KEYBDINPUT(0, code,
                                KEYEVENTF_UNICODE | KEYEVENTF_KEYUP, 0, None)),
        ])
        if interval:
            time.sleep(max(0.0, float(interval)))
    return "Typed %d characters." % len(text)


def _window_titles() -> list[tuple[int, str]]:
    result: list[tuple[int, str]] = []
    buf = ctypes.create_unicode_buffer(512)

    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def callback(hwnd, _lparam):
        if user32.IsWindowVisible(hwnd) and user32.GetWindowTextLengthW(hwnd):
            user32.GetWindowTextW(hwnd, buf, 512)
            title = buf.value.strip()
            if title:
                result.append((int(hwnd), title))
        return True

    user32.EnumWindows(callback, 0)
    return result


def list_windows() -> str:
    rows = _window_titles()
    if not rows:
        return "No visible windows."
    return "\n".join("%d: %s" % (hwnd, title) for hwnd, title in rows[:80])


def focus_window(title: str) -> str:
    q = str(title or "").strip().lower()
    if not q:
        raise ValueError("A window title is required.")
    matches = [(hwnd, name) for hwnd, name in _window_titles() if q in name.lower()]
    if not matches:
        raise ValueError("No visible window matches %r." % title)
    hwnd, name = matches[0]
    user32.ShowWindow(wt.HWND(hwnd), SW_RESTORE)
    user32.SetForegroundWindow(wt.HWND(hwnd))
    return "Focused window %r." % name


def close_window(title: str) -> str:
    q = str(title or "").strip().lower()
    if not q:
        raise ValueError("A window title is required.")
    matches = [(hwnd, name) for hwnd, name in _window_titles() if q in name.lower()]
    if not matches:
        raise ValueError("No visible window matches %r." % title)
    hwnd, name = matches[0]
    user32.PostMessageW(wt.HWND(hwnd), WM_CLOSE, 0, 0)
    return "Requested close for window %r." % name
