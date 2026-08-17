from __future__ import annotations

import platform
import subprocess
from pathlib import Path

from nj.utils.logger import get_logger

logger = get_logger(__name__)

NJ_LAUNCHD_LABEL = "com.nj-cli.run"
NJ_CRON_MARKER = "# nj-cli"


def set_schedule(every_days: int, time_str: str = "08:00") -> None:
    if every_days == 0:
        remove_schedule()
        return
    nj_path = _find_nj_binary()
    if platform.system() == "Darwin":
        _set_launchd(nj_path, every_days, time_str)
    else:
        _set_cron(nj_path, every_days, time_str)
    logger.info("schedule_set", every_days=every_days, time=time_str)


def remove_schedule() -> None:
    if platform.system() == "Darwin":
        _remove_launchd()
    else:
        _remove_cron()
    logger.info("schedule_removed")


def get_schedule() -> str | None:
    if platform.system() == "Darwin":
        plist = _launchd_plist_path()
        if plist.exists():
            return f"launchd: {plist}"
        return None
    else:
        crontab = _read_crontab()
        for line in crontab.splitlines():
            if NJ_CRON_MARKER in line and not line.startswith("#"):
                return f"cron: {line.strip()}"
        return None


def show_schedule() -> None:
    from rich.console import Console

    console = Console()
    schedule = get_schedule()
    if schedule:
        console.print(f"[green]Active schedule:[/green] {schedule}")
    else:
        console.print(
            "[yellow]No schedule set.[/yellow] Use [bold]nj --schedule N[/bold] to set one."
        )


def _find_nj_binary() -> str:
    result = subprocess.run(["which", "nj"], capture_output=True, text=True)
    if result.returncode == 0:
        return result.stdout.strip()
    return "nj"


def _launchd_plist_path() -> Path:
    return Path.home() / "Library/LaunchAgents" / f"{NJ_LAUNCHD_LABEL}.plist"


def _set_launchd(nj_path: str, every_days: int, time_str: str) -> None:
    _parse_time(time_str)
    plist_dir = Path.home() / "Library/LaunchAgents"
    plist_dir.mkdir(parents=True, exist_ok=True)
    plist_path = _launchd_plist_path()
    interval_seconds = every_days * 24 * 3600
    plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>{NJ_LAUNCHD_LABEL}</string>
  <key>ProgramArguments</key>
  <array>
    <string>{nj_path}</string>
    <string>run</string>
    <string>--silent</string>
  </array>
  <key>StartInterval</key>
  <integer>{interval_seconds}</integer>
  <key>RunAtLoad</key>
  <false/>
  <key>StandardOutPath</key>
  <string>{Path.home()}/logs/nj-cron.log</string>
  <key>StandardErrorPath</key>
  <string>{Path.home()}/logs/nj-cron.log</string>
</dict>
</plist>
"""
    plist_path.write_text(plist_content)
    subprocess.run(["launchctl", "load", str(plist_path)], capture_output=True)
    logger.info(
        "launchd_schedule_set",
        path=str(plist_path),
        interval_seconds=interval_seconds,
    )


def _remove_launchd() -> None:
    plist_path = _launchd_plist_path()
    if plist_path.exists():
        subprocess.run(["launchctl", "unload", str(plist_path)], capture_output=True)
        plist_path.unlink()
        logger.info("launchd_schedule_removed")


def _set_cron(nj_path: str, every_days: int, time_str: str) -> None:
    hour, minute = _parse_time(time_str)
    cron_line = (
        f"{minute} {hour} */{every_days} * * "
        f"{nj_path} run --silent "
        f">> ~/logs/nj-cron.log 2>&1 "
        f"{NJ_CRON_MARKER}"
    )
    current = _read_crontab()
    lines = [ln for ln in current.splitlines() if NJ_CRON_MARKER not in ln]
    lines.append(cron_line)
    new_crontab = "\n".join(lines) + "\n"
    proc = subprocess.run(
        ["crontab", "-"],
        input=new_crontab,
        text=True,
        capture_output=True,
    )
    if proc.returncode != 0:
        logger.error("cron_set_failed", stderr=proc.stderr)
    else:
        logger.info("cron_schedule_set", line=cron_line)


def _remove_cron() -> None:
    current = _read_crontab()
    lines = [ln for ln in current.splitlines() if NJ_CRON_MARKER not in ln]
    new_crontab = "\n".join(lines) + "\n"
    subprocess.run(
        ["crontab", "-"],
        input=new_crontab,
        text=True,
        capture_output=True,
    )


def _read_crontab() -> str:
    result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    return result.stdout if result.returncode == 0 else ""


def _parse_time(time_str: str) -> tuple[int, int]:
    try:
        parts = time_str.split(":")
        return int(parts[0]), int(parts[1])
    except (ValueError, IndexError):
        return 8, 0
