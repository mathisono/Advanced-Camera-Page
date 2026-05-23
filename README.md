# Advanced Camera Page

Advanced Camera Page is a lightweight Flask-based web gallery intended to run on a Raspberry Pi or similar small Linux host. It serves a local `Cam_Now` directory containing still images and MP4/MOV video files, groups matching image/video files into camera cards, and uses a user-editable CSV file for camera descriptions and metadata.

The current design is meant for a simple camera-wall / mesh-camera workflow:

- Drop current image/video files into one folder.
- The app discovers them automatically.
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
| `group` | Required. Must match the filename base without extension. |
| `description` | Human-readable card label shown above the media. |
| `enabled` | Use `yes` to show a camera, `no` to hide it. Blank defaults to `yes`. |
| `sort_order` | Optional numeric sort hint for CSV organization. Lower numbers sort earlier in the CSV. |
| `live_url` | Optional live camera/feed URL associated with the card. |
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

The template can then show a `LIVE` button or link when a live URL exists for a card.

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

A camera can be hidden without removing its image/video files.

Set `enabled` to `no`:

```csv
group,description,enabled,sort_order,live_url,notes
old-camera,Old test camera,no,999,,not currently used
```

Behavior:

- `enabled=yes` or blank: camera is visible.
- `enabled=no`: camera is hidden from the gallery.
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

The new card should now appear with its description and optional live link.

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

- Camera grouping is based on exact filename base.
- New cameras are added to CSV automatically.
- Existing descriptions are preserved.
- Disabled cameras are hidden but not deleted.
- Live links are metadata-driven.
- `/health` and `/discover` are intended for operation and troubleshooting.
- Xastir capture tools are intentionally not included in this repo at this stage.
