"""Upload existing local capture images to Supabase Storage.

This is a backfill utility. The normal capture service uploads new
images automatically, but this script can upload files that were
created while Supabase was unreachable.
"""

import os

from config import BASE_DIR, SUPABASE_BUCKET, get_supabase

LOCAL_FOLDER = BASE_DIR / "thermal_captures"

supabase = get_supabase()

if not os.path.isdir(LOCAL_FOLDER):
    raise SystemExit(f"Local folder does not exist: {LOCAL_FOLDER}")

uploaded = 0
failed = 0

for filename in sorted(os.listdir(LOCAL_FOLDER)):
    if not filename.lower().endswith((".jpg", ".jpeg", ".png")):
        continue

    local_path = os.path.join(LOCAL_FOLDER, filename)
    storage_path = f"thermal/{filename}"

    content_type = (
        "image/png" if filename.lower().endswith(".png") else "image/jpeg"
    )

    print(f"Uploading {filename}...")

    try:
        with open(local_path, "rb") as f:
            file_data = f.read()

        supabase.storage.from_(SUPABASE_BUCKET).upload(
            storage_path,
            file_data,
            {"content-type": content_type},
        )

        print(f"Uploaded: {filename}")
        uploaded += 1

    except Exception as exc:
        print(f"Failed: {filename}")
        print(exc)
        failed += 1

print(f"Finished. Uploaded={uploaded}, Failed={failed}")
