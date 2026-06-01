# 🎬 AI Video Shorts Automation Framework

<div align="center">

**Automatically transform long-form videos into viral YouTube Shorts, Instagram Reels & TikTok clips**

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![FFmpeg](https://img.shields.io/badge/FFmpeg-007808?style=flat-square&logo=ffmpeg&logoColor=white)](https://ffmpeg.org)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?style=flat-square&logo=docker&logoColor=white)](https://docker.com)

</div>

---

## 🛠️ Tech Stack

<div align="center">
<table>
<tr>
<td align="center" width="140">
<img src="https://cdn.jsdelivr.net/gh/devicons/devicon/icons/python/python-original.svg" width="48" height="48" alt="Python" />
<br><b>Python 3.11+</b>
<br><sub>Core Language</sub>
</td>
<td align="center" width="140">
<img src="https://cdn.jsdelivr.net/gh/devicons/devicon/icons/pytorch/pytorch-original.svg" width="48" height="48" alt="PyTorch" />
<br><b>PyTorch</b>
<br><sub>ML Framework</sub>
</td>
<td align="center" width="140">
<img src="https://cdn.jsdelivr.net/gh/devicons/devicon/icons/opencv/opencv-original.svg" width="48" height="48" alt="OpenCV" />
<br><b>OpenCV</b>
<br><sub>Computer Vision</sub>
</td>
<td align="center" width="140">
<img src="https://cdn.jsdelivr.net/gh/devicons/devicon/icons/numpy/numpy-original.svg" width="48" height="48" alt="NumPy" />
<br><b>NumPy</b>
<br><sub>Numeric Compute</sub>
</td>
<td align="center" width="140">
<img src="https://cdn.jsdelivr.net/gh/devicons/devicon/icons/docker/docker-original.svg" width="48" height="48" alt="Docker" />
<br><b>Docker</b>
<br><sub>Containerization</sub>
</td>
</tr>
<tr>
<td align="center" width="140">
<img src="https://upload.wikimedia.org/wikipedia/commons/5/5f/FFmpeg_Logo_new.svg" width="48" height="48" alt="FFmpeg" />
<br><b>FFmpeg</b>
<br><sub>Video Rendering</sub>
</td>
<td align="center" width="140">
<img src="https://cdn.jsdelivr.net/gh/simple-icons/simple-icons/icons/openai.svg" width="48" height="48" alt="Whisper" />
<br><b>OpenAI Whisper</b>
<br><sub>Transcription</sub>
</td>
<td align="center" width="140">
<img src="https://cdn.jsdelivr.net/gh/simple-icons/simple-icons/icons/nvidia.svg" width="48" height="48" alt="CUDA" />
<br><b>NVIDIA CUDA</b>
<br><sub>GPU Acceleration</sub>
</td>
<td align="center" width="140">
<img src="https://cdn.jsdelivr.net/gh/simple-icons/simple-icons/icons/youtube.svg" width="48" height="48" alt="YouTube" />
<br><b>YouTube API</b>
<br><sub>Auto Upload</sub>
</td>
<td align="center" width="140">
<img src="https://cdn.jsdelivr.net/gh/simple-icons/simple-icons/icons/pydantic.svg" width="48" height="48" alt="Pydantic" />
<br><b>Pydantic</b>
<br><sub>Config & Validation</sub>
</td>
</tr>
</table>
</div>

<div align="center">

### 📤 Export Platforms

[![YouTube Shorts](https://img.shields.io/badge/YouTube_Shorts-FF0000?style=for-the-badge&logo=youtube&logoColor=white)](https://youtube.com/shorts)&nbsp;
[![Instagram Reels](https://img.shields.io/badge/Instagram_Reels-E4405F?style=for-the-badge&logo=instagram&logoColor=white)](https://instagram.com)&nbsp;
[![TikTok](https://img.shields.io/badge/TikTok-000000?style=for-the-badge&logo=tiktok&logoColor=white)](https://tiktok.com)

</div>

<div align="center">

### ⚡ Powered By

![Whisper](https://img.shields.io/badge/OpenAI_Whisper-Speech_to_Text-412991?style=flat-square&logo=openai&logoColor=white)&nbsp;
![SceneDetect](https://img.shields.io/badge/PySceneDetect-Scene_Analysis-FF6F00?style=flat-square&logo=data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgZmlsbD0id2hpdGUiIHZpZXdCb3g9IjAgMCAyNCAyNCI+PHBhdGggZD0iTTQgOGgxNnYxMUg0eiIvPjxyZWN0IHg9IjIiIHk9IjQiIHdpZHRoPSIyMCIgaGVpZ2h0PSIxNiIgcng9IjIiIGZpbGw9Im5vbmUiIHN0cm9rZT0id2hpdGUiIHN0cm9rZS13aWR0aD0iMiIvPjwvc3ZnPg==&logoColor=white)&nbsp;
![OpenCV](https://img.shields.io/badge/OpenCV-Motion_Tracking-5C3EE8?style=flat-square&logo=opencv&logoColor=white)&nbsp;
![CUDA](https://img.shields.io/badge/NVIDIA-GPU_Accelerated-76B900?style=flat-square&logo=nvidia&logoColor=white)

![Typer](https://img.shields.io/badge/Typer-CLI_Framework-000000?style=flat-square&logo=gnubash&logoColor=white)&nbsp;
![Rich](https://img.shields.io/badge/Rich-Beautiful_Output-1E1E1E?style=flat-square&logo=windowsterminal&logoColor=white)&nbsp;
![YAML](https://img.shields.io/badge/YAML-Configuration-CB171E?style=flat-square&logo=yaml&logoColor=white)&nbsp;
![OAuth2](https://img.shields.io/badge/Google-OAuth2_Auth-4285F4?style=flat-square&logo=google&logoColor=white)

</div>

---

## TABLE OF CONTENTS

1. [Tech Stack](#️-tech-stack)
2. [Multi-Channel Architecture](#-multi-channel-architecture)
3. [Long-form Video Generation](#-long-form-video-generation)
4. [Scheduled Uploads](#-scheduled-uploads)
5. [macOS Setup (All Steps)](#-macos-complete-setup)
6. [Windows Setup (All Steps)](#-windows-complete-setup)
7. [YouTube API & Credentials Setup](#youtube-api--credentials-setup)
8. [Configuration Reference](#configuration-reference)
9. [Architecture & Pipeline](#architecture)
10. [Docker (Linux Servers)](#docker-linux-servers)
11. [Troubleshooting](#troubleshooting)

---

## 🎛️ Multi-Channel Architecture

The framework supports **multiple YouTube channels**, each with its own input folder, output folder, socials overlay, and YouTube credentials.

### Folder Structure

```
input/
├── krgd_vlogs/                  ← Channel: krgd_vlogs
│   ├── trip_01/                 ← Nested subfolders supported
│   │   ├── gopro_beach.mp4
│   │   └── gopro_sunset.mp4
│   └── trip_02/
│       └── drone_flight.mp4
├── techie_krishna_kayaking/     ← Channel: techie_krishna_kayaking
│   └── python_tips.mp4
├── krishna_kayaking/            ← Channel: krishna_kayaking
│   └── river_run.mp4
└── tkk_live_shorts/             ← Channel: tkk_live_shorts
    └── live_stream_clip.mp4

output/                          ← Flat per-channel output
├── krgd_vlogs/
│   ├── trip_01_gopro_beach_part001.mp4
│   ├── trip_01_gopro_beach_part001.json
│   ├── trip_01_gopro_sunset_part001.mp4
│   ├── trip_02_drone_flight_part001.mp4
│   └── longform/               ← Long-form merged videos
│       ├── trip_01_full.mp4     ← All trip_01 clips merged (16:9)
│       └── trip_02_full.mp4
├── techie_krishna_kayaking/
│   └── python_tips_part001.mp4
├── krishna_kayaking/
│   └── river_run_part001.mp4
└── tkk_live_shorts/
    └── live_stream_clip_part001.mp4

assets/social/                   ← Per-channel socials overlays
├── krgd_vlogs_socials.png
├── tkk_socials.png
└── kk_socials.png
```

### Key Concepts

- **Channel = input folder + output folder + socials image + YouTube credentials**
- Videos in nested subfolders are discovered recursively (e.g., `trip_01/`, `trip_02/`)
- Output is **flat per channel** — subfolder names are prefixed to the video name:
  `input/krgd_vlogs/trip_01/beach.mp4` → `output/krgd_vlogs/trip_01_beach_part001.mp4`
- Each channel has its own socials overlay PNG (branding image burned into shorts)
- YouTube credentials are per-channel for multi-account upload support
- **Upload uses the output filename as the YouTube video title** automatically

### Rendering Modes by Channel Type

| Channel Type | Rendering | Description |
|---|---|---|
| `tutorial` | Smart crop 16:9 → 9:16 | Face-aware cropping, fills the entire vertical frame |
| `gopro` | White letterbox | Video centered on white 9:16 canvas (no camera area lost), "WATCH THE FULL VIDEO" + YouTube logo at top, socials at bottom |
| `vertical` | Trim only | Already 9:16, just split at boundaries |

**Additionally for `gopro` channels:** Long-form videos are auto-generated per subfolder (see below).

### CLI Quick Reference

```bash
# MAIN COMMAND 1: List all configured channels
python3 -m app.main channels

# MAIN COMMAND 2: Fast batch-all (quick runs/testing)
python3 -m app.main batch-all --fast --max-clips 1008

# MAIN COMMAND 3: Quality batch-all (final runs)
python3 -m app.main batch-all --max-clips 1008

# Render clips
python3 -m app.main batch --channel tkk_live_shorts --max-clips 108
python3 -m app.main batch --channel techie_krishna_kayaking --max-clips 108
python3 -m app.main batch --channel krgd_vlogs --max-clips 108
python3 -m app.main batch --channel krishna_kayaking --max-clips 108

# Schedule uploads
python3 -m app.main schedule output/tkk_live_shorts/ --channel tkk_live_shorts
python3 -m app.main schedule output/techie_krishna_kayaking/ --channel techie_krishna_kayaking
python3 -m app.main schedule output/krgd_vlogs/ --channel krgd_vlogs
python3 -m app.main schedule output/krishna_kayaking/ --channel krishna_kayaking

# Execute all pending scheduled uploads
python3 -m app.main execute-schedule
```

Fast vs non-fast:

- Use `--fast` for speed.
- Omit `--fast` for better transcription/caption quality.

### Other CLI Commands

```bash
# Process a mixed-media vlog folder (phone videos + photos + action cam clips)
python3 -m app.main vlog input/krgd_vlogs/2026-05-30-Savandurga_NarashimaTemple_BigBanyanTree_RanganathTemple --channel krgd_vlogs

# Backward-compatible alias for vlog command
python3 -m app.main trip input/krgd_vlogs/2026-05-30-Savandurga_NarashimaTemple_BigBanyanTree_RanganathTemple --channel krgd_vlogs

# Refresh trending audio manifests from configured provider
python3 -m app.main refresh-trending-audio --limit 50

# Process a single channel (auto-generates long-form for gopro channels)
python3 -m app.main batch --channel krgd_vlogs --fast --max-clips 3

# Generate ONLY long-form videos (no shorts)
python3 -m app.main longform --channel krgd_vlogs

# Long-form for a specific subfolder only
python3 -m app.main longform --channel krgd_vlogs --subfolder 2026-05-14

# Long-form without social watermark
python3 -m app.main longform --channel krgd_vlogs --no-overlay

# Process a single video for a channel
python3 -m app.main process input/krgd_vlogs/trip_01/beach.mp4 --channel krgd_vlogs

# Batch with explicit directory
python3 -m app.main batch input/tutorials/ --channel techie_krishna_kayaking

# Watch a channel's input folder for new videos
python3 -m app.main watch --channel krgd_vlogs --fast

# Fast mode: uses tiny Whisper model + MPS GPU, ~2x faster
python3 -m app.main process video.mp4 --channel krgd_vlogs --fast
```

### Mixed-Media Vlog Workflow (Phone + Photos + GoPro)

Use this when a single folder contains mixed media from multiple devices.

Pipeline:

```text
Vlog Folder (videos + photos)
  -> Chronological long-form (metadata timestamps preferred)
  -> Existing shorts selection/render flow
  -> Platform exports:
     - YouTube shorts: original audio only
     - Instagram reels: original audio + background music mix
  -> Optional upload + move-to-trash cleanup on successful upload only
```

Run:

```bash
# End-to-end workflow for any vlog folder
python3 -m app.main vlog input/krgd_vlogs/2026-05-30-Savandurga_NarashimaTemple_BigBanyanTree_RanganathTemple --channel krgd_vlogs

# Skip upload while testing renders/exports
python3 -m app.main vlog input/krgd_vlogs/2026-05-30-Savandurga_NarashimaTemple_BigBanyanTree_RanganathTemple --channel krgd_vlogs --no-upload
```

Notes:

- Photos are inserted into the timeline with optional Ken Burns motion.
- Mixed orientations preserve content with background padding (no stretch).
- Cleanup runs only when all YouTube uploads succeed.

---

## 🚀 Automated YouTube Upload Features

When uploading videos to YouTube, the framework automatically handles several tasks without manual intervention:

### Auto-Upload Captions

- If a `.srt` (SRT subtitle) file exists alongside the video, it's automatically uploaded as English captions
- Captions appear instantly on YouTube without manual steps
- Sidecar `.srt` files are generated during the rendering process (step 3 in the pipeline)

**Configuration:**
```yaml
youtube:
  auto_upload_captions: true   # Enable auto-upload of SRT captions
```

### Monetization & Content Settings

For monetized channels, the framework automatically applies:

- **Monetization**: Enable ad monetization on the video (if channel is monetization-eligible)
- **Made for Kids**: Mark videos as made-for-kids or not (affects ad policies)
- **License Type**: Set the license to "youtube" (standard) or "creativeCommon"

**Configuration:**
```yaml
youtube:
  monetization_enabled: true      # Enable ads on this video
  made_for_kids: false            # Video is NOT made for kids
  license_type: "youtube"         # youtube or creativeCommon
```

**Important Notes:**
- Your YouTube channel must be part of the YouTube Partner Program to earn ad revenue (manual approval required)
- These settings are applied automatically during upload but cannot override YouTube's overall channel eligibility
- "Made for Kids" designation has strict FTC compliance requirements—set accurately

**Example:**
```yaml
techie_krishna_kayaking:
  upload_enabled: true
  youtube:
    auto_upload_captions: true
    monetization_enabled: true
    made_for_kids: false
    license_type: "youtube"
```

### Scheduled Batch Uploads (7-Day Spread)

Upload multiple videos automatically over 7 days at specific times per day:

**Default Schedule:** 4 videos/day at **1:07 PM, 3:07 PM, 5:07 PM, 9:07 PM UTC**

**How It Works:**

1. Schedule videos with a single command
2. Videos are queued with precise publish times based on your channel's daily schedule
3. Run `execute-schedule` to upload all pending videos at their scheduled times
4. If you run `schedule` again on day 6-7, it automatically continues from where the last upload left off

**Example: Upload 8 videos across 2 days**

```bash
# Schedule 8 videos for tkk_live_shorts (automatically spreads across days)
# First 4 upload today at 1:07 PM, 3:07 PM, 5:07 PM, 9:07 PM
# Next 4 upload tomorrow at the same times
python3 -m app.main schedule output/tkk_live_shorts/ --channel tkk_live_shorts

# Execute uploads when ready (runs at each scheduled time)
python3 -m app.main execute-schedule
```

**Configuration:**

```yaml
youtube:
  schedule_times:           # Daily upload times (HH:MM format, UTC)
    - "13:07"              # 1:07 PM
    - "15:07"              # 3:07 PM
    - "17:07"              # 5:07 PM
    - "21:07"              # 9:07 PM
  schedule_duration_days: 7  # Max 7 days before stopping
```

**Smart Continuation:**

If you run `schedule` on day 6-7 of an ongoing schedule:
- The system detects the last upload time from the existing schedule
- New videos continue immediately after (no gap)
- Example: Last upload was 2026-06-07 21:07, next new video schedules for 2026-06-08 13:07

---

## 🎬 Long-form Video Generation

For **gopro** channels, the framework automatically generates long-form vlog compilations in addition to short-form clips.

### How It Works

1. Each **subfolder** in the channel's input directory becomes one long-form video
2. All clips within the subfolder are **sorted chronologically** (GoPro naming-aware: video number → chapter order)
3. Clips are merged into a single continuous **16:9 landscape** video
4. A **social branding watermark** is applied in the top-left corner (subtle, 15% width, 60% opacity)
5. Output uses high-quality encoding (CRF 18, medium preset, AAC 192k)

### GoPro File Ordering

GoPro cameras name files as `GHxxyyyy.MP4` where `xx` = chapter, `yyyy` = video number.
The framework sorts correctly:

```
GH011244.MP4  →  Video 1244, Chapter 1  (plays first)
GH021244.MP4  →  Video 1244, Chapter 2
GH031244.MP4  →  Video 1244, Chapter 3
GH011245.MP4  →  Video 1245, Chapter 1  (plays after all 1244 chapters)
GH021245.MP4  →  Video 1245, Chapter 2
```

### Output Structure

```
output/krgd_vlogs/
├── 2026-05-14_gh011244_part001.mp4     ← Short-form clips (9:16)
├── 2026-05-14_gh011244_part002.mp4
└── longform/
    ├── 2026-05-14_full.mp4             ← All May 14 clips merged (16:9)
    └── 2026-05-15_full.mp4             ← All May 15 clips merged (16:9)
```

### Commands

```bash
# Generate long-form videos only (standalone)
python3 -m app.main longform --channel krgd_vlogs

# Process a specific subfolder
python3 -m app.main longform --channel krgd_vlogs --subfolder 2026-05-14

# Skip the social watermark overlay
python3 -m app.main longform --channel krgd_vlogs --no-overlay

# batch and batch-all auto-trigger long-form for gopro channels
python3 -m app.main batch --channel krgd_vlogs --fast --max-clips 3
python3 -m app.main batch-all --fast --max-clips 3
```

### Processing Report

After long-form generation completes, a detailed report prints:

```
══════════════════════════════════════════════════════════════
           PROCESSING REPORT
══════════════════════════════════════════════════════════════

  Channel:               krgd vlogs (krgd_vlogs)

  ── Input ──
  Videos detected:         8
  Videos processed:        8
  Skipped/failed files:    0
  Duplicates detected:     0
  Total input duration:    78.5 min (1.31 hrs)

  ── Output ──
  Short-form videos:       24
  Long-form videos:        1 created, 0 failed
  Total output duration:   78.2 min (1.30 hrs)
  Total output size:       2304 MB (2.25 GB)

  ── Performance ──
  Total processing time:   1845s (30.8 min)
  Processing speed:        2.6x realtime

  ── Output Files ──
  ✓ output/krgd_vlogs/longform/2026-05-14_full.mp4
      Duration: 78.2 min | Size: 2304 MB

══════════════════════════════════════════════════════════════
```

---
---

## 📅 Scheduled Uploads

The framework includes an intelligent upload scheduler (`schedule_uploads.py`) that distributes Shorts and long-form uploads across days with specific time slots per channel.

### Schedule Rules

| Type | Frequency | Times (Local) |
|------|-----------|---------------|
| **Shorts** | 3 per day × 3 days | 3:07 PM, 5:07 PM, 7:07 PM |
| **Long-form** | 1 per Thursday | 7:07 PM |

### Channel Hashtags

Each channel automatically appends its hashtag to video titles:

| Channel | Hashtag |
|---------|---------|
| `krgd_vlogs` | `#krgdVlog #shorts` |
| `tkk_live_shorts` | `#TKK #shorts` |

### How It Works

1. Videos are picked from each channel's output folder in **sequential filename order**
2. Titles are auto-generated from filenames (cleaned: underscores → spaces, timestamps removed, title-cased)
3. Videos are uploaded as **private** with a `publishAt` schedule time
4. YouTube auto-publishes them at the scheduled time
5. Long-form videos are only scheduled if available (non-part files in the output folder)

### Usage

```bash
# Preview the schedule (dry run — no uploads)
python3 schedule_uploads.py

# Execute uploads for real
python3 schedule_uploads.py --execute
```

### Example Output (Dry Run)

```
================================================================
 YouTube Upload Scheduler
================================================================
 Mode: DRY RUN (preview)
 Date: Thu May 28, 2026 05:33 AM PDT
 Schedule: 3 shorts/day × 3 days
           Times: 15:07, 17:07, 19:07
           Long-form: Thursdays at 19:07
================================================================

  Channel: krgd vlogs
  Shorts available: 5

  Shorts Schedule (5 videos):
  ────────────────────────────────────────────────────────────
   1. gh011244_part001.mp4
      Title: Gh011244 Part001 #krgdVlog #shorts
      Publish: Fri May 29, 2026 at 03:07 PM PDT
   2. gh011244_part002.mp4
      Title: Gh011244 Part002 #krgdVlog #shorts
      Publish: Fri May 29, 2026 at 05:07 PM PDT
   ...

  Channel: TKK Live & Shorts
  Shorts available: 78

  Shorts Schedule (9 videos):
  ────────────────────────────────────────────────────────────
   1. azure_..._part001.mp4
      Title: Azure Insurance Project Part 1 Part001 #TKK #shorts
      Publish: Fri May 29, 2026 at 03:07 PM PDT
   ...
================================================================
```

### Configuration

Edit the constants at the top of `schedule_uploads.py` to adjust:

```python
LOCAL_TZ = ZoneInfo("America/Los_Angeles")  # Your timezone
SHORTS_PER_DAY = 3                          # Shorts per day
SHORTS_DAYS = 3                             # Number of days to schedule
SHORTS_TIMES = [(15, 7), (17, 7), (19, 7)]  # Upload times (hour, minute)
LONGFORM_DAY = 3                            # 0=Mon, 3=Thu, 6=Sun
LONGFORM_TIME = (19, 7)                     # Long-form upload time
CHANNELS_TO_SCHEDULE = ["krgd_vlogs", "tkk_live_shorts"]
```

---
---

## 🍎 macOS COMPLETE SETUP

Follow these steps in order on your Mac.

---

### Step 1: Install Homebrew

If you already have Homebrew, skip this.

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

---

### Step 2: Install Python 3.11+ and FFmpeg

```bash
brew install python@3.11 ffmpeg
```

Verify:
```bash
python3 --version
# Should show: Python 3.11.x or higher

ffmpeg -version
# Should show FFmpeg version info
```

**Note:** macOS does NOT support NVIDIA CUDA. The framework uses CPU encoding (works fine). Apple Silicon Macs get MPS acceleration for Whisper automatically.

---

### Step 3: Clone the Project & Create Virtual Environment

```bash
cd ~/Projects   # or wherever you keep code

# If cloning fresh:
git clone <your-repo-url> tkk-try

cd tkk-try

# Create virtual environment
python3 -m venv .venv

# Activate it (you must do this every time you open a new terminal)
source .venv/bin/activate

# Verify
which python
# Should show: /path/to/tkk-try/.venv/bin/python
```

---

### Step 4: Install Python Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt

# Install PyTorch (MPS acceleration auto-detected on Apple Silicon)
pip install torch torchaudio
```

Verify everything installed:
```bash
python -c "import whisper; print('Whisper OK')"
python -c "import cv2; print('OpenCV OK')"
python -c "import torch; print(f'MPS available: {torch.backends.mps.is_available()}')"
```

---

### Step 5: Download Font for Captions

```bash
curl -L "https://github.com/JulietaUla/Montserrat/raw/master/fonts/ttf/Montserrat-Bold.ttf" \
    -o assets/fonts/Montserrat-Bold.ttf
```

---

### Step 6: Add Your Social Footer Images

Create or place a PNG image (1080px wide, ~150-200px tall) per channel in the assets folder.
This image appears at the bottom of every generated short (your logo, social handles, etc).

```bash
# One image per channel — referenced in configs/channels.yaml
cp /path/to/your/my_vlogs_footer.png assets/social/my_vlogs_socials.png
cp /path/to/your/my_tutorials_footer.png assets/social/my_tutorials_socials.png
```

If you don't have one yet, the framework works without it — just leave `socials_file` empty in channel config.

---

### Step 7: Configure Your Channels

Edit `configs/channels.yaml` to add your channels:

```bash
open configs/channels.yaml
# Or: code configs/channels.yaml
# Or: nano configs/channels.yaml
```

Each channel defines its own input folder, output folder, socials image, and YouTube credentials.
See [Configuration Reference](#configuration-reference) below for all fields.

Edit `configs/app.yaml` if you want to change processing settings (defaults work fine to start).

---

### Step 8: Place Videos in the Channel Input Folders

```bash
# Videos go into each channel's input folder (supports nested subfolders):
cp /path/to/your/tutorial.mp4 input/techie_krishna_kayaking/
cp /path/to/your/gopro_clip.mp4 input/krgd_vlogs/trip_01/
cp /path/to/your/river_run.mp4 input/krishna_kayaking/summer_2025/
```

Nested folders like `trip_01/` are supported — the subfolder name is prefixed to the output filename.

---

### Step 9: Run the Framework

```bash
# Make sure your venv is active!
source .venv/bin/activate

# List all configured channels and video counts
python3 -m app.main channels

# ⚡ Process ALL channels at once (easiest — just put videos in folders and run)
python3 -m app.main batch-all --fast --max-clips 3

# Process a single channel only
python3 -m app.main batch --channel krgd_vlogs --fast --max-clips 3

# Process a single video (specify channel for output routing)
python3 -m app.main process input/krgd_vlogs/trip_01/beach.mp4 --channel krgd_vlogs --fast

# Check video info first (no processing)
python3 -m app.main info input/krgd_vlogs/trip_01/beach.mp4

# Watch mode — auto-process new videos dropped into channel folder
python3 -m app.main watch --channel krgd_vlogs --fast
# Press Ctrl+C to stop

# Upload a generated short (requires YouTube API setup — see below)
python3 -m app.main upload output/krgd_vlogs/trip_01_beach_part001.mp4 \
    --channel krgd_vlogs --title "Epic Beach Adventure"

# Schedule multiple uploads (uses channel's daily upload times for 7 days)
# Default: 4 videos/day at 1:07 PM, 3:06 PM, 5:07 PM, 9:07 PM UTC
python3 -m app.main schedule output/krgd_vlogs/ --channel krgd_vlogs

# Or use custom hourly interval (e.g., every 24 hours)
python3 -m app.main schedule output/krgd_vlogs/ --channel krgd_vlogs --interval 24

# Execute all scheduled uploads (runs pending uploads, continues from last if re-run on day 6-7)
python3 -m app.main execute-schedule
```

---

### Step 10: Check Your Output

```bash
ls output/krgd_vlogs/

# Flat per-channel output (subfolder names prefixed):
# trip_01_beach_part001.mp4    ← Ready-to-upload short
# trip_01_beach_part001.srt    ← Subtitles (SRT)
# trip_01_beach_part001.ass    ← Subtitles (styled ASS)
# trip_01_beach_part001.json   ← Metadata (score, timestamps, transcript)
# trip_01_beach_part002.mp4
# ...
```

---

### 🍎 macOS Quick Reference (Copy-Paste All at Once)

```bash
brew install python@3.11 ffmpeg
cd tkk-try && python3 -m venv .venv && source .venv/bin/activate
pip install --upgrade pip && pip install -r requirements.txt && pip install torch torchaudio
curl -L "https://github.com/JulietaUla/Montserrat/raw/master/fonts/ttf/Montserrat-Bold.ttf" -o assets/fonts/Montserrat-Bold.ttf
cp ~/Downloads/my_gopro.mp4 input/krgd_vlogs/trip_01/
python3 -m app.main channels
python3 -m app.main batch-all --fast --max-clips 3
```

---
---

## 🪟 WINDOWS COMPLETE SETUP

Follow these steps in order on Windows using **PowerShell**.

---

### Step 1: Install Python 3.11+

1. Go to https://www.python.org/downloads/
2. Download **Python 3.11+** installer (Windows installer 64-bit)
3. Run the installer
4. **CRITICAL:** Check ✅ **"Add Python to PATH"** at the bottom of the installer
5. Click "Install Now"
6. **Close and reopen PowerShell** after installation

Verify:
```powershell
python --version
# Should show: Python 3.11.x or higher
```

If `python` is not recognized, the PATH wasn't set. Reinstall Python and check the PATH box.

---

### Step 2: Install FFmpeg

**Option A — Using winget (easiest, Windows 10/11):**
```powershell
winget install FFmpeg
```

**Option B — Using Chocolatey:**
```powershell
choco install ffmpeg
```

**Option C — Manual install:**
1. Go to https://www.gyan.dev/ffmpeg/builds/
2. Download **"ffmpeg-release-essentials.zip"**
3. Extract the zip to `C:\ffmpeg`
4. Add FFmpeg to PATH:
   - Press `Win + S`, search **"Environment Variables"**
   - Click "Edit the system environment variables"
   - Click "Environment Variables" button
   - Under "System variables", find **Path** → Click Edit
   - Click "New" → Add: `C:\ffmpeg\bin`
   - Click OK on all dialogs
   - **Close and reopen PowerShell**

Verify:
```powershell
ffmpeg -version
# Should show FFmpeg version info
```

---

### Step 3: (OPTIONAL) Install NVIDIA CUDA

**Skip this if you don't have an NVIDIA GPU.** The framework works without it (CPU encoding, just slower).

1. Go to https://developer.nvidia.com/cuda-downloads
2. Select: Windows → x86_64 → Your Windows version → exe (local)
3. Download and run installer (select Express Install)
4. Verify:
```powershell
nvidia-smi
# Should show your GPU name and driver version
```

---

### Step 4: Clone the Project & Create Virtual Environment

```powershell
# Navigate to your projects folder
cd C:\Users\YourName\Projects

# Clone the repo (or skip if you already have it)
git clone <your-repo-url> tkk-try
cd tkk-try

# Create Python virtual environment
python -m venv .venv

# Activate it (you must do this every time you open a new PowerShell)
.venv\Scripts\Activate.ps1

# If you get an "execution policy" error, run this ONCE:
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
# Then try activating again: .venv\Scripts\Activate.ps1

# Verify — you should see (.venv) at the start of your prompt
where python
# Should show: C:\Users\YourName\Projects\tkk-try\.venv\Scripts\python.exe
```

---

### Step 5: Install Python Dependencies

```powershell
pip install --upgrade pip
pip install -r requirements.txt
```

**If you have an NVIDIA GPU (Step 3 done):**
```powershell
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu121
```

**If you do NOT have an NVIDIA GPU:**
```powershell
pip install torch torchaudio
```

Verify:
```powershell
python -c "import whisper; print('Whisper OK')"
python -c "import cv2; print('OpenCV OK')"
python -c "import torch; print(f'CUDA available: {torch.cuda.is_available()}')"
```

---

### Step 6: Download Font for Captions

```powershell
Invoke-WebRequest -Uri "https://github.com/JulietaUla/Montserrat/raw/master/fonts/ttf/Montserrat-Bold.ttf" `
    -OutFile "assets\fonts\Montserrat-Bold.ttf"
```

---

### Step 7: Add Your Social Footer Images

Create or place a PNG image (1080px wide, ~150-200px tall) per channel in the assets folder.
This image appears at the bottom of every generated short (your logo, social handles, etc).

```powershell
# One image per channel — referenced in configs\channels.yaml
Copy-Item "C:\path\to\your\my_vlogs_footer.png" -Destination "assets\social\my_vlogs_socials.png"
Copy-Item "C:\path\to\your\my_tutorials_footer.png" -Destination "assets\social\my_tutorials_socials.png"
```

If you don't have one yet, the framework works without it — just leave `socials_file` empty in channel config.

---

### Step 8: Configure Your Channels

Open the config file in your editor:
```powershell
notepad configs\channels.yaml
# Or: code configs\channels.yaml
```

Each channel defines its own input folder, output folder, socials image, and YouTube credentials.
See [Configuration Reference](#configuration-reference) below for all fields.

Also edit `configs\app.yaml` if you want to change processing settings (defaults work fine to start).

---

### Step 9: Place Videos in the Channel Input Folders

```powershell
# Videos go into each channel's input folder (supports nested subfolders):
Copy-Item "C:\path\to\your\tutorial.mp4" -Destination "input\techie_krishna_kayaking\"
Copy-Item "C:\path\to\your\gopro_clip.mp4" -Destination "input\krgd_vlogs\trip_01\"
Copy-Item "C:\path\to\your\river_run.mp4" -Destination "input\krishna_kayaking\summer_2025\"
```

Or simply **drag-and-drop** video files into the folders using File Explorer.
Nested folders like `trip_01\` are supported — the subfolder name is prefixed to the output filename.

---

### Step 10: Run the Framework

```powershell
# Make sure your venv is active!
.venv\Scripts\Activate.ps1

# List all configured channels and video counts
python3 -m app.main channels

# ⚡ Process ALL channels at once (easiest — just put videos in folders and run)
python3 -m app.main batch-all --fast --max-clips 3

# Process a single channel only
python3 -m app.main batch --channel krgd_vlogs --fast --max-clips 3

# Process a single video
python3 -m app.main process input\krgd_vlogs\trip_01\beach.mp4 --channel krgd_vlogs --fast

# Check video info first (no processing)
python3 -m app.main info input\krgd_vlogs\trip_01\beach.mp4

# Watch mode — auto-process new videos dropped into channel folder
python3 -m app.main watch --channel krgd_vlogs --fast
# Press Ctrl+C to stop

# Upload a generated short (requires YouTube API setup — see below)
python3 -m app.main upload output\krgd_vlogs\trip_01_beach_part001.mp4 `
    --channel krgd_vlogs --title "Epic Beach Adventure"

# Schedule multiple uploads (one per day)
python3 -m app.main schedule output\krgd_vlogs\ --channel krgd_vlogs --interval 24

# Execute all scheduled uploads
python3 -m app.main execute-schedule
```

---

### Step 11: Check Your Output

```powershell
dir output\krgd_vlogs\

# Flat per-channel output (subfolder names prefixed):
# trip_01_beach_part001.mp4    ← Ready-to-upload short
# trip_01_beach_part001.srt    ← Subtitles (SRT)
# trip_01_beach_part001.ass    ← Subtitles (styled ASS)
# trip_01_beach_part001.json   ← Metadata (score, timestamps, transcript)
# trip_01_beach_part002.mp4
# ...
```

---

### 🪟 Windows Quick Reference (Copy-Paste)

```powershell
winget install Python.Python.3.11
winget install FFmpeg
# ⚠️ RESTART PowerShell here!
cd C:\Users\YourName\Projects\tkk-try
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r requirements.txt
pip install torch torchaudio
Invoke-WebRequest -Uri "https://github.com/JulietaUla/Montserrat/raw/master/fonts/ttf/Montserrat-Bold.ttf" -OutFile "assets\fonts\Montserrat-Bold.ttf"
Copy-Item "$HOME\Downloads\my_gopro.mp4" -Destination "input\krgd_vlogs\trip_01\"
python3 -m app.main channels
python3 -m app.main batch-all --fast --max-clips 3
```

---
---

## YouTube API & Credentials Setup

This section explains the YouTube credential files. **Skip entirely if you don't need auto-upload.**

---

### Two Types of Credential Files

| File | What It Is | How You Get It |
|------|-----------|----------------|
| `client_secret_<channel>.json` | OAuth app identity (from Google Cloud) | Download from Google Cloud Console |
| `credentials_<channel>.json` | Your saved login token | Auto-generated after first OAuth login |

---

### File 1: `client_secret_tech.json` — You Download This from Google

This is the OAuth client identity file. You get it from Google Cloud Console.

**Example structure** (see `configs/client_secret_example.json`):

```json
{
  "installed": {
    "client_id": "123456789012-abcdefghijklmnopqrstuvwxyz123456.apps.googleusercontent.com",
    "project_id": "your-project-name-123456",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    "client_secret": "GOCSPX-XXXXXXXXXXXXXXXXXXXXXXXXXX",
    "redirect_uris": ["http://localhost"]
  }
}
```

**How to get this file (step by step):**

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click the project dropdown at the top → **"New Project"**
3. Name it (e.g., "Shorts Automation") → Click Create
4. Select your new project from the dropdown
5. In the left sidebar: **APIs & Services → Library**
6. Search **"YouTube Data API v3"** → Click it → Click **Enable**
7. In the left sidebar: **APIs & Services → Credentials**
8. Click **+ CREATE CREDENTIALS** → **OAuth client ID**
9. If asked to "Configure consent screen":
   - User type: **External** → Create
   - App name: anything (e.g., "Shorts Uploader")
   - User support email: your email
   - Developer contact: your email
   - Click Save and Continue through all steps
   - Under **Test users** → Add your Google/YouTube email
   - Click Save
10. Back to Credentials → **+ CREATE CREDENTIALS → OAuth client ID**
11. Application type: **Desktop app**
12. Name: anything (e.g., "Desktop Client")
13. Click **Create**
14. Click the **⬇ Download** button (or "Download JSON")
15. Save the downloaded file as:
    ```
    configs/client_secret_tech.json
    ```
    (Replace `tech` with your channel name from `channels.yaml`)

---

### File 2: `credentials_tech.json` — Auto-Generated (Do NOT Create Manually)

This file is created **automatically** the first time you run an upload command. You never write this file yourself.

**What happens:**
1. You run: `python3 -m app.main upload output/clip.mp4 --channel tech_channel`
2. A browser window opens → Google login page
3. You sign in with your YouTube account
4. You click "Allow" to grant upload permission
5. The framework saves the OAuth token as `configs/credentials_tech.json`
6. All future uploads use this cached token — no browser needed

**After auto-generation, it looks like** (see `configs/credentials_example.json`):

```json
{
  "token": "ya29.a0AfH6SMBx...<long-access-token>...",
  "refresh_token": "1//0dx...<refresh-token>...",
  "token_uri": "https://oauth2.googleapis.com/token",
  "client_id": "123456789012-abcdefghijklmnopqrstuvwxyz123456.apps.googleusercontent.com",
  "client_secret": "GOCSPX-XXXXXXXXXXXXXXXXXXXXXXXXXX",
  "scopes": ["https://www.googleapis.com/auth/youtube.upload"],
  "expiry": "2026-05-25T12:00:00.000000Z"
}
```

**If uploads stop working:**
1. Delete `configs/credentials_tech.json`
2. Run any upload command again
3. Re-authenticate in the browser popup

---

### Multiple Channels

For each channel, you need a separate `client_secret` file (referenced in `configs/channels.yaml`):
```
configs/client_secret_krgd.json       ← for krgd_vlogs
configs/client_secret_tkk.json        ← for techie_krishna_kayaking & tkk_live_shorts
configs/client_secret_kk.json         ← for krishna_kayaking
```

Each one can be from the same Google Cloud project (just one OAuth client) or different projects.

---

### Security Notes

- **NEVER** commit `client_secret_*.json` or `credentials_*.json` to git
- The `.gitignore` already excludes these files
- If you accidentally commit them, revoke credentials in Google Cloud Console immediately
- Example files (`*_example.json`) are safe — they contain fake values

---
---

## Configuration Reference

### App Configuration (`configs/app.yaml`)

Controls video processing parameters, output settings, transcription, captions, and rendering.

```yaml
video:
  output_width: 1080        # Output video width (pixels)
  output_height: 1920       # Output video height (pixels)
  fps: 30                   # Output frame rate
  video_bitrate: "8M"       # Video bitrate
  audio_bitrate: "192k"     # Audio bitrate
  preset: "medium"          # Encoding speed (ultrafast → veryslow)
  crf: 18                   # Quality (0=lossless, 23=default, 51=worst)

shorts:
  min_duration: 15          # Minimum clip length in seconds
  max_duration: 60          # Maximum clip length in seconds
  target_duration: 45       # Ideal clip length
  silence_threshold: -40    # dB threshold for silence detection
  silence_min_duration: 2.0 # Minimum silence duration to count (seconds)

transcription:
  model: "base"             # Whisper model: tiny | base | small | medium | large
  language: "en"            # Language code
  word_timestamps: true     # Enable word-level timing
  device: "auto"            # auto | cuda | cpu | mps

captions:
  enabled: true             # Generate & burn subtitles
  font_size: 48             # Caption font size
  font_color: "#FFFFFF"     # Caption text color
  outline_color: "#000000"  # Caption outline color
  outline_width: 3          # Outline thickness
  max_words_per_line: 6     # Words per subtitle line

rendering:
  gpu_enabled: true         # Use GPU encoder (NVIDIA only)
  gpu_encoder: "h264_nvenc" # NVIDIA GPU encoder
  cpu_encoder: "libx264"    # CPU fallback encoder

processing:
  batch_size: 5             # Videos to process in parallel
  max_workers: 4            # Worker threads
  retry_attempts: 3         # Retries on failure

trip:
  photo_duration: 4.0       # Duration per inserted photo (seconds)
  ken_burns_enabled: true   # Apply subtle pan/zoom on photos
  blur_background_enabled: true  # Preserve aspect ratio with blur background
  instagram_music_volume: 0.2    # Background music mix for Instagram export
  trending_audio_count: 100      # Max tracks to load from manifests/provider
  cleanup_after_upload: true     # Move generated files to trash after successful upload
  output_width: 1920             # Long-form output width
  output_height: 1080            # Long-form output height
  instagram_trending_manifest: "configs/trending_audio_instagram.json"
  youtube_trending_manifest: "configs/trending_audio_youtube.json"
  trending_provider:
    enabled: false               # Auto-refresh manifests before export
    provider_type: "filesystem" # filesystem | remote_manifest | pixabay_audio
    source_dir: "assets/audio/trending"
    source_manifest_url: ""
    auth_env_var: ""
    download_dir: "assets/audio/ingested"
    request_timeout_seconds: 30
    pixabay_api_key_env: "PIXABAY_API_KEY"
    pixabay_category: "music"
    pixabay_order: "popular"
```

### Trending Audio (Free Automation)

The framework supports provider-based ingestion for Instagram background tracks.

Free legal option included:

- `pixabay_audio` provider (requires free Pixabay API key)

Setup:

```bash
export PIXABAY_API_KEY="your_key_here"
```

```yaml
trip:
  trending_provider:
    enabled: true
    provider_type: "pixabay_audio"
```

Refresh manifests manually:

```bash
python3 -m app.main refresh-trending-audio --limit 50
```

Manifests consumed by exports:

- `configs/trending_audio_instagram.json`
- `configs/trending_audio_youtube.json`

Important: Direct downloading of Instagram's own trending audio catalog is not documented in this project. The provider flow is designed for legal/local/licensed sources.

### Channel Configuration (`configs/channels.yaml`)

Each channel maps to its own input folder, output folder, socials overlay, and YouTube credentials.

#### Channel Types

The `type` field determines how `batch-all` processes each channel:

| Type | Workflow | Use Case |
|------|----------|----------|
| `vlog` | Mixed-media long-form first, then shorts from each subfolder | Phone videos + photos + action cam in same trip/event folder |
| `gopro` | Individual video processing + auto-generated long-form per subfolder | Mostly GoPro clips, handled as separate videos initially |
| `tutorial` | Individual video processing (shorts only) | Standalone tutorial/education videos |

```yaml
channels:
  krgd_vlogs:
    name: "krgd vlogs"
    type: "vlog"                          # vlog | gopro | tutorial
    youtube_url: "https://www.youtube.com/@krgd_vlogs"
    input_folder: "input/krgd_vlogs"      # For vlog: subfolders are mixed-media trips
    output_folder: "output/krgd_vlogs"    # Flat output per channel
    socials_file: "assets/social/krgd_vlogs_socials.png"  # Branding overlay
    intro_text: ""                        # Text at top of shorts
    hook_keywords:                        # Keywords that signal good clip start
      - "amazing"
      - "incredible"
      - "adventure"
    upload_enabled: false                 # Enable YouTube upload
    youtube:
      client_secrets: "configs/client_secret_krgd.json"
      credentials: "configs/credentials_krgd.json"
      default_tags: ["vlog", "gopro", "travel", "adventure"]
      default_category: "19"              # YouTube category ID
      privacy_status: "private"           # private | unlisted | public
      schedule_delay_hours: 48            # Hours between scheduled uploads

  techie_krishna_kayaking:
    name: "techie krishna kayaking"
    type: "tutorial"
    youtube_url: "https://www.youtube.com/@TechieKrishnaKayaking"
    input_folder: "input/techie_krishna_kayaking"
    output_folder: "output/techie_krishna_kayaking"
    socials_file: "assets/social/tkk_socials.png"
    intro_text: "Learn Faster"
    hook_keywords:
      - "how to"
      - "tip"
      - "mistake"
      - "shortcut"
      - "secret"
    upload_enabled: false
    youtube:
      client_secrets: "configs/client_secret_tkk.json"
      credentials: "configs/credentials_tkk.json"
      default_tags: ["tutorial", "tech", "kayaking"]
      default_category: "28"
      privacy_status: "private"
      schedule_delay_hours: 24             # Fallback interval if use_daily_times=False
      schedule_times:                      # Daily upload times (HH:MM format, UTC)
        - "13:07"                          # 1:07 PM
        - "15:07"                          # 3:07 PM
        - "17:07"                          # 5:07 PM
        - "21:07"                          # 9:07 PM
      schedule_duration_days: 7            # Max scheduling window (days)
      auto_upload_captions: true           # Auto-upload SRT captions after upload
      monetization_enabled: true           # Enable monetization on videos
      made_for_kids: false                 # Content is NOT made for kids
      license_type: "youtube"              # youtube | creativeCommon
```

---

## Output Structure

Output is **flat per channel**. Videos from nested input subfolders have the subfolder name prefixed.

```
output/
├── krgd_vlogs/
│   ├── trip_01_gopro_beach_part001.mp4     ← Short video clip
│   ├── trip_01_gopro_beach_part001.srt     ← SRT subtitles
│   ├── trip_01_gopro_beach_part001.ass     ← Styled ASS subtitles
│   ├── trip_01_gopro_beach_part001.json    ← Metadata & transcript
│   ├── trip_01_gopro_beach_part002.mp4
│   └── trip_02_drone_flight_part001.mp4
├── techie_krishna_kayaking/
│   ├── python_tips_part001.mp4
│   └── python_tips_part001.json
└── krishna_kayaking/
    └── river_run_part001.mp4
```

Naming pattern: `<subfolder>_<videoname>_part<NNN>.mp4`

(If the video is directly in the channel's input folder with no subfolder, the name is just `<videoname>_part<NNN>.mp4`)

---

## Features

- **Multi-channel support** with per-channel input/output folders, socials overlays, and YouTube credentials
- **Mixed-media vlog command** (`vlog`) for phone videos + photos + action camera footage in one folder
- **Chronological timeline merge** using metadata timestamp, then file create time, then modified time
- **Platform exports per short**: `_yt.mp4` (original audio) and `_insta.mp4` (music-mixed)
- **Provider-based trending audio ingestion** (`filesystem`, `remote_manifest`, `pixabay_audio`)
- **Safe post-upload cleanup** moves generated outputs to OS trash only after successful uploads
- **`batch-all` command** — process every video across all channels with one command
- **Gopro letterbox mode** — white 9:16 canvas with video centered (no camera area lost), "Watch the full video on YT" text at top, socials at bottom
- **Smart crop mode** — face-aware 16:9 → 9:16 cropping for tutorial channels
- **Fast mode** (`--fast`) — uses tiny Whisper model + GPU acceleration, ~2x faster processing
- **Filename as YouTube title** — upload/schedule automatically uses the output filename as the video title
- **Recursive subfolder discovery** — organize videos in nested folders (`trip_01/`, `trip_02/`)
- **Flat output per channel** — subfolder names prefixed to output filenames
- **`channels` command** — list all configured channels with video counts at a glance
- **Auto-detection** of video aspect ratio, category, and properties
- **Smart clip selection** using AI-powered content analysis
- **Speech transcription** with OpenAI Whisper (word-level timestamps)
- **Silence detection** for intelligent clip boundaries
- **Scene detection** using PySceneDetect
- **Motion analysis** with OpenCV for action videos
- **Caption generation** (SRT & ASS with word-level karaoke styling)
- **GPU acceleration** (NVIDIA NVENC / Apple MPS)
- **YouTube upload** with OAuth2, scheduling, multi-channel support
- **Folder watcher** for automatic processing
- **Batch processing** for large video libraries
- **Docker support** with GPU passthrough

## Supported Input

| Type | Aspect Ratio | Rendering | Description |
|------|-------------|-----------|-------------|
| OBS Tutorials | 16:9 | Smart crop → 9:16 | Face-aware cropping, hook detection, caption burn |
| GoPro/Action | 16:9 | White letterbox | Video centered on white canvas, no cropping, "Watch full video on YT" + socials |
| Vertical | 9:16 | Trim only | Split at silence/sentence boundaries |

---

## Architecture

```
app/
├── main.py              # CLI entry point (Typer) — process, batch, batch-all, channels, watch, upload, schedule
├── vlog_pipeline.py     # Generic vlog-facing API exports
├── trip_pipeline.py     # Mixed-media long-form + platform export orchestration
├── trending_audio_provider.py  # Provider-based audio ingestion and manifest refresh
├── cleanup.py           # Move generated assets to OS trash after successful upload
├── detector.py          # Video property detection & categorization
├── transcriber.py       # Whisper-based speech transcription (MPS/CUDA/CPU)
├── silence_detector.py  # FFmpeg silence detection
├── clip_selector.py     # AI clip selection & scoring (with --fast mode)
├── caption_generator.py # SRT/ASS subtitle generation
├── renderer.py          # FFmpeg rendering pipeline (runtime filter detection)
├── smart_crop.py        # Face-aware smart cropping
├── scene_detector.py    # PySceneDetect integration
├── motion_detector.py   # OpenCV motion analysis
├── uploader.py          # YouTube Data API uploader
├── scheduler.py         # Upload scheduling
└── utils/
    ├── config.py        # Pydantic config management (channels, app settings)
    ├── logging.py       # Structured logging (structlog + rich)
    └── files.py         # File/path utilities, channel video discovery, output naming

configs/
├── app.yaml             # Processing settings (video, shorts, transcription, captions)
├── channels.yaml        # Multi-channel configuration (input/output/socials/youtube)
├── trending_audio_instagram.json # Instagram export music manifest
├── trending_audio_youtube.json   # YouTube export music manifest
└── client_secret_*.json # YouTube OAuth credentials (per channel, gitignored)

assets/
├── fonts/               # Caption fonts (Montserrat-Bold.ttf)
└── social/              # Per-channel socials overlay images
```

## Processing Pipeline

```
Input Video (from channel input folder)
    │
    ├── Resolve channel config → socials_file, output_folder, type
    │
    ├── detect_video() → VideoInfo (resolution, fps, category)
    │
    ├── [Tutorial] → transcribe → find hooks → score clips
    │   └── smart_crop → render 9:16 with captions + socials overlay
    │
    ├── [GoPro] → motion_analyze → scene_detect → score excitement
    │   └── smart_crop → render 9:16 with socials overlay
    │
    └── [Vertical] → silence_detect → split at boundaries
        └── trim → render (preserve framing)
    │
    ├── Generate SRT + ASS subtitles
    ├── Export metadata JSON
    ├── Output to channel folder: output/<channel_id>/<subfolder>_<name>_partNNN.mp4
    │
    └── [Optional] Schedule YouTube upload (per-channel credentials)
```

**Fast mode** (`--fast`): Uses Whisper `tiny` model + MPS/CUDA GPU, skips word-level timestamps. ~2x faster.

---

## Docker (Linux Servers)

```bash
# Build
docker build -t shorts-ai .

# Run in watch mode with GPU
docker compose up shorts-ai

# Process a batch
docker compose --profile process up shorts-ai-process

# Run uploader
docker compose --profile upload up shorts-ai-uploader
```

**For GPU support (Linux only):**
```bash
sudo apt-get install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
docker run --rm --gpus all nvidia/cuda:12.2.0-base-ubuntu22.04 nvidia-smi
```

---

## Troubleshooting

### FFmpeg not found
```bash
# macOS
which ffmpeg
brew install ffmpeg
```
```powershell
# Windows
where ffmpeg
winget install FFmpeg
```

### "No module named whisper"
```bash
pip install openai-whisper
```

### Whisper out of memory
Reduce model size in `configs/app.yaml`:
```yaml
transcription:
  model: "tiny"  # Use "tiny" or "base" instead of "large"
```

### CUDA not detected (Windows only)
```powershell
nvidia-smi
python -c "import torch; print(torch.cuda.is_available())"
```
If False, reinstall PyTorch with CUDA:
```powershell
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu121
```

### GPU rendering not working
Set `gpu_enabled: false` in `configs/app.yaml` → uses CPU encoding (slower but always works).

### Upload authentication fails
1. Delete `configs/credentials_*.json`
2. Re-run upload command
3. Complete OAuth flow in browser

### Virtual environment not active
If you see `ModuleNotFoundError`, you forgot to activate the venv:
```bash
# macOS
source .venv/bin/activate
```
```powershell
# Windows
.venv\Scripts\Activate.ps1
```

### Processing is slow
- Use `--fast` flag for ~2x speedup (tiny Whisper model, GPU acceleration, no word timestamps)
- Use GPU encoding (needs NVIDIA GPU — Windows/Linux only; Apple Silicon uses MPS automatically)
- Use `transcription.model: "tiny"` (fastest, less accurate)
- Reduce `processing.max_workers` if running out of RAM
- For 2+ hour videos, expect 5-15 minutes processing time on CPU

### Trending audio ingestion returns 0 tracks

- Check provider settings in `configs/app.yaml` under `trip.trending_provider`
- If using `pixabay_audio`, ensure `PIXABAY_API_KEY` is exported in your shell
- Run `python3 -m app.main refresh-trending-audio --limit 20` and verify manifests are updated

### MPS / Apple Silicon issues
- Whisper word-level timestamps require CPU (float64 not supported on MPS)
- Use `--fast` mode to skip word timestamps and get full MPS acceleration
- If you see `RuntimeError: MPS does not support float64`, this is handled automatically

### "execution policy" error on Windows
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```
Then try activating the venv again.

---

## 📄 License

Internal use only.

---

<div align="center">

**Built by 👨‍💻 Krishna with ❤️ for Data Engineering**

### 📫 Let's Connect

<p align="center">
  <a href="https://www.linkedin.com/in/krishnakayaking/"><img src="https://img.shields.io/badge/LinkedIn-Krishna_Kayaking-0A66C2?style=flat-square&logo=linkedin" /></a>&nbsp;
  <a href="https://www.youtube.com/@TechieKrishnaKayaking"><img src="https://img.shields.io/badge/YouTube-Techie_Krishna_Kayaking-FF0000?style=flat-square&logo=youtube" /></a>&nbsp;
  <a href="https://www.techiekrishnakayaking.com/"><img src="https://img.shields.io/badge/Website-techiekrishnakayaking.com-000?style=flat-square&logo=google-chrome&logoColor=white" /></a>&nbsp;
  <a href="https://topmate.io/techie_krishna_kayaking"><img src="https://img.shields.io/badge/Topmate-Book_a_Session-FFCA28?style=flat-square&logo=bookstack&logoColor=black" /></a>&nbsp;
  <a href="https://www.instagram.com/techiekrishnakayaking/"><img src="https://img.shields.io/badge/Instagram-techiekrishnakayaking-E4405F?style=flat-square&logo=instagram&logoColor=white" /></a>&nbsp;
  <a href="mailto:KrishnaKayaking@gmail.com"><img src="https://img.shields.io/badge/Email-KrishnaKayaking@gmail.com-D14836?style=flat-square&logo=gmail&logoColor=white" /></a>&nbsp;
  <a href="https://play.google.com/store/apps/details?id=co.diaz.ycvkc&hl=en_IN"><img src="https://img.shields.io/badge/Play_Store-Download_App-414141?style=flat-square&logo=google-play&logoColor=white" /></a>
</p>

<p align="center">
  If you're working on <b>data platforms, analytics, or BI</b> and care about <b>data quality and automation</b>, feel free to reach out or open an issue/discussion on any repo here.
</p>

---

<p align="center">
  <img src="https://komarev.com/ghpvc/?username=techiekrishnakayaking&style=flat-square&color=blue" alt="Profile views" />
</p>