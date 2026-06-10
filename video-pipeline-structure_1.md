# Video Pipeline — Folder & Script Structure

## Machine Overview

| Machine | Role | OS | Shares |
|---------|------|----|--------|
| **STREAMING-PC** | Ingests from recorder SSD, renames from WordPress, holds MOV for 3 weeks | Windows 11 | Exposes Desktop (or subfolder) as SMB share (ro) |
| **DocuSynology** | Staging (`~/video`) + WORM archive (`~/Videos`) | Synology DSM | `video` (rw), `Videos` (WORM) |
| **ai-video-train** | Camera angle detection (GPU VM, Proxmox) | Ubuntu 24.04 | Mounts remote shares; model at `~/camera-ai/` |
| **video-processing** | Exposure normalize + LUT + encode + Vimeo upload (Proxmox VM) | Ubuntu 24.04 | Mounts remote shares |

---

## Network Share Layout

```
\\STREAMING-PC\Desktop              (read-only from VMs — or a subfolder if you prefer)
    ├── 07-JUD-519-022V.mov         ← already renamed from WordPress
    └── 66-REV-910-004V.mov

\\DocuSynology\video                (read-write — pipeline output + 3-week staging)
    ├── 07-JUD/
    │   ├── 07-JUD-519-022V.mp4     ← folder derived from filename: <book#>-<abbrev>
    │   ├── 07-JUD-519-023V.mp4
    │   └── ...
    ├── 66-REV/
    │   └── 66-REV-910-004V.mp4
    └── angle-json/
        ├── 07-JUD-519-022V.json
        └── 66-REV-910-004V.json

\\DocuSynology\Videos               (WORM — final archive, syncs to Azure cold storage)
    ├── 07-JUD/
    │   ├── 07-JUD-510-001V.mp4
    │   └── ...
    └── 66-REV/
        └── ...
```

### File Lifecycle

```
Recorder SSD
  → STREAMING-PC Desktop (manual copy)
    → Rename from WordPress (existing scripts)
      → 07-JUD-519-022V.mov stays on Desktop  (shared as \\STREAMING-PC\Desktop)
        ├──→ ai-video-train reads MOV in-place → writes JSON to \video\angle-json\
        └──→ video-processing reads MOV in-place + angle JSON
               → per-segment exposure normalize → LUT → encode MP4
               → derives folder from filename (07-JUD-519-022V → 07-JUD)
               → writes MP4 to \\DocuSynology\video\07-JUD\07-JUD-519-022V.mp4
               → uploads MP4 to Vimeo

  Then, on timers:
    STREAMING-PC: deletes MOV from Desktop after 3 weeks (existing cleanup)
    DocuSynology: after 3 weeks in ~/video/<book>/, move to ~/Videos/<book>/ (WORM)
                  → Azure cold storage sync picks it up from there
```

**Key principle:** MOVs never get copied. VMs mount the shares and read in-place.
Pipeline writes MP4 + JSON directly to `\\DocuSynology\video`. Files sit there
for 3 weeks to verify quality, then get committed to `\\DocuSynology\Videos` (WORM).

---

## ai-video-train VM

```
~/camera-ai/                        # your trained model (already in place)
    ├── best_model.pth
    └── ...

/srv/video-pipeline/
├── config/
│   ├── pipeline.env                # SMB creds, paths, email/SMTP, retry settings
│   └── azure-archive-inventory.csv # tracks archive dates + Azure tier + eligibility
│
├── mnt/                            # mountpoints for remote shares
│   ├── streaming-desktop/          # → \\STREAMING-PC\Desktop     (ro)
│   ├── synology-video/             # → \\DocuSynology\video       (rw)
│   └── synology-videos/            # → \\DocuSynology\Videos      (ro, WORM)
│
├── scripts/
│   ├── classify_angles.py          # extracted from classify_video.py — ONLY angle detection
│   │                               #   reads MOV → extracts frames → model inference → JSON
│   │                               #   no LUT logic, no video encoding
│   ├── detect_angles.sh            # wrapper: validates inputs, calls classify_angles.py,
│   │                               #   validates output JSON, handles errors
│   ├── process_weekly.sh           # orchestrator for weekly pipeline (this VM's portion)
│   ├── process_archive_batch.sh    # orchestrator for archive batch (manual trigger)
│   └── lib/
│       ├── logging.sh              # structured logging (timestamp, level, context)
│       ├── retry.sh                # retry w/ exponential backoff + max attempts
│       ├── notify.sh               # send email on failure/completion (mailx or msmtp)
│       ├── lock.sh                 # flock-based locking to prevent duplicate runs
│       └── healthcheck.sh          # mount verification, disk space, model availability
│
├── work/
│   ├── frames/                     # temp extracted frames (cleaned up after each job)
│   └── processing/                 # temp space for current job metadata
│
├── logs/
│   ├── weekly/
│   │   ├── 07-JUD-519-022V.log
│   │   └── ...
│   ├── archive/
│   │   └── batch-2024-03-10.log
│   └── pipeline.log                # rolling log, all activity (for Zabbix tail later)
│
└── state/
    ├── weekly-processed.txt        # list of files already processed (prevents re-runs)
    └── archive-processed.txt       # same for archive batches
```

### classify_angles.py (extracted from classify_video.py)

This is the classification-only portion of your existing script. Keeps: frame extraction,
model inference, smoothing, segment building, JSON output. Removes: all LUT/apply_luts
logic, video encoding, ffmpeg output.

```
Usage: python classify_angles.py \
         --video /mnt/streaming-desktop/07-JUD-519-022V.mov \
         --model ~/camera-ai/best_model.pth \
         --output-json /srv/video-pipeline/work/processing/07-JUD-519-022V.json

Output JSON schema:
{
  "video": "07-JUD-519-022V.mov",
  "class_names": ["camera1", "camera2", "camera3", "camera4"],
  "num_segments": 47,
  "segments": [
    {"camera": "camera1", "start": 0.0, "end": 45.5, "class_index": 0},
    {"camera": "camera3", "start": 45.5, "end": 92.0, "class_index": 2},
    ...
  ]
}
```

### Scripts Detail

**detect_angles.sh**
```
Usage: detect_angles.sh <input.mov> <output.json>

Steps:
  1. Verify input file exists and is readable
  2. Verify model exists at ~/camera-ai/best_model.pth
  3. Run: python classify_angles.py --video <input> --model ~/camera-ai/best_model.pth --output-json <output>
  4. Validate output JSON (jq syntax check + expected schema: class_names, segments array)
  5. Exit 0 on success, non-zero on failure with structured error to stderr
```

**process_weekly.sh**
```
Usage: process_weekly.sh [--dry-run] [--file specific_file.mov]

Steps:
  1. Source config/pipeline.env
  2. Run healthcheck.sh (mounts, disk, model file)
  3. Acquire lock (lock.sh) — exit if already running
  4. Scan /mnt/streaming-desktop/ for .mov files not in state/weekly-processed.txt
  5. For each file:
     a. Log start
     b. detect_angles.sh <mov_path> <work/processing/filename.json>
        - On failure: retry (retry.sh, 3 attempts), then notify + skip
     c. Copy validated JSON to /mnt/synology-video/angle-json/
     d. Write completion marker to state file
     e. Clean up work/frames/
     f. Log end + duration
  6. Notify summary (files processed, failures)
```

**process_archive_batch.sh**
```
Usage: process_archive_batch.sh <year> [--limit N]

Steps:
  1. Read azure-archive-inventory.csv
  2. Filter to eligible files (age > retention threshold for tier)
  3. For each eligible file (up to --limit):
     a. Verify file exists on /mnt/synology-videos/ (WORM)
     b. Run detect_angles.sh
     c. Store JSON to /mnt/synology-video/angle-json/
     d. Update inventory CSV with processing date
     e. Log per-file result
  4. Summary report: processed, skipped (too new), failed, remaining
```

---

## video-processing VM

```
/srv/video-pipeline/
├── config/
│   ├── pipeline.env                # SMB creds, Vimeo API token
│   ├── vimeo.env                   # Vimeo OAuth tokens (separate, tighter perms)
│   ├── luts/
│   │   ├── camera1.cube            # per-camera LUT files (matched to class_names in JSON)
│   │   ├── camera2.cube
│   │   ├── camera3.cube
│   │   └── camera4.cube
│   └── exposure/
│       ├── camera1.json            # per-camera exposure/WB normalization params
│       ├── camera2.json            #   e.g. {"brightness": 0.05, "gamma": 1.1, "whitebalance": ...}
│       ├── camera3.json
│       └── camera4.json
│
├── mnt/
│   ├── streaming-desktop/          # → \\STREAMING-PC\Desktop     (ro)
│   ├── synology-video/             # → \\DocuSynology\video       (rw, staging)
│   └── synology-videos/            # → \\DocuSynology\Videos      (rw, WORM promotion)
│
├── scripts/
│   ├── process_video.sh            # single-file: read segments → per-segment normalize + LUT → encode
│   ├── upload_vimeo.sh             # upload MP4 to Vimeo via API, verify, return URL
│   ├── promote_to_worm.sh          # moves 3+ week old files from ~/video → ~/Videos (WORM)
│   ├── run_weekly.sh               # orchestrator: watches for angle JSON, runs full chain
│   ├── approve.sh                  # Phase 3: approve reviewed file, triggers Vimeo upload
│   └── lib/
│       ├── logging.sh              # (same pattern as ai-video-train)
│       ├── retry.sh
│       ├── notify.sh
│       ├── lock.sh
│       ├── healthcheck.sh          # mounts, ffmpeg available, Vimeo API reachable, disk space
│       └── validate_mp4.sh         # post-encode checks: duration match, codec, resolution, file size
│
├── work/
│   └── encoding/                   # temp output during ffmpeg encode (local disk, fast I/O)
│
├── logs/
│   ├── weekly/
│   │   ├── 07-JUD-519-022V.log
│   │   └── ...
│   ├── uploads/
│   │   └── vimeo-upload-2024-03-08.log
│   ├── worm/
│   │   └── promote-2024-03-29.log
│   └── pipeline.log
│
└── state/
    ├── weekly-processed.txt
    ├── vimeo-uploads.txt           # filename → vimeo URL mapping
    └── worm-promoted.txt           # filename → WORM promotion timestamp
```

### Scripts Detail

**process_video.sh**
```
Usage: process_video.sh <input.mov>

Steps:
  1. Verify input file exists, is readable, has expected codec (ffprobe)
  2. Read angle JSON from /mnt/synology-video/angle-json/<filename>.json
  3. For each segment in the JSON:
     a. Look up camera name (e.g. "camera2")
     b. Load exposure params from config/exposure/camera2.json
     c. Load LUT from config/luts/camera2.cube
     d. Build ffmpeg command for this segment:
        - Input: direct from SMB mount (no copy), -ss/-to for segment bounds
        - Filters: exposure/WB normalize (eq, colorbalance) → lut3d
        - Encoder: libx264, preset medium, CRF ~18-22 (configurable)
        - Audio: copy or re-encode AAC
        - Output: segment part file in work/encoding/
     e. On segment failure: retry up to 2x, then notify + abort entire file
  4. Concatenate all segment parts (ffmpeg concat demuxer, -c copy)
  5. Run ffmpeg with -xerror flag + progress logging
  6. validate_mp4.sh (duration within 1s of source, resolution, codec check)
  7. Derive book folder from filename: 07-JUD-519-022V → 07-JUD
  8. On validation pass: mkdir -p + move MP4 to /mnt/synology-video/07-JUD/07-JUD-519-022V.mp4
  9. Clean up segment parts from work/encoding/
  10. On failure: notify + abort
```

**upload_vimeo.sh**
```
Usage: upload_vimeo.sh <input.mp4> [--title "..."] [--description "..."]

Steps:
  1. Verify Vimeo API token is valid (test endpoint)
  2. Check file size, estimate upload time
  3. Upload via Vimeo tus/resumable API
     - On network failure: auto-resume (tus protocol handles this)
     - On auth failure: notify immediately, do not retry
  4. Poll for transcode completion (with timeout)
  5. Verify video is accessible (API check)
  6. Log Vimeo URL to state/vimeo-uploads.txt
  7. Return Vimeo URL to caller
```

**promote_to_worm.sh**
```
Usage: promote_to_worm.sh [--dry-run] [--age-days 21]

Steps:
  1. Scan /mnt/synology-video/<book>/ folders for MP4s older than 21 days (configurable)
     (skips angle-json/ folder)
  2. For each eligible file:
     a. Verify file integrity (ffprobe)
     b. Verify matching Vimeo upload exists in state/vimeo-uploads.txt
     c. Derive book folder from filename (07-JUD-519-022V → 07-JUD)
     d. Move to /mnt/synology-videos/07-JUD/07-JUD-519-022V.mp4 (WORM, mkdir -p as needed)
     e. Verify file exists on WORM side + size matches
     f. Log to state/worm-promoted.txt
  3. Summary: promoted, skipped (too new), skipped (no Vimeo confirmation), failed
  4. Notify if any failures

Runs weekly via cron. Intentionally conservative — won't promote a file unless it's
old enough AND has a confirmed Vimeo upload. Belt and suspenders before committing
to immutable storage.
```

**run_weekly.sh**
```
Usage: run_weekly.sh [--dry-run] [--file specific_file.mov]

Steps:
  1. Source config/pipeline.env
  2. healthcheck.sh
  3. Acquire lock
  4. Check for files that have completed angle detection
     (JSON exists in /mnt/synology-video/angle-json/)
     but haven't been video-processed yet (not in state/weekly-processed.txt)
  5. For each:
     a. process_video.sh (reads MOV from streaming-desktop, encodes, writes MP4 to Synology/<book>/)
     b. [Phase 2-3] → flag for review, notify you to check the file on Synology
        [Phase 5]   → upload_vimeo.sh (MP4 already on Synology, just upload to Vimeo)
     c. Update state file
  6. Summary notification
     (STREAMING-PC handles its own MOV cleanup on its 3-week timer)
     (promote_to_worm.sh handles WORM migration on its own schedule)
```

**approve.sh**
```
Usage: approve.sh <filename>   (or "approve.sh --all")

Steps:
  1. Verify MP4 exists on /mnt/synology-video/<book>/<filename>.mp4
  2. Trigger upload_vimeo.sh (reads from Synology)
  3. On success: update state, notify with Vimeo URL
  4. On failure: notify, leave file for retry
```

---

## STREAMING-PC (Windows 11)

Almost nothing changes. Your existing scripts handle the SSD ingest and WordPress rename.
The only new piece is sharing the Desktop (or a subfolder) so the VMs can read the MOVs.

### Existing workflow (keep as-is)
```
1. Recorder SSD → copy MOV to Desktop
2. Existing scripts rename from WordPress → 07-JUD-519-022V.mov
3. MOV stays on Desktop
```

### New: share the Desktop
```
C:\Users\<you>\Desktop\             ← shared as \\STREAMING-PC\Desktop (read-only)
    ├── 07-JUD-519-022V.mov         ← VMs read this in-place
    └── 07-JUD-519-023V.mov
```
(If sharing the whole Desktop feels messy, make a subfolder like `Desktop\VideoInbox`
and have your rename scripts drop files there instead. Either way works.)

### Existing cleanup (keep as-is)
```
MOVs sit on Desktop for 3 weeks as safety net → existing cleanup script deletes them.
```

### Optional: notification hook
```
C:\Scripts\
└── Check-PipelineStatus.ps1        # (optional) polls \\DocuSynology\video\mp4\ for matching .mp4
                                      to confirm pipeline completed for each MOV
```

**What changes for you day-to-day:** Almost nothing. You copy from the SSD, your rename
scripts run, the MOV sits on the Desktop, and the pipeline takes it from there. You just
stop running the FFmpeg encode and Vimeo upload steps on this machine once the pipeline
is trusted. Keep the old scripts around until Phase 5.

---

## Shared Library Pattern (lib/)

Both VMs use the same `lib/` scripts. Keep them in sync via a git repo or just copy — they're small. Here's what each does:

**logging.sh** — Every script sources this. Writes structured lines:
```
2024-03-08T14:23:01-0600 [INFO]  [process_weekly] Starting: 2024-03-08_service.mov
2024-03-08T14:23:01-0600 [ERROR] [detect_angles]  Model inference failed (exit 1), attempt 2/3
```
Format: `TIMESTAMP [LEVEL] [CONTEXT] Message`
Writes to both per-job log and pipeline.log. Pipeline.log is what Zabbix will eventually tail.

**retry.sh** — Wraps any command with exponential backoff:
```bash
# retry <max_attempts> <initial_delay_sec> <command...>
retry 3 5 detect_angles.sh "$input" "$output"
# Attempts: immediate, wait 5s, wait 10s, then fail
```

**notify.sh** — Sends email via msmtp or mailx. Configurable in pipeline.env:
```bash
# notify <subject> <body> [--priority high]
notify "Pipeline failure: detect_angles" "File: service.mov\nError: model timeout" --priority high
```

**lock.sh** — Prevents concurrent runs using flock:
```bash
# acquire_lock <lockfile>  — returns 1 if already locked
acquire_lock /tmp/weekly-pipeline.lock
```

**healthcheck.sh** — Runs before any pipeline work:
```
Checks:
  ✓ All SMB mounts are accessible (df + test write on rw mounts)
  ✓ Required disk space available (configurable threshold)
  ✓ ffmpeg / model binary / vimeo CLI reachable
  ✓ Network connectivity to Vimeo API
  ✓ SMTP relay reachable (so failure notifications can actually send)
Reports: pass/fail per check, aborts pipeline on critical failures
```

**validate_mp4.sh** — Post-encode sanity checks:
```
Checks:
  ✓ File exists and is > 0 bytes
  ✓ ffprobe can read it (not corrupted)
  ✓ Duration matches source within 1 second
  ✓ Video codec is h264
  ✓ Resolution matches expected (1080p)
  ✓ File size is within expected range (not suspiciously small or large)
```

---

## Coordination Between VMs

The two VMs coordinate via the DocuSynology `video` share, not direct communication:

```
                    \\DocuSynology\video
                    ├── angle-json/                  ← ai-video-train WRITES here
                    │   └── 07-JUD-519-022V.json
                    ├── 07-JUD/                      ← video-processing WRITES here
                    │   └── 07-JUD-519-022V.mp4        (folder derived from filename)
                    └── 66-REV/
                        └── 66-REV-910-004V.mp4

ai-video-train                              video-processing
writes JSON ──→  DocuSynology\video  ──→  reads JSON + MOV, encodes MP4,
                                          writes MP4 back to DocuSynology\video\<book>\
```

**run_weekly.sh** on video-processing polls or uses inotifywait on the
`/mnt/synology-video/angle-json/` mount to detect when a new JSON appears,
signaling that angle detection is complete and video processing can begin.

---

## Cron / Systemd Scheduling

### ai-video-train VM
```
# /etc/cron.d/video-pipeline
# Check for new weekly videos every 30 minutes during business hours
*/30 8-18 * * 1-5  pipeuser  /srv/video-pipeline/scripts/process_weekly.sh >> /srv/video-pipeline/logs/cron.log 2>&1
```

### video-processing VM
```
# /etc/cron.d/video-pipeline
# Check for completed angle JSONs every 30 minutes (offset from ai-video-train)
15,45 8-18 * * 1-5  pipeuser  /srv/video-pipeline/scripts/run_weekly.sh >> /srv/video-pipeline/logs/cron.log 2>&1

# Promote aged files from ~/video → ~/Videos WORM archive (weekly, Sunday night)
0 2 * * 0  pipeuser  /srv/video-pipeline/scripts/promote_to_worm.sh >> /srv/video-pipeline/logs/cron.log 2>&1
```

Or use systemd path units / inotifywait for event-driven triggering instead of polling.

---

## Zabbix Integration (Future)

When you're ready, the structured logging makes Zabbix integration straightforward:

- **Log monitoring:** Zabbix agent tails `pipeline.log`, triggers on `[ERROR]` or `[CRITICAL]` lines
- **State file monitoring:** Alert if `weekly-processed.txt` hasn't been updated in 7+ days
- **Mount health:** Custom UserParameter calling `healthcheck.sh --json` for structured output
- **Vimeo upload tracking:** Monitor `vimeo-uploads.txt` for failed/missing entries
- **WORM promotion:** Monitor `worm-promoted.txt` — alert if files are aging past 4+ weeks without promotion
- **Disk space:** Standard Zabbix filesystem monitoring on work/ directories and DocuSynology shares

---

## Phase Progression Checklist

### Phase 2: Manual (you are here → target)
- [ ] SMB shares mounted on both VMs
- [ ] Scripts deployed, lib/ in place
- [ ] Run process_weekly.sh manually, inspect JSON on Synology
- [ ] Run run_weekly.sh manually, inspect MP4 on Synology
- [ ] Run approve.sh manually after visual check → Vimeo upload
- [ ] Run 3–5 weekly videos through successfully

### Phase 3: Semi-Automatic
- [ ] Enable cron jobs on both VMs (except promote_to_worm.sh)
- [ ] Pipeline runs automatically, MP4 lands on Synology, you get email notification
- [ ] Visually check MP4, run approve.sh for Vimeo upload
- [ ] Run 3–5 more weeks in this mode
- [ ] Enable promote_to_worm.sh cron once first batch has aged 3 weeks

### Phase 4: Archive Processing
- [ ] Populate azure-archive-inventory.csv
- [ ] Calculate Azure tier retention thresholds
- [ ] Run process_archive_batch.sh on a small test batch
- [ ] Verify JSON quality on archived content

### Phase 5: Full Automation
- [ ] Remove review gate (run_weekly.sh goes straight to Vimeo upload)
- [ ] promote_to_worm.sh running on weekly cron
- [ ] Set up Zabbix monitoring
- [ ] Set up weekly summary email (processed count, WORM promotions, any errors)
- [ ] Document runbook for common failure scenarios
