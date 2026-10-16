#!/usr/bin/env python3
"""Read GitHub-detected root license metadata at pinned source commits.

No source code or license text is saved. A detected root license is only a
first-pass signal: nested licenses, generated artifacts, and dataset terms
still need review before any record can be used for training.
"""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
GH = ROOT / ".tools/github-cli/gh"
GH_CONFIG = ROOT / ".secrets/github-cli-auth"


def main():
    source = json.loads((ROOT / "docs/verification/cyberforge-linked-upstream-map.json").read_text())
    if source["status"] != "UPSTREAM_MAP_ONLY_NOT_LICENSE_APPROVAL":
        raise ValueError("Unexpected source map")
    env = os.environ.copy()
    env["GH_CONFIG_DIR"] = str(GH_CONFIG)
    results = []
    for row in source["rows"]:
        url = row["main_repo_url"]
        result = {"project": row["project"], "source_url": url,
                  "secure_base_commit": row["secure_base_commit"]}
        if not url:
            result["status"] = "UPSTREAM_URL_NOT_MAPPED"
            results.append(result)
            continue
        parsed = urlparse(url)
        parts = parsed.path.strip("/").removesuffix(".git").split("/")
        if parsed.scheme != "https" or parsed.hostname != "github.com" or len(parts) != 2 or not all(re.fullmatch(r"[A-Za-z0-9_.-]+", x) for x in parts):
            result["status"] = "UNSUPPORTED_SOURCE_URL"
            results.append(result)
            continue
        owner, repo = parts
        endpoint = f"repos/{owner}/{repo}/license?ref={row['secure_base_commit']}"
        proc = subprocess.run([str(GH), "api", endpoint], env=env,
                              capture_output=True, text=True, timeout=25)
        if proc.returncode != 0:
            result["status"] = "NOT_RESOLVED_AT_BASE_REF" if "404" in proc.stderr else "API_ERROR"
            # Error bodies may contain unrelated details. Do not save them.
            results.append(result)
            continue
        try:
            payload = json.loads(proc.stdout)
        except ValueError:
            result["status"] = "INVALID_API_RESPONSE"
            results.append(result)
            continue
        license_meta = payload.get("license") if isinstance(payload, dict) else None
        path = payload.get("path") if isinstance(payload, dict) else None
        spdx = license_meta.get("spdx_id") if isinstance(license_meta, dict) else None
        if not isinstance(path, str) or not isinstance(spdx, str):
            result["status"] = "LICENSE_FILE_WITHOUT_RECOGNIZED_SPDX"
        else:
            result["status"] = ("ROOT_LICENSE_UNCLASSIFIED" if spdx == "NOASSERTION"
                                else "ROOT_LICENSE_SPDX_DETECTED")
            result["spdx_id"] = spdx
            result["license_path"] = path
            result["license_url_at_base"] = f"https://github.com/{owner}/{repo}/blob/{row['secure_base_commit']}/{path}"
        results.append(result)
    counts = {status: sum(row["status"] == status for row in results)
              for status in sorted({row["status"] for row in results})}
    report = {
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "ROOT_LICENSE_METADATA_ONLY_NOT_TRAINING_APPROVAL",
        "project_dataset_revision": source["project_dataset_revision"],
        "linked_record_count": source["linked_record_count"],
        "project_count": len(results), "status_counts": counts,
        "rows": results,
        "limits": [
            "GitHub root-license detection at the pinned base commit does not review nested file licenses, copied source, CyberForge trajectory/data terms, or per-record validation.",
            "A 404 could mean an unavailable commit or no detectable license; it is not interpreted as a no-license conclusion.",
            "No record is approved for training by this audit."
        ],
    }
    dest = ROOT / "docs/verification/cyberforge-linked-upstream-license-audit.json"
    dest.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"project_count": len(results), "status_counts": counts,
                      "report": str(dest)}))


if __name__ == "__main__":
    main()
