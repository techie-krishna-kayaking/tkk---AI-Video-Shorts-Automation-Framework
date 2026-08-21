#!/usr/bin/env python3
"""Quick test for app renderer with hardcoded captions and subtitles."""

import time
from pathlib import Path
from app.renderer import Renderer, RenderJob
from app.detector import VideoCategory, detect_video

# Source clip
source = Path("input/flows/vlog_gopro/2026-07-13-DAILY OFFICE VLOG-Home_Office_INFOBLOX_Rajajinagar_GoldenHeights_OfficeVlog_MotoVlog/GH011293.MP4")
output = Path("output/samples/style2_review/gh011293_10s_captions_subtitles.mp4")
output.parent.mkdir(parents=True, exist_ok=True)

# Get real video info
video_info = detect_video(source)

# Create render job WITH hardcoded captions and subtitle extraction
job = RenderJob(
    input_path=source,
    output_path=output,
    start=0.0,
    end=10.0,
    crop=None,
    overlay_path=Path("assets/social/krgd_vlogs.png"),
    hook_text="",
    video_info=video_info,
    channel_type="gopro",
    gopro_layout="orange_70_15_15",  # style2
    caption_line1="DAILY VLOG - IT ENGINEER",
    caption_line2="KTM DUKE 390",
)

# Render with skip_smart_crop=True
renderer = Renderer(skip_smart_crop=True)

print("=" * 70)
print("APP RENDERER TEST (GoPro style2, captions + subtitles)")
print("=" * 70)
start = time.time()
result = renderer.render_clip(job)
elapsed = time.time() - start

print(f"\nRender time: {elapsed:.1f}s")
print(f"Output: {result.output_path}")
print(f"Success: {result.success}")
print(f"File size: {result.file_size / 1024 / 1024:.1f} MB")
print(f"Duration: {result.duration:.1f}s")

if not result.success:
    print(f"Error: {result.error}")
else:
    print("\n✓ Render complete! Video with captions and subtitles created.")

