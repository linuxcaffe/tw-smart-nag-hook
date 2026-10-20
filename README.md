- Project: https://github.com/linuxcaffe/tw-smart-nag-hook
- Issues:  https://github.com/linuxcaffe/tw-smart-nag-hook/issues

# tw-smart-nag-hook
Replace Taskwarrior's static nag message with a live, context-aware reminder about your most urgent task.

## TL;DR

- Fires before every `task` invocation as an `on-launch` hook
- Reads conditions from `~/.task/config/smart-nag.rc` — first match wins
- Each condition defines a `filter`, a `msg` template, and a `sort` order
- Token substitution in messages: `<description>`, `<due>`, `<due.age>`, `{count}`, and more
- Six default conditions: active tasks, due today, scheduled today, overdue, behind schedule, highest urgency
- Writes the result as `nag=` to `~/.task/config/nag-state.rc` (included from your taskrc) — native nag trigger controls when it fires
- Optional desktop popup on a systemd timer, with Snooze
- Add your own conditions without touching the hook script
- Requires Taskwarrior 2.6.0+, Python 3.6+

## Why this exists

Taskwarrior has a built-in nag message: a static string that appears when you complete a task while others are more urgent. It tells you that something is more urgent. It does not tell you what that thing is.

The result is a nudge that carries no information. You still have to run `task next` or `task active` to find out what you should actually be doing. The nag becomes noise and you learn to ignore it.

tw-smart-nag-hook replaces that static string with a message generated from your live task data. Before every `task` invocation, it checks your configured conditions in order, finds the first one that matches, and writes a message like `[nag] task 7 "Write quarterly report" is 3d overdue!` as `nag=` in `nag-state.rc`, which your taskrc includes. The nag trigger still controls when the message appears — this hook controls what it says.

Because conditions are fully configurable, you can tune the priority order and message wording to match how you actually work.

## What this means for you

Every time Taskwarrior shows you a nag, it now tells you exactly which task is demanding attention and why — whether it is overdue, scheduled for today, or sitting active and unfinished. You stop ignoring the nag because it stops wasting your time.

## Core concepts

**Condition** — a named block in `smart-nag.rc` that pairs a task filter with a message template. The hook evaluates conditions top to bottom and uses the first one whose filter returns at least one task.

**Token** — a placeholder in a message template that the hook replaces with live task data. Tokens use angle-bracket syntax: `<description>`, `<due>`, `<due.age>`. The special token `{count}` expands to the number of matching tasks.

## Installation

**Option 1 — Install script**

```bash
bash smart-nag.install
```

Installs the hook to `~/.task/hooks/`, the popup script to `~/.task/scripts/`, the timer units to `~/.config/systemd/user/` and the config to `~/.task/config/smart-nag.rc`, and includes `nag-state.rc` and `smart-nag.rc` (from `~/.task/config/included.rc` if you have one, else `~/.taskrc`).

An existing `smart-nag.rc` is never overwritten, and removing smart-nag leaves it in place, so `tw -u smart-nag` keeps your settings. An enabled popup timer stays enabled across an update.

Needs `tw_condition_lib.py` and `tw_hook_lib.py` in `~/.task/scripts/`; awesome-taskwarrior installs both.

**Option 2 — Via [awesome-taskwarrior](https://github.com/linuxcaffe/awesome-taskwarrior)**

```bash
tw -I smart-nag
```

**Option 3 — Manual**

```bash
# Copy the hook and make it executable
cp on-launch_smart-nag.py ~/.task/hooks/on-launch_smart-nag.py
chmod +x ~/.task/hooks/on-launch_smart-nag.py

# Copy the config
cp smart-nag.rc ~/.task/config/smart-nag.rc

# The hook writes the nag here; Taskwarrior shows it only if it's included
echo "nag=" > ~/.task/config/nag-state.rc
echo "include ~/.task/config/nag-state.rc" >> ~/.taskrc

# Verify the hook is active
task diagnostics | grep smart-nag
```

Note: including `smart-nag.rc` itself is optional. The hook reads it directly. Add the include only if you also use [tw-sanity-check](https://github.com/linuxcaffe/tw-sanity-check) and want it to pick up the conditions via its include-chain traversal.

## Configuration

`~/.task/config/smart-nag.rc` ships with six conditions. Each block has four keys:

```ini
# smart-nag.rc

# Active tasks — checked first
condition.nag-started.filter      = +PENDING +ACTIVE
condition.nag-started.msg         = task <id> "<description>" is active! Still working on it?
condition.nag-started.sort        = urgency-
condition.nag-started.type        = nag

# Due today
condition.nag-due-today.filter    = +PENDING due:today
condition.nag-due-today.msg       = task <id> "<description>" is due TODAY!
condition.nag-due-today.sort      = due+,urgency-
condition.nag-due-today.type      = nag

# Scheduled today
condition.nag-sched-today.filter  = +PENDING scheduled:today
condition.nag-sched-today.msg     = task <id> "<description>" is scheduled for TODAY!
condition.nag-sched-today.sort    = scheduled+,urgency-
condition.nag-sched-today.type    = nag

# Overdue — uses <due.age> token
condition.nag-due-late.filter     = +PENDING due.before:today
condition.nag-due-late.msg        = task <id> "<description>" is <due.age> overdue!
condition.nag-due-late.sort       = due+,urgency-
condition.nag-due-late.type       = nag

# Behind schedule
condition.nag-sched-late.filter   = +PENDING scheduled.before:today
condition.nag-sched-late.msg      = task <id> "<description>" is <scheduled.age> behind schedule!
condition.nag-sched-late.sort     = scheduled+,urgency-
condition.nag-sched-late.type     = nag

# Highest urgency fallback — fires when nothing above matched
condition.nag-highest-urgency.filter = +PENDING ( due.none: and scheduled.none: )
condition.nag-highest-urgency.msg    = task <id> "<description>" is the highest urgency!
condition.nag-highest-urgency.sort   = urgency-
condition.nag-highest-urgency.type   = nag
```

**Key reference**

| Key           | Description |
|---------------|-------------|
| `filter`      | Any valid Taskwarrior filter expression |
| `msg`         | Message template — supports tokens (see below) |
| `sort`        | Comma-separated sort keys; `-` suffix = descending, `+` = ascending |
| `type`        | Must be `nag` for this hook |
| `description` | Human-readable label for the condition (used by tw-sanity-check) |

**Token reference**

| Token            | Expands to |
|------------------|------------|
| `<field>`        | Value of any task field: `<description>`, `<id>`, `<project>`, `<due>`, etc. |
| `<field.age>`    | Human-readable age with direction: `3d ago`, `in 2w` |
| `<field±Nd>`     | Date field with offset: `<due+1w>` |
| `{count}`        | Number of tasks matched by the filter |

## Usage

The hook runs automatically before every `task` invocation. You do not need to invoke it directly.

**Test the hook manually**

```bash
# Run any task command and observe the nag if it fires
task done <id>          # nag appears when higher-urgency tasks exist

# Inspect what rc.nag is currently set to
task _get rc.nag
```

The hook caches its result for 30 seconds (`~/.task/logs/smart-nag.cache`), so a burst of commands runs the condition filters once. Taskwarrior has read `nag-state.rc` before on-launch hooks run, so the hook evaluates the conditions in a detached child and the command doesn't wait; the result shows from the next command on.

In clients without a terminal the nag arrives on stderr like any warning: tw-web shows it in its output line after a write (reads run with hooks off, so they neither refresh nor show it).

**Add a custom condition**

Open `~/.task/config/smart-nag.rc` and add a new block. Conditions are evaluated top to bottom — the first match wins, so place higher-priority conditions earlier in the file.

```ini
# Example: nag about tasks tagged +urgent with no due date
condition.nag-urgent-noduedate.filter = +PENDING +urgent due.none:
condition.nag-urgent-noduedate.msg    = task <id> "<description>" is urgent but has no due date!
condition.nag-urgent-noduedate.sort   = urgency-
condition.nag-urgent-noduedate.type   = nag
```

**Disable a condition temporarily**

Comment out the `filter` line or remove the block. The hook skips any condition with an empty or missing filter.

```ini
# condition.nag-started.filter  = +PENDING +ACTIVE   # disabled
```

**Suppress the nag entirely**

If no conditions match, the hook writes an empty `nag=`. Taskwarrior then shows no nag. The `nag-highest-urgency` fallback matches any pending task — remove or disable it if you want the nag to fire only for specific situations.

## Desktop popup

`smart-nag-popup.py` evaluates the same conditions on a systemd user timer (2 minutes after login, then every 30 minutes; edit the `.timer` to change it) and shows the first match as a desktop notification. It's off until you turn it on:

```ini
# smart-nag.rc
nag.popup         = on    # master switch
nag.popup-timeout = 8     # seconds before it auto-dismisses
nag.popup-snooze  = 30    # minutes Snooze suppresses it
nag.popup-gtk     = on    # yad dialog with Open tasks / Snooze / Dismiss
```

```bash
systemctl --user enable --now tw-smart-nag-popup.timer
```

The yad dialog needs `yad` and `gtk-task.sh` (tw-gtk); without them it falls back to `notify-send`, then a plain yad window.

## Project status

Stable and in daily use; configuration format and token syntax are settled for v1.x.

---

- License: MIT
- Language: Python 3
- Requires: Taskwarrior 2.6.0, Python 3.6+
- Platforms: Linux
- Version: 1.2.2
