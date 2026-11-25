"""Materialize and validate the production's original text and image bytes."""

import hashlib
import json
import os
import re
import subprocess
import tempfile
import unicodedata
import zipfile
from functools import lru_cache
from pathlib import Path

from creative_studio_plan import ID, PlanError

FORMATS = ("md", "mdx", "zip")
NAME = re.compile(r"(?:manuscript\.(?:mdx?|zip)|manifest\.json|images/(?:cover|chapter-[0-9]{2,3})\.png)")
HASH = re.compile(r"[a-f0-9]{64}")


def sha(data):
    return hashlib.sha256(data).hexdigest()


@lru_cache(maxsize=128)
def _fingerprint(path, _size, _modified, _changed):
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


class Exports:
    def __init__(self, root, validator):
        self.root = root
        self.validator = validator

    def file(self, job_id, receipt, name):
        generation = receipt.get("generation", "")
        if not ID.fullmatch(job_id) or not HASH.fullmatch(generation) or not NAME.fullmatch(name):
            raise PlanError("production_export_invalid")
        path = self.root / job_id / generation / name
        fingerprint = receipt.get("files", {}).get(name, {})
        try:
            stat = path.stat()
            if (stat.st_size == fingerprint.get("bytes") and stat.st_size > 0
                    and _fingerprint(path, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns) == fingerprint.get("sha256")):
                return path
        except OSError:
            pass
        raise PlanError("production_export_missing")

    def valid(self, job_id, receipt):
        names = set(receipt.get("files", {}))
        if not {"manuscript.md", "manuscript.mdx", "manuscript.zip", "manifest.json", "images/cover.png"} <= names:
            return False
        try:
            for name in names:
                self.file(job_id, receipt, name)
        except PlanError:
            return False
        return True

    def build(self, job_id, document, manifest, render, image_bytes):
        assets = [document["cover"], *(c["image"] for c in document["chapters"])]
        names = ["images/cover.png", *(f"images/chapter-{c['number']:02}.png" for c in document["chapters"])]
        if len({asset["id"] for asset in assets}) != len(assets):
            raise PlanError("production_export_invalid")
        image_paths = {asset["id"]: path for asset, path in zip(assets, names, strict=True)}
        checks = ["chapters", "relative_images", "png", "mdx_compile", "zip", "file_integrity"]
        slug = unicodedata.normalize("NFKD", document["title"]).encode("ascii", "ignore").decode().lower()
        slug = re.sub(r"[^a-z0-9]+", "-", slug).strip("-")[:60] or "manuscript"
        root = self.root / job_id
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root) as directory:
            staging = Path(directory)
            files = {}

            def write(name, data):
                path = staging / name
                path.parent.mkdir(mode=0o700, exist_ok=True)
                with path.open("wb") as handle:
                    handle.write(data)
                    handle.flush()
                    os.fsync(handle.fileno())
                files[name] = {"bytes": len(data), "sha256": sha(data)}

            metadata = []
            for asset, path in zip(assets, names, strict=True):
                write(path, image_bytes(asset["id"], asset["request"]["size"]))
                metadata.append({"path": path, "id": asset["id"], "alt": asset["alt"], "model": asset["request"].get("model"),
                                 "size": asset["request"]["size"], "visual_profile": asset.get("visual_profile"),
                                 "seed": asset["request"].get("seed"), "sha256": files[path]["sha256"]})
            for fmt in ("md", "mdx"):
                write(f"manuscript.{fmt}", render(document, fmt, image_paths=image_paths).encode("utf-8"))
            public = {**manifest, "status": "completed", "checkpoint": {"phase": "done"},
                      "exports": [f"manuscript.{ext}" for ext in FORMATS], "images": metadata, "checks": checks}
            write("manifest.json", json.dumps(public, ensure_ascii=False, indent=2).encode("utf-8"))
            # The input digest keeps retried writes under the same generation path.
            generation = sha(json.dumps(files, sort_keys=True).encode())
            bundle = staging / "manuscript.zip"
            with zipfile.ZipFile(bundle, "w", zipfile.ZIP_DEFLATED) as archive:
                for name in files:
                    archive.write(staging / name, name)
                # Preserve the metadata entry consumed by existing clients.
                archive.writestr("images/metadata.json", json.dumps(metadata, ensure_ascii=False))
            with bundle.open("rb+") as handle:
                files[bundle.name] = {"bytes": bundle.stat().st_size, "sha256": hashlib.file_digest(handle, "sha256").hexdigest()}
                os.fsync(handle.fileno())
            target = root / generation
            target.mkdir(mode=0o700, exist_ok=True)
            for name in files:
                destination = target / name
                destination.parent.mkdir(mode=0o700, exist_ok=True)
                os.replace(staging / name, destination)
        return {"generation": generation, "slug": slug, "files": files, "checks": checks}

    def validate(self, job_id, receipt, document, escape):
        if not self.valid(job_id, receipt):
            raise PlanError("production_export_missing")
        for fmt in ("md", "mdx"):
            path = self.file(job_id, receipt, f"manuscript.{fmt}")
            text = path.read_text(encoding="utf-8")
            prefix = "Kapitel" if document["language"] == "de" else "Chapter"
            previous = -1
            for chapter in document["chapters"]:
                number = chapter["number"]
                heading = f"\n\n## {prefix} {number}\n\n### {escape(chapter['title'], fmt)}\n\n"
                end = text.find(heading, max(0, previous))
                if end < 0:
                    raise PlanError("production_export_invalid")
                image, marker, rest = text[end + len(heading):].partition("\n\n")
                expected = escape(chapter["body"], fmt)
                if (not marker or not image.endswith(f"](images/chapter-{number:02}.png)")
                        or not (rest == expected + "\n" or rest.startswith(expected + "\n\n"))):
                    raise PlanError("production_export_invalid")
                previous = end + len(heading) + len(image) + len(marker) + len(expected)
            if "](images/cover.png)" not in text:
                raise PlanError("production_export_invalid")
        try:
            checked = subprocess.run(["node", str(self.validator())], input=path.read_bytes(),
                                     capture_output=True, timeout=30, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise PlanError("production_mdx_tool_unavailable") from exc
        if checked.returncode:
            if b"MODULE_NOT_FOUND" in checked.stderr or b"ERR_MODULE_NOT_FOUND" in checked.stderr:
                raise PlanError("production_mdx_tool_unavailable")
            raise PlanError("production_mdx_invalid")
        with zipfile.ZipFile(self.file(job_id, receipt, "manuscript.zip")) as archive:
            expected = set(receipt["files"]) - {"manuscript.zip"}
            if set(archive.namelist()) != expected | {"images/metadata.json"} or archive.testzip():
                raise PlanError("production_export_invalid")
            for name in expected:
                if sha(archive.read(name)) != receipt["files"][name]["sha256"]:
                    raise PlanError("production_export_invalid")
