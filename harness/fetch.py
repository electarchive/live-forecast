import gzip
import hashlib
import json
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def get(url: str) -> bytes | None:
    for attempt in range(4):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "live-forecast replication"})
            with urllib.request.urlopen(request, timeout=120) as response:
                body = response.read()
            return gzip.decompress(body) if body[:2] == b"\x1f\x8b" else body
        except Exception as error:
            print("retry", url, error, file=sys.stderr, flush=True)
            time.sleep(120 * 2**attempt)
    return None


if __name__ == "__main__":
    manifest = json.loads((ROOT / "frames/manifest.json").read_text())
    bad = 0
    for year, races in manifest.items():
        for key, entry in races.items():
            folder = ROOT / "frames/raw" / year / key
            folder.mkdir(parents=True, exist_ok=True)
            for stamp, digest in entry["captures"]:
                target = folder / f"{stamp}.json"
                if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest() == digest:
                    continue
                body = get(f"https://web.archive.org/web/{stamp}id_/{entry['url']}")
                if body is None or hashlib.sha256(body).hexdigest() != digest:
                    print("checksum mismatch", year, key, stamp, file=sys.stderr)
                    bad += 1
                    continue
                target.write_bytes(body)
                time.sleep(4.5)
            print(year, key, len(entry["captures"]), "captures", flush=True)
    sys.exit(1 if bad else 0)
