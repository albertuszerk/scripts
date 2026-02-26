import os
import json
import subprocess
import shutil
import argparse
from datetime import datetime, timedelta

# --- RELATIVE PFADERMITTLUNG ---
# Ermittelt den Ort des Skripts (fotopool-bin) und das Stammverzeichnis
BIN_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(BIN_DIR)

# Definition der Arbeitsverzeichnisse relativ zum Stammverzeichnis
SOURCE_DIR = os.path.join(BASE_DIR, "fotopool-alt")
TARGET_DIR_OK = os.path.join(BASE_DIR, "fotopool-neu")
TARGET_DIR_NO_DATE = os.path.join(BASE_DIR, "fotopool-ohne-datum")
DB_FILE = os.path.join(BIN_DIR, "photo_db.json")

# Apple-Dateitypen Profil
IMAGE_EXT = {'.jpg', '.jpeg', '.png', '.heic', '.heif', '.tiff', '.tif', '.dng', '.gif'}
VIDEO_EXT = {'.mov', '.mp4', '.m4v', '.qt', '.3gp'}

def get_exif_date(file_path):
    """Liest Metadaten via ExifTool aus und fixiert das Jahr auf 4 Stellen."""
    try:
        cmd = [
            "exiftool", "-s3", 
            "-d", "%Y:%m:%d %H:%M:%S", # Verhindert den Millennium Bug (erzwingt YYYY)
            "-CreateDate", "-DateTimeOriginal", "-CreationDate", 
            file_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        dates = [d for d in result.stdout.strip().split('\n') if d]
        if dates:
            return datetime.strptime(dates[0], "%Y:%m:%d %H:%M:%S")
    except Exception:
        pass
    return None

def write_exif_date(file_path, date_obj):
    """Schreibt das Anker-Datum (1971) und synchronisiert die Systemzeit (mtime)."""
    date_str = date_obj.strftime("%Y:%m:%d %H:%M:%S")
    ext = os.path.splitext(file_path)[1].lower()
    
    if ext in VIDEO_EXT:
        cmd = [
            "exiftool", "-overwrite_original",
            f"-QuickTime:CreateDate={date_str}",
            f"-QuickTime:ModifyDate={date_str}",
            f"-Keys:CreationDate={date_str}",
            file_path
        ]
    else:
        cmd = [
            "exiftool", "-overwrite_original",
            f"-AllDates={date_str}",
            f"-CreationDate={date_str}",
            file_path
        ]
    subprocess.run(cmd, capture_output=True)
    
    # mtime-Sync fuer korrekte Anzeige in XnView MP
    ts = date_obj.timestamp()
    os.utime(file_path, (ts, ts))

def scan():
    print(f"--- ANALYSE: Scanne {SOURCE_DIR} ---")
    db = []
    if not os.path.exists(SOURCE_DIR):
        print(f"Fehler: Quellordner {SOURCE_DIR} nicht gefunden!")
        return

    for root, _, files in os.walk(SOURCE_DIR):
        for file in files:
            ext = os.path.splitext(file)[1].lower()
            if ext in IMAGE_EXT or ext in VIDEO_EXT:
                path = os.path.join(root, file)
                date = get_exif_date(path)
                file_type = "PIC" if ext in IMAGE_EXT else "VID"
                db.append({
                    "orig_path": path,
                    "full_timestamp": date.isoformat() if date else None,
                    "day_string": date.strftime("%Y%m%d") if date else None,
                    "type": file_type,
                    "extension": ext
                })
    
    with open(DB_FILE, "w") as f:
        json.dump(db, f, indent=4)
    print(f"Erfolg: {len(db)} Dateien in {DB_FILE} erfasst.")

def export(custom_name=None):
    if not os.path.exists(DB_FILE):
        print("Fehler: Keine Datenbank gefunden. Bitte zuerst --scan ausfuhren.")
        return
    with open(DB_FILE, "r") as f:
        db = json.load(f)
    
    with_date = [e for e in db if e["full_timestamp"]]
    no_date = [e for e in db if not e["full_timestamp"]]
    with_date.sort(key=lambda x: x["full_timestamp"])
    
    final_list = no_date + with_date
    os.makedirs(TARGET_DIR_OK, exist_ok=True)
    os.makedirs(TARGET_DIR_NO_DATE, exist_ok=True)

    anchor_start = datetime(1971, 9, 9, 0, 0, 0)

    print(f"--- EXPORT: {len(final_list)} Dateien werden verarbeitet ---")
    for i, entry in enumerate(final_list, start=1):
        display_type = custom_name if custom_name else entry["type"]
        
        if not entry["full_timestamp"]:
            synthetic_date = anchor_start + timedelta(seconds=i)
            new_name = f"19710909-{display_type}-{i:05d}{entry['extension']}"
            dest_path = os.path.join(TARGET_DIR_NO_DATE, new_name)
            shutil.copy2(entry['orig_path'], dest_path)
            write_exif_date(dest_path, synthetic_date)
        else:
            new_name = f"{entry['day_string']}-{display_type}-{i:05d}{entry['extension']}"
            dest_path = os.path.join(TARGET_DIR_OK, new_name)
            shutil.copy2(entry['orig_path'], dest_path)

    print(f"\nExport fertig. Label: {custom_name if custom_name else 'Standard (PIC/VID)'}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="iPhone Photo Manager")
    parser.add_argument("--scan", action="store_true")
    parser.add_argument("--export", action="store_true")
    parser.add_argument("--nameit", type=str)
    
    args = parser.parse_args()
    if args.scan: scan()
    elif args.export: export(custom_name=args.nameit)
