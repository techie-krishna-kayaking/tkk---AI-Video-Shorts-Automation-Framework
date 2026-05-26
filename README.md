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
3. [macOS Setup (All Steps)](#-macos-complete-setup)
4. [Windows Setup (All Steps)](#-windows-complete-setup)
5. [YouTube API & Credentials Setup](#youtube-api--credentials-setup)
6. [Configuration Reference](#configuration-reference)
7. [Architecture & Pipeline](#architecture)
8. [Docker (Linux Servers)](#docker-linux-servers)
9. [Troubleshooting](#troubleshooting)

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
│   └── trip_02_drone_flight_part001.mp4
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

### CLI Quick Reference

```bash
# List all configured channels
python -m app.main channels

# Process a single video for a channel
python -m app.main process input/krgd_vlogs/trip_01/beach.mp4 --channel krgd_vlogs

# Batch process all videos in a channel (recursive)
python -m app.main batch --channel krgd_vlogs --fast --max-clips 3

# Batch with explicit directory
python -m app.main batch input/tutorials/ --channel techie_krishna_kayaking

# Watch a channel's input folder for new videos
python -m app.main watch --channel krgd_vlogs --fast

# Fast mode: uses tiny Whisper model + MPS GPU, ~2x faster
python -m app.main process video.mp4 --channel krgd_vlogs --fast
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
python -m app.main channels

# Process a single video (specify channel for output routing)
python -m app.main process input/krgd_vlogs/trip_01/beach.mp4 --channel krgd_vlogs

# Fast mode — uses tiny Whisper model + MPS GPU, ~2x faster
python -m app.main process input/krgd_vlogs/trip_01/beach.mp4 --channel krgd_vlogs --fast

# Batch process all videos in a channel (recursive subfolder discovery)
python -m app.main batch --channel krgd_vlogs --fast --max-clips 3

# Batch with explicit directory
python -m app.main batch input/tutorials/ --channel techie_krishna_kayaking

# Check video info first (no processing)
python -m app.main info input/krgd_vlogs/trip_01/beach.mp4

# Watch mode — auto-process new videos dropped into channel folder
python -m app.main watch --channel krgd_vlogs --fast
# Press Ctrl+C to stop

# Upload a generated short (requires YouTube API setup — see below)
python -m app.main upload output/krgd_vlogs/trip_01_beach_part001.mp4 \
    --channel krgd_vlogs --title "Epic Beach Adventure"

# Schedule multiple uploads (one per day)
python -m app.main schedule output/krgd_vlogs/ --channel krgd_vlogs --interval 24

# Execute all scheduled uploads
python -m app.main execute-schedule
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
cp ~/Downloads/my_tutorial.mp4 input/techie_krishna_kayaking/
python -m app.main channels
python -m app.main process input/techie_krishna_kayaking/my_tutorial.mp4 --channel techie_krishna_kayaking --fast
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
python -m app.main channels

# Process a single video (specify channel for output routing)
python -m app.main process input\krgd_vlogs\trip_01\beach.mp4 --channel krgd_vlogs

# Fast mode — uses tiny Whisper model + GPU, ~2x faster
python -m app.main process input\krgd_vlogs\trip_01\beach.mp4 --channel krgd_vlogs --fast

# Batch process all videos in a channel (recursive subfolder discovery)
python -m app.main batch --channel krgd_vlogs --fast --max-clips 3

# Batch with explicit directory
python -m app.main batch input\tutorials\ --channel techie_krishna_kayaking

# Check video info first (no processing)
python -m app.main info input\krgd_vlogs\trip_01\beach.mp4

# Watch mode — auto-process new videos dropped into channel folder
python -m app.main watch --channel krgd_vlogs --fast
# Press Ctrl+C to stop

# Upload a generated short (requires YouTube API setup — see below)
python -m app.main upload output\krgd_vlogs\trip_01_beach_part001.mp4 `
    --channel krgd_vlogs --title "Epic Beach Adventure"

# Schedule multiple uploads (one per day)
python -m app.main schedule output\krgd_vlogs\ --channel krgd_vlogs --interval 24

# Execute all scheduled uploads
python -m app.main execute-schedule
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
Copy-Item "$HOME\Downloads\my_tutorial.mp4" -Destination "input\techie_krishna_kayaking\"
python -m app.main channels
python -m app.main process input\techie_krishna_kayaking\my_tutorial.mp4 --channel techie_krishna_kayaking --fast
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
1. You run: `python -m app.main upload output/clip.mp4 --channel tech_channel`
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
```

### Channel Configuration (`configs/channels.yaml`)

Each channel maps to its own input folder, output folder, socials overlay, and YouTube credentials.

```yaml
channels:
  krgd_vlogs:
    name: "krgd vlogs"
    type: "gopro"                         # tutorial | gopro | vertical
    youtube_url: "https://www.youtube.com/@krgd_vlogs"
    input_folder: "input/krgd_vlogs"      # Videos go here (subfolders OK)
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
      schedule_delay_hours: 24
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
- **Fast mode** (`--fast`) — uses tiny Whisper model + GPU acceleration, ~2x faster processing
- **Recursive subfolder discovery** — organize videos in nested folders (`trip_01/`, `trip_02/`)
- **Flat output per channel** — subfolder names prefixed to output filenames
- **`channels` command** — list all configured channels with video counts at a glance
- **Auto-detection** of video aspect ratio, category, and properties
- **Smart clip selection** using AI-powered content analysis
- **Speech transcription** with OpenAI Whisper (word-level timestamps)
- **Silence detection** for intelligent clip boundaries
- **Scene detection** using PySceneDetect
- **Motion analysis** with OpenCV for action videos
- **Smart cropping** with face detection (16:9 → 9:16)
- **Caption generation** (SRT & ASS with word-level karaoke styling)
- **GPU acceleration** (NVIDIA NVENC / Apple MPS)
- **YouTube upload** with OAuth2, scheduling, multi-channel support
- **Folder watcher** for automatic processing
- **Batch processing** for large video libraries
- **Docker support** with GPU passthrough

## Supported Input

| Type | Aspect Ratio | Processing |
|------|-------------|------------|
| OBS Tutorials | 16:9 | Smart crop → 9:16, hook detection, caption burn |
| GoPro/Action | 16:9 | Motion analysis, excitement scoring, scene transitions |
| Vertical | 9:16 | Trim at silence/sentence boundaries |

---

## Architecture

```
app/
├── main.py              # CLI entry point (Typer) — process, batch, channels, watch, upload, schedule
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