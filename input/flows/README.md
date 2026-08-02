# Input Folder Guide (Type-Based Editing Flows)

Place your source videos/files in these folders based on editing style:

- Camera Facing Long Form:
  - input/flows/camera_facing/longform
- Camera Facing Short Form:
  - input/flows/camera_facing/shortform

- Vlog GoPro Long Form:
  - input/flows/vlog_gopro/longform
- Vlog GoPro Short Form (Editing Style 1):
  - input/flows/vlog_gopro/shorts_style1
- Vlog GoPro Short Form (Editing Style 2):
  - input/flows/vlog_gopro/shorts_style2

- Cooking Long Form:
  - input/flows/cooking/longform
- Cooking Short Form:
  - input/flows/cooking/shortform

- Tutorial Long Form:
  - input/flows/tutorial/longform
- Tutorial Short Form:
  - input/flows/tutorial/shortform

- Hyperlapse Merge:
  - input/flows/hyperlapse
  - Put both videos and images here.
  - Keep names in ascending order (for example: 1.mp4, 2.mp4, 3.mp4 and 1.jpg, 2.jpg, 3.jpg).

Run flows with:

python3 -m app.main run-flow --flow <flow_id>

Examples:

python3 -m app.main run-flow --flow vlog_gopro_short_form_editing_style_1
python3 -m app.main run-flow --flow vlog_gopro_short_form_editing_style_2
python3 -m app.main run-flow --flow hyperlapse_merge
