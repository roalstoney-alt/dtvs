#!/usr/bin/env python3
"""DTVS-P001 single-node, resumable 20-minute restoration runner."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path, block: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(block):
            h.update(chunk)
    return h.hexdigest()


def run(cmd: list[str], *, capture: bool = False, cwd: Path | None = None) -> str:
    printable = subprocess.list2cmdline(cmd)
    print(f"[dtvs] {printable}", flush=True)
    cp = subprocess.run(cmd, cwd=cwd, text=True, check=True,
                        stdout=subprocess.PIPE if capture else None,
                        stderr=subprocess.STDOUT if capture else None)
    return cp.stdout or ""


def probe(path: Path) -> dict:
    raw = run(["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)], capture=True)
    return json.loads(raw)


def parse_hms(value: str) -> float:
    h, m, s = value.split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


def format_hms(seconds: float) -> str:
    ms = int(round((seconds - int(seconds)) * 1000))
    whole = int(seconds)
    return f"{whole//3600:02d}:{(whole%3600)//60:02d}:{whole%60:02d}.{ms:03d}"


def load_config(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    required = ["spec_version", "pilot_id", "source_path", "subtitle_path", "segment_start",
                "segment_duration_seconds", "chunk_seconds", "target_width", "target_height",
                "realesrgan_executable", "realesrgan_model"]
    missing = [k for k in required if k not in data]
    if missing:
        raise ValueError(f"Missing config fields: {missing}")
    if data["segment_duration_seconds"] != 1200:
        raise ValueError("DTVS-P001 requires exactly 1200 seconds")
    if data["segment_duration_seconds"] % data["chunk_seconds"]:
        raise ValueError("duration must divide evenly by chunk_seconds")
    return data


def version(command: list[str]) -> str:
    try:
        return run(command, capture=True).splitlines()[0]
    except Exception as exc:
        return f"ERROR: {exc}"


def preflight(config_path: Path) -> dict:
    cfg = load_config(config_path)
    source = ROOT / cfg["source_path"]
    subtitle = ROOT / cfg["subtitle_path"]
    realesrgan = ROOT / cfg["realesrgan_executable"]
    for command in ("ffmpeg", "ffprobe", "nvidia-smi"):
        if not shutil.which(command):
            raise RuntimeError(f"Missing command: {command}")
    for path in (source, subtitle, realesrgan):
        if not path.exists():
            raise FileNotFoundError(path)
    free_gb = shutil.disk_usage(ROOT).free / (1024**3)
    if free_gb < cfg["minimum_free_disk_gb"]:
        raise RuntimeError(f"Free disk {free_gb:.1f}GB < required {cfg['minimum_free_disk_gb']}GB")
    p = probe(source)
    duration = float(p["format"]["duration"])
    if parse_hms(cfg["segment_start"]) + cfg["segment_duration_seconds"] > duration:
        raise RuntimeError("Frozen segment exceeds source duration")
    out = {
        "checked_at": utc_now(), "free_disk_gb": round(free_gb, 2),
        "source_sha256": sha256(source), "subtitle_sha256": sha256(subtitle),
        "source_probe": p,
        "versions": {
            "python": sys.version.splitlines()[0], "platform": platform.platform(),
            "ffmpeg": version(["ffmpeg", "-version"]),
            "nvidia_smi": version(["nvidia-smi"]),
            "realesrgan": version([str(realesrgan), "-h"]),
        }
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return out


class EnergyLogger:
    def __init__(self, path: Path, interval: int):
        self.path, self.interval = path, interval
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self._loop, daemon=True)

    def start(self):
        self.thread.start()

    def stop(self):
        self.stop_event.set(); self.thread.join(timeout=self.interval + 5)

    def _loop(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        new = not self.path.exists()
        with self.path.open("a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            if new: w.writerow(["timestamp_utc", "gpu_index", "power_w", "utilization_pct", "memory_used_mb", "temperature_c"])
            while not self.stop_event.is_set():
                try:
                    raw = run(["nvidia-smi", "--query-gpu=index,power.draw,utilization.gpu,memory.used,temperature.gpu",
                               "--format=csv,noheader,nounits"], capture=True)
                    for line in raw.strip().splitlines():
                        w.writerow([utc_now()] + [x.strip() for x in line.split(",")])
                    f.flush()
                except Exception as exc:
                    w.writerow([utc_now(), "ERROR", str(exc)]); f.flush()
                self.stop_event.wait(self.interval)


def event(path: Path, kind: str, **fields):
    record = {"timestamp_utc": utc_now(), "event": kind, **fields}
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def get_video_info(p: dict) -> tuple[str, str]:
    v = next(s for s in p["streams"] if s["codec_type"] == "video")
    rate = v.get("avg_frame_rate") or v.get("r_frame_rate")
    return rate, v.get("pix_fmt", "unknown")


def run_pilot(config_path: Path, run_id: str | None):
    cfg = load_config(config_path)
    pf = preflight(config_path)
    config_hash = sha256(config_path)
    run_id = run_id or f"{cfg['pilot_id']}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:6]}"
    out = ROOT / "runs" / run_id
    out.mkdir(parents=True, exist_ok=True)
    events = out / "events.jsonl"
    (out / "source_probe.json").write_text(json.dumps(pf["source_probe"], indent=2), encoding="utf-8")
    (out / "software_versions.json").write_text(json.dumps(pf["versions"], indent=2), encoding="utf-8")
    manifest = {
        "run_id": run_id, "pilot_id": cfg["pilot_id"], "spec_version": cfg["spec_version"],
        "state": "RUNNING", "started_at": utc_now(), "config_sha256": config_hash,
        "source_sha256": pf["source_sha256"], "subtitle_sha256": pf["subtitle_sha256"],
        "claim_boundary": "single-node reproducibility only"
    }
    manifest_path = out / "run_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    source = ROOT / cfg["source_path"]
    subtitle = ROOT / cfg["subtitle_path"]
    exe = ROOT / cfg["realesrgan_executable"]
    fps, _ = get_video_info(pf["source_probe"])
    total_chunks = cfg["segment_duration_seconds"] // cfg["chunk_seconds"]
    energy = EnergyLogger(out / "energy.csv", cfg["energy_sample_seconds"])
    energy.start(); event(events, "RUN_STARTED", run_id=run_id, chunks=total_chunks)
    try:
        chunk_outputs = []
        for idx in range(total_chunks):
            chunk = out / "chunks" / f"{idx:03d}"
            chunk.mkdir(parents=True, exist_ok=True)
            checkpoint = chunk / "checkpoint.json"
            encoded = chunk / "chunk.mkv"
            if checkpoint.exists():
                cp = json.loads(checkpoint.read_text(encoding="utf-8"))
                if cp.get("state") == "CHUNK_ACCEPTED" and encoded.exists() and cp.get("sha256") == sha256(encoded):
                    event(events, "CHUNK_SKIPPED", chunk=idx, reason="valid checkpoint")
                    chunk_outputs.append(encoded); continue
            frames_in, frames_out = chunk / "frames_in", chunk / "frames_out"
            frames_in.mkdir(exist_ok=True); frames_out.mkdir(exist_ok=True)
            start = parse_hms(cfg["segment_start"]) + idx * cfg["chunk_seconds"]
            event(events, "CHUNK_EXTRACT_START", chunk=idx)
            vf = cfg["preprocess_filter"]
            run(["ffmpeg", "-hide_banner", "-y", "-ss", format_hms(start), "-t", str(cfg["chunk_seconds"]),
                 "-i", str(source), "-an", "-vf", vf, "-vsync", "0", str(frames_in / "%08d.png")])
            event(events, "CHUNK_UPSCALE_START", chunk=idx)
            run([str(exe), "-i", str(frames_in), "-o", str(frames_out), "-n", cfg["realesrgan_model"],
                 "-s", str(cfg["realesrgan_scale"]), "-t", str(cfg["realesrgan_tile"]), "-f", "png"])
            target = f"scale={cfg['target_width']}:{cfg['target_height']}:force_original_aspect_ratio=decrease:flags=lanczos,pad={cfg['target_width']}:{cfg['target_height']}:(ow-iw)/2:(oh-ih)/2:black"
            run(["ffmpeg", "-hide_banner", "-y", "-framerate", fps, "-i", str(frames_out / "%08d.png"),
                 "-vf", target, "-c:v", cfg["video_codec"], "-crf", str(cfg["video_crf"]),
                 "-preset", cfg["video_preset"], "-pix_fmt", cfg["pixel_format"], str(encoded)])
            ep = probe(encoded); duration = float(ep["format"]["duration"])
            if abs(duration - cfg["chunk_seconds"]) > 1.0:
                raise RuntimeError(f"Chunk {idx} duration {duration} outside tolerance")
            digest = sha256(encoded)
            checkpoint.write_text(json.dumps({"chunk": idx, "state": "CHUNK_ACCEPTED", "sha256": digest,
                                              "duration": duration, "accepted_at": utc_now()}, indent=2), encoding="utf-8")
            event(events, "CHUNK_ACCEPTED", chunk=idx, sha256=digest)
            chunk_outputs.append(encoded)
            shutil.rmtree(frames_in); shutil.rmtree(frames_out)

        concat = out / "concat.txt"
        concat.write_text("".join(f"file '{p.resolve().as_posix()}'\n" for p in chunk_outputs), encoding="utf-8")
        video_only = out / "video_4k.mkv"
        run(["ffmpeg", "-hide_banner", "-y", "-f", "concat", "-safe", "0", "-i", str(concat), "-c", "copy", str(video_only)])
        audio = out / "segment_audio.mka"
        try:
            run(["ffmpeg", "-hide_banner", "-y", "-ss", cfg["segment_start"], "-t", str(cfg["segment_duration_seconds"]),
                 "-i", str(source), "-vn", "-c:a", "flac", str(audio)])
        except subprocess.CalledProcessError:
            audio = None; event(events, "AUDIO_ABSENT")
        master = out / "master_4k_zh.mkv"
        cmd = ["ffmpeg", "-hide_banner", "-y", "-i", str(video_only)]
        if audio: cmd += ["-i", str(audio)]
        cmd += ["-i", str(subtitle), "-map", "0:v:0"]
        if audio: cmd += ["-map", "1:a:0", "-map", "2:0"]
        else: cmd += ["-map", "1:0"]
        cmd += ["-c:v", "copy", "-c:a", "copy", "-c:s", "srt", "-metadata:s:s:0", "language=zho", str(master)]
        run(cmd)
        review = out / "review_4k_zh_burned.mp4"
        escaped = str(subtitle.resolve()).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
        run(["ffmpeg", "-hide_banner", "-y", "-i", str(master), "-vf",
             f"subtitles='{escaped}':charenc=UTF-8:force_style='FontName=Microsoft YaHei,FontSize=22,Outline=2,Shadow=0,MarginV=42'",
             "-c:v", "libx265", "-crf", "18", "-preset", "medium", "-c:a", "aac", "-b:a", "192k", str(review)])
        hashes = {p.name: sha256(p) for p in (master, review, video_only) if p.exists()}
        (out / "artifact_hashes.json").write_text(json.dumps(hashes, indent=2), encoding="utf-8")
        qc = {"state": "MANUAL_REVIEW_REQUIRED", "master_probe": probe(master), "hashes": hashes,
              "required_manual_samples": cfg["gates"]["manual_sample_count"]}
        (out / "qc_report.json").write_text(json.dumps(qc, indent=2), encoding="utf-8")
        manual = out / "manual_review.csv"
        with manual.open("w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f); w.writerow(["timestamp_seconds", "faces", "edges", "flicker", "motion", "intertitle", "subtitle_timing", "hallucination", "pass", "notes"])
            for t in range(0, cfg["segment_duration_seconds"], cfg["sample_interval_seconds"]): w.writerow([t, "", "", "", "", "", "", "", "", ""])
        manifest.update({"state": "RUNNING", "pipeline_completed_at": utc_now(), "next_gate": "manual review", "artifacts": hashes})
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        event(events, "PIPELINE_COMPLETE", next_gate="manual review")
        print(f"Pipeline complete. Review evidence at {out}")
    except Exception as exc:
        manifest.update({"state": "FAILED", "failed_at": utc_now(), "error": repr(exc)})
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        event(events, "RUN_FAILED", error=repr(exc)); raise
    finally:
        energy.stop()


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="command", required=True)
    for name in ("preflight", "run"):
        p = sub.add_parser(name); p.add_argument("--config", required=True); p.add_argument("--run-id")
    args = ap.parse_args()
    config = (ROOT / args.config).resolve()
    if args.command == "preflight": preflight(config)
    else: run_pilot(config, args.run_id)


if __name__ == "__main__":
    main()

