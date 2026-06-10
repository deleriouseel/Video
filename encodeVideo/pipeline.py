'''
pipeline.py — orchestrator for the weekly video encode/upload pipeline.

Replaces the individually scheduled 01-11 scripts with a single state-driven
run. Scheduled check every 5 minutes via Task Scheduler. Each run loads
pipeline_state.json, performs whatever step is next needed (or exits
immediately if nothing to do), saves state, and exits.

Absorbed into this script:
  01_get_driveFiles.ps1      -> step_copy (drive detection + copy)
  09_delete_desktopFiles.ps1 -> hk_delete_desktop (gated on verified archive copy)
  10_delete_driveFiles.ps1   -> hk_delete_drive (gated on completed cycles)

Run as subprocesses:
  02_get_fileNames, 03_encode_video, 04_upload_video, 05_rename_vimeo, 06_update_wordpress,
  07_update_subsplash (non-blocking), 08_move_files, 11_delete_oldFiles.

The weekly cycle is keyed by Monday's date. The main chain runs once per
cycle: copy -> rename -> encode -> upload -> rename_vimeo -> update_wordpress.
Housekeeping (backup move, deletes) runs at most once per day.

Alerts (email + Graylog event_type=error):
  - Drive not plugged in (or has no qualifying files) by Monday 8:40pm.
  - Pipeline stalled mid-chain by Tuesday 9:00am.

Email goes through Amazon SES. Needs these in .env (alerts are skipped, and logged as errors, if unset):
  SES_REGION, EMAIL_FROM, EMAIL_TO, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY 

Testing (no files are copied, encoded, moved, deleted, or uploaded):
  python pipeline.py --dry-run
      Real drive detection, date math, file scanning, and verification, but
      every action is logged as "DRY RUN: would ..." and state is not saved.
  python pipeline.py --dry-run --pretend-new-week
      Same, but treats this week as unprocessed so the whole chain is walked.
  python pipeline.py --test-email
      Sends one real test email through SES to verify the configuration.
'''

import ctypes
import logging
import json
import os
import shutil
import subprocess
import sys
from datetime import date, datetime, time as dtime, timedelta

try:
    import boto3
    _BOTO3_AVAILABLE = True
except ImportError:
    _BOTO3_AVAILABLE = False

from dotenv import load_dotenv
from logger import get_logger

SCRIPT_NAME = "encode_pipeline"
logger = get_logger(SCRIPT_NAME, __file__)

DRY_RUN = "--dry-run" in sys.argv
TEST_EMAIL = "--test-email" in sys.argv
PRETEND_NEW_WEEK = "--pretend-new-week" in sys.argv

def log_extra(**kwargs):
    return {"script_name": SCRIPT_NAME, **kwargs}

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(SCRIPT_DIR, ".env"))

STATE_FILE = os.path.join(SCRIPT_DIR, "pipeline_state.json")
LOCK_FILE = os.path.join(SCRIPT_DIR, "pipeline.lock")
LOCK_STALE_HOURS = 12

DESKTOP = os.path.join(os.path.expanduser("~"), "Desktop")
STUDIES_DIR = r"D:\Studies"
NETWORK_DIR = r"\\DocuSynology\video"
DRIVE_LABEL_PREFIX = "STUDIO"
MIN_DURATION_SECONDS = 1800

# The recorder cannot be set past ~2024, so its clock runs in a past year
# whose calendar (day-of-week) matches the current year. 2026 -> 2015.
RECORDER_YEAR = lambda real_year: 2015 + (real_year - 2026)

# Drive is expected Monday evening after the Monday recording finishes.
COPY_NOT_BEFORE = dtime(20, 30)        # don't start copying before this on Monday
DRIVE_DEADLINE = dtime(20, 40)         # email if nothing copied by this on Monday
STALL_DEADLINE_DAY_OFFSET = 1          # Tuesday
STALL_DEADLINE = dtime(9, 0)           # email if chain incomplete by this

# Subprocess steps: state key -> (script file, timeout seconds)
SUBPROCESS_STEPS = {
    "rename":           ("02_get_fileNames.py", 600),
    "encode":           ("03_encode_video.py", 6 * 3600),
    "upload":           ("04_upload_video.py", 3 * 3600),
    "rename_vimeo":     ("05_rename_vimeo.py", 600),
    "update_wordpress": ("06_update_wordpress.py", 600),
    "subsplash":        ("07_update_subsplash.py", 900),
    "move_backup":      ("08_move_files.py", 2 * 3600),
    "delete_old":       ("11_delete_oldFiles.py", 3600),
}

REQUIRED_STEPS = ["copy", "rename", "encode", "upload", "rename_vimeo", "update_wordpress"]


# ---------------------------------------------------------------- state

def default_state():
    return {
        "week": None,            # ISO date of this cycle's Monday
        "steps": {},             # step name -> True when done this cycle
        "files": {},             # desktop filename at copy time -> tracking dict
        "alerts": {},            # alert name -> True once sent this cycle
        "copy_status": None,     # "no_drive" | "drive_no_files" | "ok"
        "completed_weeks": [],   # ISO Mondays of fully completed cycles
        "housekeeping": {},      # task name -> ISO date last run
    }


def load_state():
    if not os.path.exists(STATE_FILE):
        return default_state()
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            state = json.load(f)
        merged = default_state()
        merged.update(state)
        return merged
    except Exception as e:
        logger.error(f"Could not read state file, starting fresh: {e}",
                     extra=log_extra(event_type="error", error_message=str(e)))
        return default_state()


def save_state(state):
    if DRY_RUN:
        return
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp, STATE_FILE)


def cycle_monday(d):
    """Monday of the week containing d (cycles run Monday..Sunday)."""
    return d - timedelta(days=d.weekday())


def cycle_for_date(d):
    """The cycle (Monday ISO date) in which a recording made on d gets processed.
    Fri/Sat/Sun recordings are processed the following Monday."""
    if d.weekday() >= 4:
        monday = d + timedelta(days=7 - d.weekday())
    else:
        monday = d - timedelta(days=d.weekday())
    return monday.isoformat()


def rollover(state):
    week = cycle_monday(date.today()).isoformat()
    if state["week"] == week:
        return
    if state["week"] is not None:
        done = all(state["steps"].get(s) for s in REQUIRED_STEPS)
        if not done:
            pending = [s for s in REQUIRED_STEPS if not state["steps"].get(s)]
            logger.error(f"Cycle {state['week']} ended incomplete. Pending steps: {pending}",
                         extra=log_extra(event_type="error",
                                         error_message=f"incomplete cycle {state['week']}"))
    logger.info(f"Starting new cycle: {week}", extra=log_extra())
    state["week"] = week
    state["steps"] = {}
    state["files"] = {}
    state["alerts"] = {}
    state["copy_status"] = None


# ---------------------------------------------------------------- helpers

def acquire_lock():
    if os.path.exists(LOCK_FILE):
        age_hours = (datetime.now().timestamp() - os.path.getmtime(LOCK_FILE)) / 3600
        if age_hours < LOCK_STALE_HOURS:
            logger.info("Another pipeline run is in progress, exiting.", extra=log_extra())
            return False
        logger.warning(f"Removing stale lock file ({age_hours:.1f}h old).", extra=log_extra())
        try:
            os.remove(LOCK_FILE)
        except OSError:
            return False
    try:
        fd = os.open(LOCK_FILE, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        return True
    except FileExistsError:
        return False


def release_lock():
    try:
        os.remove(LOCK_FILE)
    except OSError:
        pass


def walk_files(top):
    """os.walk yielding full file paths, skipping recycle bin and system dirs
    (the original PowerShell scripts never saw hidden/system items either)."""
    skip = {"$RECYCLE.BIN", "SYSTEM VOLUME INFORMATION"}
    for root, dirs, names in os.walk(top):
        dirs[:] = [d for d in dirs if d.upper() not in skip]
        for name in names:
            yield os.path.join(root, name)


def find_studio_drive():
    """Return the root path (e.g. 'E:\\') of the volume labeled STUDIO*, or None."""
    kernel32 = ctypes.windll.kernel32
    kernel32.SetErrorMode(1)  # SEM_FAILCRITICALERRORS: no "insert disk" dialogs
    bitmask = kernel32.GetLogicalDrives()
    for i in range(26):
        if not bitmask & (1 << i):
            continue
        root = f"{chr(65 + i)}:\\"
        label = ctypes.create_unicode_buffer(261)
        fs = ctypes.create_unicode_buffer(261)
        serial, maxlen, flags = ctypes.c_uint(), ctypes.c_uint(), ctypes.c_uint()
        ok = kernel32.GetVolumeInformationW(
            root, label, 261, ctypes.byref(serial), ctypes.byref(maxlen),
            ctypes.byref(flags), fs, 261)
        if ok and label.value.upper().startswith(DRIVE_LABEL_PREFIX):
            return root
    return None


def ffprobe_duration(path):
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", path],
            capture_output=True, text=True, timeout=120)
        return float(result.stdout.strip())
    except Exception as e:
        logger.warning(f"ffprobe failed for {path}: {e}",
                       extra=log_extra(event_type="error", error_message=str(e)))
        return None


def recorder_target_dates(today):
    """Latest Friday, Sunday, Monday as they appear on the recorder's offset clock."""
    target_year = RECORDER_YEAR(today.year)
    try:
        offset_today = today.replace(year=target_year)
    except ValueError:  # Feb 29 with no leap-year counterpart
        offset_today = today.replace(year=target_year, day=28)
    latest_friday = offset_today - timedelta(days=(offset_today.weekday() - 4) % 7)
    latest_sunday = offset_today - timedelta(days=(offset_today.weekday() - 6) % 7)
    latest_monday = offset_today - timedelta(days=offset_today.weekday())
    logger.info(f"Recorder target dates ({target_year}): Fri {latest_friday}, "
                f"Sun {latest_sunday}, Mon {latest_monday}", extra=log_extra())
    return latest_friday, latest_sunday, latest_monday


def adjusted_file_date(path):
    """Creation date, mapped to the current year when the recorder's offset
    clock (any year before 2020) produced it."""
    created = datetime.fromtimestamp(os.path.getctime(path)).date()
    if created.year < 2020:
        try:
            return created.replace(year=date.today().year)
        except ValueError:
            return created.replace(year=date.today().year, day=28)
    return created


def find_archived_copy(stem):
    """Look for an encoded .mp4 for this stem on D: or the backup server.
    Returns the first existing non-empty path, or None."""
    folder = stem[:6]
    candidates = [
        os.path.join(STUDIES_DIR, stem + ".mp4"),
        os.path.join(STUDIES_DIR, folder, stem + ".mp4"),
        os.path.join(NETWORK_DIR, folder, stem + ".mp4"),
    ]
    for path in candidates:
        try:
            if os.path.isfile(path) and os.path.getsize(path) > 0:
                return path
        except OSError:
            continue
    return None


def verified_output(output_path, source_duration):
    """An encode output is valid if it exists, is non-empty, and its duration
    matches the source within 2% (or 60s, whichever is larger)."""
    if not (os.path.isfile(output_path) and os.path.getsize(output_path) > 0):
        return False
    duration = ffprobe_duration(output_path)
    if duration is None or duration <= 0:
        return False
    if source_duration:
        return abs(duration - source_duration) <= max(60, 0.02 * source_duration)
    return True


def run_step_script(step):
    """Run one of the numbered scripts as a subprocess. Returns True on exit 0."""
    script, timeout = SUBPROCESS_STEPS[step]
    path = os.path.join(SCRIPT_DIR, script)
    if DRY_RUN:
        logger.info(f"DRY RUN: would run step '{step}' ({script})",
                    extra=log_extra(step=step))
        return True
    logger.info(f"Running step '{step}' ({script})", extra=log_extra(step=step))
    try:
        result = subprocess.run([sys.executable, path], cwd=SCRIPT_DIR,
                                capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        logger.error(f"Step '{step}' timed out after {timeout}s",
                     extra=log_extra(event_type="error", step=step,
                                     error_message=f"timeout after {timeout}s"))
        return False
    if result.returncode != 0:
        tail = (result.stderr or result.stdout or "")[-2000:]
        logger.error(f"Step '{step}' exited with code {result.returncode}: {tail}",
                     extra=log_extra(event_type="error", step=step,
                                     error_message=tail))
        return False
    logger.info(f"Step '{step}' finished successfully", extra=log_extra(step=step))
    return True


def send_alert_email(subject, body):
    if DRY_RUN and not TEST_EMAIL:
        logger.info(f"DRY RUN: would send email '{subject}'", extra=log_extra())
        return True
    region = os.getenv("SES_REGION")
    from_addr = os.getenv("EMAIL_FROM")
    to_addr = os.getenv("EMAIL_TO")
    if not _BOTO3_AVAILABLE:
        logger.error("Alert email not sent: boto3 is not installed. "
                     "Install with: pip install boto3",
                     extra=log_extra(event_type="error",
                                     error_message="boto3 not installed"))
        return False
    if not all([region, from_addr, to_addr]):
        logger.error("Alert email not sent: SES settings missing from .env "
                     "(SES_REGION, EMAIL_FROM, EMAIL_TO)",
                     extra=log_extra(event_type="error",
                                     error_message="SES not configured"))
        return False
    try:
        ses = boto3.client("ses", region_name=region)
        ses.send_email(
            Source=from_addr,
            Destination={"ToAddresses": [a.strip() for a in to_addr.split(",")]},
            Message={
                "Subject": {"Data": subject},
                "Body": {"Text": {"Data": body}},
            },
        )
        logger.info(f"Alert email sent: {subject}", extra=log_extra())
        return True
    except Exception as e:
        logger.error(f"Failed to send alert email: {e}",
                     extra=log_extra(event_type="error", error_message=str(e)))
        return False


# ---------------------------------------------------------------- main chain

def step_copy(state):
    """Port of 01_get_driveFiles.ps1. Copies qualifying .mov files from the
    STUDIO drive to the desktop and records them in state for tracking."""
    today = date.today()
    now = datetime.now()
    # Don't copy before Monday evening: the Monday recording isn't on the
    # drive yet, and copying early would mark the step done without it.
    if today.weekday() == 0 and now.time() < COPY_NOT_BEFORE:
        logger.debug("Before Monday copy window, skipping copy attempt.")
        return False

    drive = find_studio_drive()
    if not drive:
        state["copy_status"] = "no_drive"
        logger.info("No STUDIO drive present.", extra=log_extra())
        return False
    logger.info(f"STUDIO drive found at {drive}", extra=log_extra())

    latest_friday, latest_sunday, latest_monday = recorder_target_dates(today)
    targets = {latest_friday, latest_sunday, latest_monday}

    mov_files = [p for p in walk_files(drive) if p.lower().endswith(".mov")]

    sunday_candidates = []
    to_copy = []
    for path in mov_files:
        created = datetime.fromtimestamp(os.path.getctime(path)).date()
        if created not in targets:
            logger.debug(f"'{path}' (created {created}) not on a target date, skipping.")
            continue
        duration = ffprobe_duration(path)
        if duration is None:
            continue
        logger.info(f"'{os.path.basename(path)}' duration: {duration / 60:.2f} minutes",
                    extra=log_extra())
        if duration <= MIN_DURATION_SECONDS:
            logger.info(f"'{path}' is shorter than 30 minutes, skipping.", extra=log_extra())
            continue
        if created == latest_sunday:
            sunday_candidates.append((os.path.getctime(path), path, duration))
        else:
            to_copy.append((path, duration))

    # Sunday: only the earliest service
    if sunday_candidates:
        sunday_candidates.sort()
        _, path, duration = sunday_candidates[0]
        logger.info(f"Selected earliest Sunday file: {os.path.basename(path)}",
                    extra=log_extra())
        to_copy.append((path, duration))

    if DRY_RUN:
        for path, duration in to_copy:
            logger.info(f"DRY RUN: would copy '{path}' to desktop "
                        f"({duration / 60:.1f} min)", extra=log_extra())
        logger.info(f"DRY RUN: {len(to_copy)} files would be copied", extra=log_extra())
        return False

    for path, duration in to_copy:
        name = os.path.basename(path)
        dest = os.path.join(DESKTOP, name)
        already = (name in state["files"]
                   and os.path.isfile(dest)
                   and os.path.getsize(dest) == state["files"][name]["size"])
        if not already:
            logger.info(f"Copying '{path}' to '{dest}'", extra=log_extra())
            try:
                shutil.copy2(path, dest)  # copy2 keeps mtime: 03 matches on it
            except Exception as e:
                logger.error(f"Failed to copy '{path}': {e}",
                             extra=log_extra(event_type="error", error_message=str(e)))
                continue
        state["files"][name] = {
            "size": os.path.getsize(dest),
            "mtime": os.path.getmtime(dest),
            "duration": duration,
            "renamed_to": state["files"].get(name, {}).get("renamed_to"),
            "missing": False,
            "on_d": state["files"].get(name, {}).get("on_d", False),
        }

    if state["files"]:
        state["copy_status"] = "ok"
        names = ", ".join(state["files"])
        logger.info(f"Copied {len(state['files'])} files from drive",
                    extra=log_extra(event_type="key_event", step="copy",
                                    file_count=len(state["files"]), filenames=names))
        return True
    state["copy_status"] = "drive_no_files"
    logger.warning("STUDIO drive present but no qualifying files found.",
                   extra=log_extra(event_type="error",
                                   error_message="drive present, no qualifying files"))
    return False


def step_rename(state):
    """Run 02, then verify each tracked file actually got renamed. A file may
    stay pending if its WordPress post isn't published yet; we retry next run."""
    files = state["files"]
    pending = {n: f for n, f in files.items() if not f["renamed_to"] and not f["missing"]}
    if not pending:
        return True

    if not run_step_script("rename"):
        return False

    desktop_movs = [n for n in os.listdir(DESKTOP) if n.endswith(".MOV")]
    claimed = {f["renamed_to"] for f in files.values() if f["renamed_to"]}
    for name, f in pending.items():
        if os.path.isfile(os.path.join(DESKTOP, name)):
            logger.info(f"'{name}' not renamed yet (no matching WordPress post?). Will retry.",
                        extra=log_extra())
            continue
        match = None
        for cand in desktop_movs:
            if cand in files or cand in claimed:
                continue
            cand_path = os.path.join(DESKTOP, cand)
            if (os.path.getsize(cand_path) == f["size"]
                    and abs(os.path.getmtime(cand_path) - f["mtime"]) < 5):
                match = cand
                break
        if match:
            f["renamed_to"] = match
            claimed.add(match)
            logger.info(f"'{name}' renamed to '{match}'", extra=log_extra())
        else:
            f["missing"] = True
            logger.error(f"'{name}' disappeared from desktop without a traceable rename.",
                         extra=log_extra(event_type="error",
                                         error_message=f"lost track of {name}"))

    done = all(f["renamed_to"] or f["missing"] for f in files.values())
    if done:
        renamed = [f["renamed_to"] for f in files.values() if f["renamed_to"]]
        logger.info(f"Renamed {len(renamed)} files",
                    extra=log_extra(event_type="key_event", step="rename",
                                    file_count=len(renamed),
                                    filenames=", ".join(renamed)))
    return done


def step_encode(state):
    """Run 03 if any tracked file lacks a verified output on D:, then verify."""
    tracked = [f for f in state["files"].values() if f["renamed_to"] and not f["missing"]]
    if not tracked:
        return True

    def verify_all():
        for f in tracked:
            if f["on_d"]:
                continue
            out = os.path.join(STUDIES_DIR, os.path.splitext(f["renamed_to"])[0] + ".mp4")
            if verified_output(out, f["duration"]):
                f["on_d"] = True
                logger.info(f"Verified encode output on D: {out}", extra=log_extra())
        return all(f["on_d"] for f in tracked)

    if verify_all():
        return True
    if not run_step_script("encode"):
        return False
    done = verify_all()
    if done:
        names = ", ".join(f["renamed_to"] for f in tracked)
        logger.info(f"Encoded and verified {len(tracked)} files on D:",
                    extra=log_extra(event_type="key_event", step="encode",
                                    file_count=len(tracked), filenames=names))
    else:
        failed = [f["renamed_to"] for f in tracked if not f["on_d"]]
        logger.error(f"Encode ran but outputs failed verification: {failed}",
                     extra=log_extra(event_type="error",
                                     error_message=f"unverified outputs: {failed}"))
    return done


def run_chain(state):
    """Run the main weekly chain in order, stopping at the first incomplete step.
    Each completed step is recorded in state so it never re-runs this cycle
    (re-running 04 would create duplicate Vimeo uploads)."""
    chain = [
        ("copy", lambda: step_copy(state)),
        ("rename", lambda: step_rename(state)),
        ("encode", lambda: step_encode(state)),
        ("upload", lambda: run_step_script("upload")),
        ("rename_vimeo", lambda: run_step_script("rename_vimeo")),
        ("update_wordpress", lambda: run_step_script("update_wordpress")),
    ]
    for name, func in chain:
        if state["steps"].get(name):
            continue
        ok = func()
        save_state(state)
        if not ok:
            if DRY_RUN:
                logger.info(f"DRY RUN: chain stops at '{name}' this run; later "
                            f"steps run on future invocations once it completes.",
                            extra=log_extra())
            return
        state["steps"][name] = True
        save_state(state)

    # Optional: subsplash is half-built and must never block the cycle.
    # Disabled until 07_update_subsplash.py is finished — uncomment to enable.
    # if not state["steps"].get("subsplash"):
    #     ok = run_step_script("subsplash")
    #     state["steps"]["subsplash"] = True  # one attempt per cycle, pass or fail
    #     if not ok:
    #         logger.warning("Subsplash step failed (non-blocking).", extra=log_extra())
    #     save_state(state)

    if state["week"] not in state["completed_weeks"]:
        state["completed_weeks"].append(state["week"])
        state["completed_weeks"] = state["completed_weeks"][-26:]
        logger.info(f"Cycle {state['week']} complete.",
                    extra=log_extra(event_type="key_event", step="cycle_complete",
                                    file_count=len(state["files"]),
                                    filenames=", ".join(state["files"])))
        save_state(state)


def check_alerts(state):
    now = datetime.now()
    monday = date.fromisoformat(state["week"])

    if not state["steps"].get("copy"):
        deadline = datetime.combine(monday, DRIVE_DEADLINE)
        if now >= deadline and not state["alerts"].get("no_drive"):
            if state["copy_status"] == "drive_no_files":
                detail = ("The STUDIO drive is plugged in, but no recordings from "
                          "Friday/Sunday/Monday over 30 minutes were found on it.")
            else:
                detail = ("No STUDIO drive is connected to the computer. "
                          "Check that the external drive is plugged in properly.")
            send_alert_email(
                "Video pipeline: drive not ready",
                f"{detail}\n\nNothing has been copied for the week of {monday}. "
                f"The pipeline will keep checking every few minutes and start "
                f"automatically once the drive is available.")
            state["alerts"]["no_drive"] = True
        return

    done = all(state["steps"].get(s) for s in REQUIRED_STEPS)
    if not done:
        stall = datetime.combine(monday + timedelta(days=STALL_DEADLINE_DAY_OFFSET),
                                 STALL_DEADLINE)
        if now >= stall and not state["alerts"].get("stalled"):
            pending = [s for s in REQUIRED_STEPS if not state["steps"].get(s)]
            logger.error(f"Pipeline stalled. Pending steps: {pending}",
                         extra=log_extra(event_type="error",
                                         error_message=f"stalled at {pending[0]}"))
            send_alert_email(
                "Video pipeline: stalled",
                f"The pipeline for the week of {monday} has not finished. "
                f"Pending steps: {', '.join(pending)}.\n\n"
                f"Check the encode_pipeline logs in Graylog for details.")
            state["alerts"]["stalled"] = True


# ---------------------------------------------------------------- housekeeping

def hk_delete_desktop():
    """Port of 09_delete_desktopFiles.ps1, but a file is only deleted if a
    verified copy exists on D: or the backup server."""
    today = date.today()
    latest_friday = today - timedelta(days=(today.weekday() - 4) % 7)
    deleted = []
    for path in walk_files(DESKTOP):
        name = os.path.basename(path)
        if name.lower().endswith((".mov", ".mp4")):
            created = datetime.fromtimestamp(os.path.getctime(path)).date()
            if created >= latest_friday:
                continue
            stem = os.path.splitext(name)[0]
            archived = find_archived_copy(stem)
            if archived:
                if DRY_RUN:
                    logger.info(f"DRY RUN: would delete desktop file '{path}' "
                                f"(archived at {archived})", extra=log_extra())
                    deleted.append(name)
                    continue
                try:
                    os.remove(path)
                    deleted.append(name)
                    logger.info(f"Deleted desktop file '{path}' (archived at {archived})",
                                extra=log_extra())
                except OSError as e:
                    logger.error(f"Failed to delete '{path}': {e}",
                                 extra=log_extra(event_type="error", error_message=str(e)))
            else:
                logger.warning(f"NOT deleting '{path}': no archived copy found on D: or backup.",
                               extra=log_extra(event_type="error",
                                               error_message=f"no archive for {name}"))
    summary = log_extra() if DRY_RUN else log_extra(
        event_type="key_event", step="delete_desktop",
        file_count=len(deleted), filenames=", ".join(deleted))
    logger.info(f"Desktop cleanup{' (dry run)' if DRY_RUN else ''} deleted "
                f"{len(deleted)} files", extra=summary)
    return True


def hk_delete_drive(state):
    """Port of 10_delete_driveFiles.ps1, but a file is only deleted if the
    cycle it belongs to completed (copied, encoded, uploaded, backed up flow
    finished). Returns False when no drive is present so it retries later."""
    drive = find_studio_drive()
    if not drive:
        return False
    today = date.today()
    latest_friday = today - timedelta(days=(today.weekday() - 4) % 7)
    completed = set(state["completed_weeks"])
    deleted = []
    for path in walk_files(drive):
        name = os.path.basename(path)
        adjusted = adjusted_file_date(path)
        if adjusted >= latest_friday:
            continue
        week = cycle_for_date(adjusted)
        if week not in completed:
            logger.warning(f"NOT deleting '{path}': cycle {week} is not recorded "
                           f"as completed.", extra=log_extra())
            continue
        if DRY_RUN:
            logger.info(f"DRY RUN: would delete drive file '{path}' "
                        f"(cycle {week} completed)", extra=log_extra())
            deleted.append(name)
            continue
        try:
            os.remove(path)
            deleted.append(name)
            logger.info(f"Deleted drive file '{path}' (cycle {week} completed)",
                        extra=log_extra())
        except OSError as e:
            logger.error(f"Failed to delete '{path}': {e}",
                         extra=log_extra(event_type="error", error_message=str(e)))
    summary = log_extra() if DRY_RUN else log_extra(
        event_type="key_event", step="delete_drive",
        file_count=len(deleted), filenames=", ".join(deleted))
    logger.info(f"Drive cleanup{' (dry run)' if DRY_RUN else ''} deleted "
                f"{len(deleted)} files", extra=summary)
    return True


def run_housekeeping(state):
    """Each housekeeping task runs at most once per day. A task returning
    False (e.g. drive absent) is retried on later runs the same day."""
    today = date.today().isoformat()
    tasks = [
        ("move_backup", lambda: run_step_script("move_backup")),
        ("delete_old", lambda: run_step_script("delete_old")),
        ("delete_desktop", hk_delete_desktop),
        ("delete_drive", lambda: hk_delete_drive(state)),
    ]
    for name, func in tasks:
        if state["housekeeping"].get(name) == today:
            continue
        try:
            if func():
                state["housekeeping"][name] = today
        except Exception as e:
            logger.error(f"Housekeeping task '{name}' failed: {e}",
                         extra=log_extra(event_type="error", step=name,
                                         error_message=str(e)))
            state["housekeeping"][name] = today  # don't retry a crasher all day
        save_state(state)


# ---------------------------------------------------------------- entry point

def main():
    if DRY_RUN or TEST_EMAIL:
        console = logging.StreamHandler()
        console.setLevel(logging.DEBUG)
        console.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s",
                                               datefmt="%H:%M:%S"))
        logger.addHandler(console)
    if TEST_EMAIL:
        ok = send_alert_email("Video pipeline: test email",
                              "This is a test of the encode pipeline's SES alerting.")
        return 0 if ok else 1
    if not acquire_lock():
        return 0
    if DRY_RUN:
        logger.info("DRY RUN: no files will be copied, encoded, moved, deleted, "
                    "or uploaded, and state will not be saved.", extra=log_extra())
    logger.info(f"Starting script: {SCRIPT_NAME}",
                extra=log_extra(event_type="script_start"))
    try:
        state = load_state()
        rollover(state)
        if DRY_RUN and PRETEND_NEW_WEEK:
            logger.info("DRY RUN: pretending this week has not been processed.",
                        extra=log_extra())
            state["steps"] = {}
            state["files"] = {}
            state["alerts"] = {}
            state["copy_status"] = None
        save_state(state)
        run_chain(state)
        check_alerts(state)
        run_housekeeping(state)
        save_state(state)
        logger.info(f"Finished script: {SCRIPT_NAME}",
                    extra=log_extra(event_type="script_stop", exit_status="success"))
        return 0
    except Exception as e:
        logger.error(f"Script crashed: {e}",
                     extra=log_extra(event_type="script_stop", exit_status="error",
                                     error_message=str(e)))
        return 1
    finally:
        release_lock()


if __name__ == "__main__":
    sys.exit(main())
