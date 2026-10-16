#!/usr/bin/env python3
"""Map pinned CyberForge project metadata to upstream source URLs, without code.

Only reads project.json from archives already covered by the checksum audit.
This is a repository-identity input to, not a substitute for, license review.
"""

from datetime import datetime, timezone
import importlib.util
import io
import json
from pathlib import Path
import tarfile
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("archive_metadata", ROOT / "scripts/audit-cyberforge-archive-metadata.py")
archive_metadata = importlib.util.module_from_spec(spec)
spec.loader.exec_module(archive_metadata)


def main():
    directory = json.loads((ROOT / "docs/verification/cyberforge-all-nonoverlap-hf-archive-audit.json").read_text())
    linked = json.loads((ROOT / "docs/verification/cyberforge-all-nonoverlap-hf-metadata-audit.json").read_text())
    pinned = {row["project"]: row for row in directory["projects"]}
    project_names = sorted(row["project"] for row in linked["projects"])
    context = archive_metadata.ssl_context()
    rows = []
    for project in project_names:
        row = pinned[project]
        raw = archive_metadata.fetch_bytes(project, directory["project_dataset_revision"], row["sha256"], context)
        with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as archive:
            metadata = archive_metadata.read_json_member(archive, f"{project}/project.json")
        if metadata.get("project") != project:
            raise ValueError("Archive project name mismatch")
        repo = metadata.get("main_repo_url")
        commit = metadata.get("secure_base_commit")
        repo_valid = isinstance(repo, str) and urlparse(repo).scheme == "https" and bool(urlparse(repo).hostname)
        if not isinstance(commit, str) or len(commit) != 40 or any(c not in "0123456789abcdef" for c in commit):
            raise ValueError("Missing or invalid fixed upstream base commit")
        rows.append({"project": project, "main_repo_url": repo if repo_valid else None,
                     "repository_url_status": "PRESENT" if repo_valid else "MISSING_OR_NON_HTTPS",
                     "secure_base_commit": commit, "archive_sha256_verified": True,
                     "upstream_license_status": "NOT_CHECKED"})
    report = {
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "UPSTREAM_MAP_ONLY_NOT_LICENSE_APPROVAL",
        "project_dataset_revision": directory["project_dataset_revision"],
        "linked_record_count": linked["linked_records_checked"],
        "linked_project_count": len(rows),
        "rows": rows,
        "limits": "Repository URLs and base commits are from project.json; upstream licenses and per-row validation have not been checked.",
    }
    dest = ROOT / "docs/verification/cyberforge-linked-upstream-map.json"
    dest.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"projects": len(rows), "mapped_urls": sum(row['repository_url_status']=='PRESENT' for row in rows),
                      "missing_url_projects": [row['project'] for row in rows if row['repository_url_status']!='PRESENT'],
                      "hosts": sorted({urlparse(row['main_repo_url']).hostname for row in rows if row['main_repo_url']}),
                      "report": str(dest)}))


if __name__ == "__main__":
    main()
