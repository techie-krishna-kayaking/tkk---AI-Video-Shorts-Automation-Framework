#!/usr/bin/env python3
"""Test with dynamic captions (not hardcoded)."""

from pathlib import Path
from app.renderer import Renderer, RenderJob
from app.detector import detect_video

source = Path("input/flows/vlog_gopro/2026-07-13-DAILY OFFICE VLOG-Home_Office_INFOBLOX_Rajajinagar_GoldenHeights_OfficeVlog_MotoVlog/GH011293.MP4")
output = Path("output/samples/style2_review/gh011293_10s_dynamic_captions.mp4")
output.parent.mkdir(parents=True, exist_ok=True)

video_info = detect_video(source)

# NO hardcoded captions - use dynamic from folder name
job = RenderJob(
    input_path=source,
    output_path=output,
    start=0.0,
    end=10.0,
    overlay_path=Path("assets/social/krgd_vlogs.png"),
    video_info=video_info,
    channel_type="gopro",
    gopro_layout="orange_70_15_15",
    caption_line1="",  # Empty = dynamic
    caption_line2="",  # Empty = dynamic
)

renderer = Renderer(skip_smart_crop=True)
result = renderer.render_clip(job)

print(f"Success: {result.success}")
print(f"File size: {result.file_size / 1024 / 1024:.1f} MB" if result.file_size else "N/A")
if not result.success:
    print(f"Error: {result.error}")
