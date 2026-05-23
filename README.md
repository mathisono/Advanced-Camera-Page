# Advanced Camera Page

Advanced Camera Page is a lightweight Flask-based web gallery intended to run on a Raspberry Pi or similar small Linux host. It serves a local `Cam_Now` directory containing still images and MP4/MOV video files, groups matching image/video files into **camera cards**, and uses a user-editable CSV file for camera descriptions and metadata.

A **camera card** is the visible gallery tile for one camera/source. Each camera card can contain:

- one still image
- one video file
- or a matched still image + video file pair

The still image and video are grouped together when they share the same filename base / group.

Example:

```text
KJ6DZB-G5.jpeg  -> group: KJ6DZB-G5
KJ6DZB-G5.mp4   -> group: KJ6DZB-G5
```

These two files display together inside **one camera card**.

The current design is meant for a simple camera-wall / mesh-camera workflow:

- Drop current image/video files into one folder.
- The app discovers them automatically.
- Matching still/video pairs are grouped into one camera card.
- The app keeps a metadata CSV in sync.
- The user edits descriptions, enable/disable status, live URLs, and notes in that CSV.
- The web page reflects the metadata without hardcoding cameras into HTML.

---

## Core Paths

Default install paths used by the current Raspberry Pi deployment:

```text
/opt/camnow_gallery/app.py
/opt/camnow_gallery/templates/index.html
/opt/camnow_gallery/descriptions.csv
/home/kj6dzb/2/MSE-87/Cam_Now
```

The app expects these environment variables:

```bash
MEDIA_ROOT=/home/kj6dzb/2/MSE-87/Cam_Now
DESCRIPTIONS_FILE=/opt/camnow_gallery/descriptions.csv
HOST=0.0.0.0
PORT=8080
```

`MEDIA_ROOT` is required. `DESCRIPTIONS_FILE` is optional and defaults to:

```text
/opt/camnow_gallery/descriptions.csv
```

---

## Supported Media Files

Images:

```text
.jpg .jpeg .png .gif .webp .bmp
```

Videos:

```text
.mp4 .m4v .mov
```

The app ignores:

- hidden files beginning with `.`
- `.tmp` files
- zero-byte files
- files with unsupported extensions
- unreadable or broken media entries

---

## Camera Cards and Media Grouping

The gallery displays media as **camera cards**.

A camera card is created from a discovered media group. The group is normally the filename without the extension.

Examples:

```text
4cam.jpeg       -> camera card/group: 4cam
4cam.mp4        -> camera card/group: 4cam

KJ6DZB-G5.jpeg  -> camera card/group: KJ6DZB-G5
KJ6DZB-G5.mp4   -> camera card/group: KJ6DZB-G5

SFWEM_meshy.png -> camera card/group: SFWEM_meshy
```

When a still image and video file share the same group, they display together inside one camera card:

```text
4cam.jpeg
4cam.mp4
```

Result:

```text
Camera Card: 4cam
  - still image
  - video
```

The template intentionally groups by the `f.group` value produced by `app.py`, not by hardcoded HTML. This keeps image/video pairing consistent and lets the backend control grouping rules if they change later.

---

## How Auto-Discovery Works

Auto-discovery happens automatically whenever the main page is loaded and when the `/discover` endpoint is requested.

The app scans the top level of `MEDIA_ROOT` and identifies valid media files. For each file, it derives a camera group from the filename without the extension.

Example:

```text
KJ6DZB-G5.jpeg     -> group: KJ6DZB-G5
KJ6DZB-G5.mp4      -> group: KJ6DZB-G5
SFWEM_meshy.png    -> group: SFWEM_meshy
KJ6DZB_4_MAP.png   -> group: KJ6DZB_4_MAP
```

If a discovered group is missing from `descriptions.csv`, the app automatically adds a new row with blank metadata:

```csv
group,description,enabled,sort_order,live_url,notes
KJ6DZB-G5,,yes,,,auto-discovered
```

The app does **not** overwrite descriptions or metadata that the user has already entered. It only appends newly discovered groups.

This means onboarding a new camera can be as simple as copying a new image or video into `Cam_Now` and refreshing the page or visiting `/discover`.

---

## Metadata CSV Format

The metadata file is:

```text
descriptions.csv
```

Current column format:

```csv
group,description,enabled,sort_order,live_url,notes
```

Column meanings:

| Column | Purpose |
|---|---|
| `group` | Required. Must match the filename base without extension. This is the camera card ID. |
| `description` | Human-readable camera card label shown above the media. |
| `enabled` | Use `yes` to show a camera card, `no` to hide it. Blank defaults to `yes`. |
| `sort_order` | Optional numeric sort hint for CSV organization. Lower numbers sort earlier in the CSV. |
| `live_url` | Optional live camera/feed URL associated with the camera card. |
| `notes` | Freeform admin notes. Not required for display. |

Example:

```csv
group,description,enabled,sort_order,live_url,notes
KJ6DZB-G5,KJ6DZB LG G5 Portable,yes,10,,portable camera
KJ6DZB_4_MAP,Xastir screen print from KJ6DZB-4,yes,20,,map snapshot
SFWEM_meshy,SFWEM mesh status graphic,yes,30,,
old-test-camera,Old test camera,no,999,,hidden from gallery
```

---

## Live URL Support

Each camera group can optionally have a `live_url` in `descriptions.csv`.

Example:

```csv
group,description,enabled,sort_order,live_url,notes
chabot-cam,Chabot Space & Science Center,yes,50,http://camera-host.local/live,live camera link
```

The Flask app loads `live_url` values and passes them to the template as `live_urls`.

The template shows a `LIVE` button/link when a live URL exists for a camera card.

Suggested Jinja usage inside a card loop:

```jinja2
{% set live_url = (live_urls.get(base, '') or '').strip() %}
{% if live_url %}
  <a class="btnlink apply-btn" href="{{ live_url }}" target="_blank" rel="noopener">LIVE</a>
{% endif %}
```

This allows live camera links to be added without editing Python or HTML. Only the CSV needs to change.

---

## Disabled-Camera Support

A camera card can be hidden without removing its image/video files.

Set `enabled` to `no`:

```csv
group,description,enabled,sort_order,live_url,notes
old-camera,Old test camera,no,999,,not currently used
```

Behavior:

- `enabled=yes` or blank: camera card is visible.
- `enabled=no`: camera card is hidden from the gallery.
- The row remains in the CSV, so it can be re-enabled later.
- Auto-discovery does not delete disabled rows.

This is useful for cameras that are temporarily offline, retired, or under test.

---

## Health Checking

The app provides a simple health endpoint:

```text
/health
```

Example:

```bash
curl http://127.0.0.1:8080/health
```

Example response:

```json
{
  "ok": true,
  "media_root": "/home/kj6dzb/2/MSE-87/Cam_Now",
  "media_root_exists": true,
  "descriptions_file": "/opt/camnow_gallery/descriptions.csv",
  "descriptions_file_exists": true
}
```

Use `/health` to quickly verify that:

- the Flask app is running
- the configured media directory exists
- the descriptions CSV exists

This is useful for systemd checks, troubleshooting, and quick status checks from another host.

---

## Discovery Endpoint

The app also provides a discovery endpoint:

```text
/discover
```

Example:

```bash
curl http://127.0.0.1:8080/discover
```

Example response:

```json
{
  "media_root": "/home/kj6dzb/2/MSE-87/Cam_Now",
  "descriptions_file": "/opt/camnow_gallery/descriptions.csv",
  "added_new_groups": ["new-camera"],
  "groups_found_in_media_folder": ["KJ6DZB-G5", "new-camera"],
  "known_groups_in_csv": ["KJ6DZB-G5", "new-camera"],
  "unreadable": []
}
```

`/discover` is useful when adding or troubleshooting cameras because it shows exactly what the app sees in the media folder and what it added to the CSV.

---

## Typical New Camera Onboarding Workflow

1. Copy the camera's current image and/or video into `Cam_Now`.

   Example:

   ```text
   /home/kj6dzb/2/MSE-87/Cam_Now/NewCam.jpeg
   /home/kj6dzb/2/MSE-87/Cam_Now/NewCam.mp4
   ```

2. Visit:

   ```text
   http://<pi-ip>:8080/discover
   ```

3. Confirm that `NewCam` appears in `added_new_groups`.

4. Edit:

   ```text
   /opt/camnow_gallery/descriptions.csv
   ```

5. Add description and optional metadata:

   ```csv
   NewCam,North ridge test camera,yes,40,http://newcam.local/live,temporary test
   ```

6. Refresh the gallery page.

The new camera card should now appear with its description, grouped still/video media, and optional live link.

---

## Running Locally

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
export MEDIA_ROOT=/home/kj6dzb/2/MSE-87/Cam_Now
export DESCRIPTIONS_FILE=/opt/camnow_gallery/descriptions.csv
python app.py
```

Then open:

```text
http://127.0.0.1:8080/
```

---

## Service Restart

If installed as a systemd service:

```bash
sudo systemctl restart camnow-gallery
sudo systemctl status camnow-gallery --no-pager
journalctl -u camnow-gallery -e --no-pager
```

Template-only changes usually require only a browser refresh. Python changes require a service restart.

---

## Current Design Notes

- A visible gallery unit is called a **camera card**.
- Camera cards are grouped by exact filename base / backend `f.group`.
- A still image and video with the same group display together in one camera card.
- New camera cards are added to CSV automatically.
- Existing descriptions are preserved.
- Disabled camera cards are hidden but not deleted.
- Live links are metadata-driven.
- `/health` and `/discover` are intended for operation and troubleshooting.
- Xastir capture tools are intentionally not included in this repo at this stage.
