#!/usr/bin/env python3
# smart-nag-popup.py — Timer-driven desktop popup nag for Taskwarrior
#
# Evaluates smart-nag.rc conditions and fires a desktop notification when a
# condition matches. Runs independently of task invocations — driven by a
# systemd user timer (tw-smart-nag-popup.timer).
#
# Install:
#   cp smart-nag-popup.py ~/.task/scripts/smart-nag-popup.py
#   chmod +x ~/.task/scripts/smart-nag-popup.py
#   cp tw-smart-nag-popup.service tw-smart-nag-popup.timer ~/.config/systemd/user/
#   systemctl --user daemon-reload
#   systemctl --user enable --now tw-smart-nag-popup.timer
#
# Config keys in smart-nag.rc (all optional, shown with defaults):
#   nag.popup         = on    # on|off — master switch
#   nag.popup-timeout = 8     # seconds before notification auto-dismisses
#   nag.popup-snooze  = 30    # minutes to suppress after clicking Snooze
#   nag.popup-gtk     = on    # on|off — yad dialog with Open/Snooze buttons
#                             #          (requires yad and gtk-task.sh)

import os
import sys
import time
import subprocess
from pathlib import Path

sys.path.insert(0, str(Path.home() / '.task' / 'scripts'))
sys.path.insert(0, str(Path.home() / 'dev' / 'awesome-taskwarrior' / 'lib'))

from tw_condition_lib import compute_action, load_rc, sort_tasks
from tw_hook_lib import task_export

NAG_RC      = Path.home() / '.task' / 'config' / 'smart-nag.rc'
SNOOZE_FILE = Path.home() / '.task' / 'config' / '.smart-nag-snooze'
GTK_TASK    = Path.home() / '.task' / 'scripts' / 'gtk-task.sh'


# ── Snooze ────────────────────────────────────────────────────────────────────

def is_snoozed():
    if not SNOOZE_FILE.exists():
        return False
    try:
        return time.time() < float(SNOOZE_FILE.read_text().strip())
    except (ValueError, OSError):
        return False


def write_snooze(minutes):
    try:
        SNOOZE_FILE.write_text(str(time.time() + minutes * 60))
    except OSError:
        pass


# ── Popup backends ────────────────────────────────────────────────────────────

def _has(cmd):
    return subprocess.run(['which', cmd], capture_output=True).returncode == 0


def show_notify_send(message, timeout_secs):
    subprocess.run(
        ['notify-send', '--app-name=Taskwarrior',
         '-t', str(timeout_secs * 1000), 'Taskwarrior', message],
        check=False,
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )


def show_yad(message, timeout_secs, with_buttons):
    """YAD popup. with_buttons=True adds Open/Snooze/Dismiss.
    Returns 'open', 'snooze', or 'dismiss'."""
    cmd = [
        'yad', '--title=Taskwarrior', f'--text={message}',
        f'--timeout={timeout_secs}', '--timeout-indicator=top',
        '--no-markup', '--wrap', '--width=420', '--borders=14', '--skip-taskbar',
    ]
    if with_buttons:
        cmd += ['--button=Open tasks:10', '--button=Snooze:20', '--button=Dismiss:30']
    else:
        cmd.append('--no-buttons')

    result = subprocess.run(
        cmd, capture_output=True,
        stdin=subprocess.DEVNULL
    )
    if result.returncode == 10:
        return 'open'
    if result.returncode == 20:
        return 'snooze'
    return 'dismiss'   # 30, 252 (timeout), or window-close


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    if not NAG_RC.exists():
        sys.exit(0)

    cfg, conditions = load_rc(NAG_RC, app_prefix='nag')

    if cfg.get('popup', 'on').strip().lower() != 'on':
        sys.exit(0)

    timeout  = int(cfg.get('popup-timeout', '8').strip())
    snooze_m = int(cfg.get('popup-snooze',  '30').strip())
    use_gtk  = cfg.get('popup-gtk', 'on').strip().lower() == 'on'

    if is_snoozed():
        sys.exit(0)

    # Find first matching condition
    message = ''
    for cond in conditions:
        if cond.get('type', 'nag') != 'nag':
            continue
        filt = cond.get('filter', '').strip()
        if not filt:
            continue
        tasks = task_export(filt.split())
        if not tasks:
            continue
        tasks = sort_tasks(tasks, cond.get('sort', ''))
        message = compute_action(cond.get('msg', ''), tasks[0], count=len(tasks))
        if message:
            break

    if not message:
        sys.exit(0)

    # Fire popup — richest available backend
    if use_gtk and _has('yad') and GTK_TASK.exists():
        action = show_yad(message, timeout, with_buttons=True)
        if action == 'open':
            subprocess.Popen(
                [str(GTK_TASK)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL, start_new_session=True
            )
        elif action == 'snooze':
            write_snooze(snooze_m)
    elif _has('notify-send'):
        show_notify_send(message, timeout)
    elif _has('yad'):
        show_yad(message, timeout, with_buttons=False)
    # else: no display tool available — silent exit


if __name__ == '__main__':
    main()
