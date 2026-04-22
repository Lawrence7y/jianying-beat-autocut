from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence

import numpy as np


def ensure_jianying_scripts_on_path(current_file: str) -> tuple[str, str]:
    current_dir = os.path.dirname(os.path.abspath(current_file))
    workspace_root = os.path.abspath(os.path.join(current_dir, ".."))
    env_root = os.getenv("JY_SKILL_ROOT", "").strip()

    candidates = [
        env_root,
        os.path.join(workspace_root, "skills", "jianying"),
        os.path.join(workspace_root, "skills", "jianying-editor"),
        os.path.join(current_dir, "skills", "jianying"),
        os.path.join(current_dir, "skills", "jianying-editor"),
        os.path.abspath(".agent/skills/jianying-editor"),
        os.path.abspath(".trae/skills/jianying-editor"),
        os.path.abspath(".claude/skills/jianying-editor"),
    ]

    attempted: list[str] = []
    for candidate in candidates:
        if not candidate:
            continue
        root = os.path.abspath(candidate)
        attempted.append(root)
        wrapper = os.path.join(root, "scripts", "jy_wrapper.py")
        if os.path.exists(wrapper):
            scripts_path = os.path.join(root, "scripts")
            if scripts_path not in sys.path:
                sys.path.insert(0, scripts_path)
            return root, scripts_path

    raise ImportError(
        "Could not find jianying skill scripts/jy_wrapper.py. Tried:\n- "
        + "\n- ".join(attempted)
    )


SKILL_ROOT, _SCRIPTS_PATH = ensure_jianying_scripts_on_path(__file__)

import librosa  # noqa: E402
import pyJianYingDraft as draft  # noqa: E402
import pyJianYingDraft.assets as draft_assets  # noqa: E402
from pyJianYingDraft import trange  # noqa: E402

from jy_wrapper import JyProject  # noqa: E402
from utils.formatters import get_default_drafts_root, get_duration_ffprobe_cached  # noqa: E402


VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".m4v", ".webm"}
AUDIO_EXTENSIONS = {".mp3", ".wav", ".aac", ".flac", ".m4a", ".ogg"}

DEFAULT_SHOT_DETAIL_LEVEL = "medium"
SHOT_DETAIL_PRESETS: dict[str, dict[str, float]] = {
    "coarse": {
        "shot_scene_threshold": 0.40,
        "shot_min_sec": 0.45,
        "shot_analysis_fps": 6.0,
        "shot_max_sec": 0.0,
    },
    "medium": {
        "shot_scene_threshold": 0.34,
        "shot_min_sec": 0.28,
        "shot_analysis_fps": 8.0,
        "shot_max_sec": 0.0,
    },
    "fine": {
        "shot_scene_threshold": 0.27,
        "shot_min_sec": 0.18,
        "shot_analysis_fps": 12.0,
        "shot_max_sec": 0.0,
    },
}
SHOT_DETAIL_LEVEL_ALIASES = {
    "粗剪": "coarse",
    "中度": "medium",
    "精细": "fine",
    "自定义": "custom",
    "coarse": "coarse",
    "medium": "medium",
    "fine": "fine",
    "custom": "custom",
    "": DEFAULT_SHOT_DETAIL_LEVEL,
}


@dataclass
class SliceCursor:
    path: Path
    duration_us: int
    cursor_us: int = 0


def normalize_shot_detail_level(detail_level: str | None) -> str:
    key = "" if detail_level is None else str(detail_level).strip()
    if key in SHOT_DETAIL_LEVEL_ALIASES:
        return SHOT_DETAIL_LEVEL_ALIASES[key]

    lowered = key.lower()
    if lowered in SHOT_DETAIL_LEVEL_ALIASES:
        return SHOT_DETAIL_LEVEL_ALIASES[lowered]

    allowed = ", ".join(["coarse", "medium", "fine", "custom", "粗剪", "中度", "精细", "自定义"])
    raise ValueError(f"Unsupported shot_detail_level: {detail_level}. Allowed: {allowed}")


def resolve_shot_detail_settings(
    detail_level: str | None,
    *,
    shot_scene_threshold: float | None = None,
    shot_min_sec: float | None = None,
    shot_analysis_fps: float | None = None,
    shot_max_sec: float | None = None,
) -> dict[str, float]:
    normalized = normalize_shot_detail_level(detail_level)
    if normalized != "custom":
        return dict(SHOT_DETAIL_PRESETS[normalized])

    if None in {shot_scene_threshold, shot_min_sec, shot_analysis_fps, shot_max_sec}:
        raise ValueError("Custom shot detail mode requires explicit shot parameters.")

    return {
        "shot_scene_threshold": float(shot_scene_threshold),
        "shot_min_sec": float(shot_min_sec),
        "shot_analysis_fps": float(shot_analysis_fps),
        "shot_max_sec": float(shot_max_sec),
    }


def match_shot_detail_level_for_settings(settings: dict[str, float], tolerance: float = 1e-9) -> str:
    for level, preset in SHOT_DETAIL_PRESETS.items():
        if all(abs(float(settings[key]) - float(preset[key])) <= tolerance for key in preset):
            return level
    return "custom"


def ensure_assets_files(
    *,
    assets_dir: Path,
    required_filenames: Sequence[str],
    fallback_dirs: Sequence[Path],
) -> list[Path]:
    assets_dir.mkdir(parents=True, exist_ok=True)
    copied: list[Path] = []
    for name in required_filenames:
        target = assets_dir / name
        if target.exists():
            continue
        for fallback_dir in fallback_dirs:
            src = fallback_dir / name
            if src.exists() and src.is_file():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, target)
                copied.append(target)
                break
    return copied


def ensure_pyjianying_asset_templates() -> dict:
    assets_dir = Path(draft_assets.__file__).resolve().parent
    required = [
        draft_assets.ASSET_FILES["DRAFT_CONTENT_TEMPLATE"],
        draft_assets.ASSET_FILES["DRAFT_META_TEMPLATE"],
    ]
    fallback_dirs = [
        Path(SKILL_ROOT) / "scripts" / "vendor" / "pyJianYingDraft" / "assets",
        Path(sys.prefix) / "Lib" / "site-packages" / "pyJianYingDraft" / "assets",
        Path.home()
        / "AppData"
        / "Roaming"
        / "Python"
        / f"Python{sys.version_info.major}{sys.version_info.minor}"
        / "site-packages"
        / "pyJianYingDraft"
        / "assets",
    ]
    copied = ensure_assets_files(
        assets_dir=assets_dir,
        required_filenames=required,
        fallback_dirs=fallback_dirs,
    )
    missing = [name for name in required if not (assets_dir / name).exists()]
    return {
        "assets_dir": str(assets_dir),
        "copied": [str(p) for p in copied],
        "missing": missing,
    }


def build_intervals(
    beat_times_s: Sequence[float],
    total_duration_s: float,
    min_interval_s: float = 0.05,
) -> list[tuple[float, float]]:
    total = max(0.0, float(total_duration_s))
    if total <= 0:
        return []

    points = [float(t) for t in beat_times_s if 0.0 <= float(t) <= total]
    points.sort()

    merged_points: list[float] = []
    for p in points:
        if not merged_points or p > merged_points[-1]:
            merged_points.append(p)

    if not merged_points or merged_points[0] > 0.0:
        merged_points.insert(0, 0.0)
    if merged_points[-1] < total:
        merged_points.append(total)

    intervals: list[tuple[float, float]] = []
    for start, end in zip(merged_points, merged_points[1:]):
        if (end - start) >= min_interval_s:
            intervals.append((start, end))
    return intervals


def intervals_to_microseconds(
    intervals: Sequence[tuple[float, float]],
    total_duration_s: float,
    min_duration_us: int = 1,
) -> list[tuple[int, int]]:
    total_us = max(1, int(round(total_duration_s * 1_000_000)))
    normalized: list[tuple[int, int]] = []
    prev_end = 0

    for start_s, end_s in intervals:
        raw_start = int(start_s * 1_000_000)
        raw_end = int(end_s * 1_000_000)
        start_us = max(prev_end, raw_start)
        end_us = max(start_us + min_duration_us, raw_end)
        end_us = min(end_us, total_us)
        if end_us - start_us >= min_duration_us:
            normalized.append((start_us, end_us))
            prev_end = end_us
    return normalized


def clamp_intervals_to_max_end(
    intervals_us: Sequence[tuple[int, int]],
    max_end_us: int,
    min_duration_us: int = 1,
) -> list[tuple[int, int]]:
    if max_end_us <= 0:
        return []
    clipped: list[tuple[int, int]] = []
    prev_end = 0
    for start_us, end_us in intervals_us:
        start = max(prev_end, int(start_us))
        end = min(int(end_us), max_end_us)
        if end - start >= min_duration_us:
            clipped.append((start, end))
            prev_end = end
    return clipped


def split_intervals_by_max_duration(
    intervals_us: Sequence[tuple[int, int]],
    max_duration_us: int,
    min_duration_us: int = 1,
) -> list[tuple[int, int]]:
    max_us = int(max_duration_us)
    if max_us <= 0:
        return [(int(s), int(e)) for s, e in intervals_us if int(e) - int(s) >= min_duration_us]
    if max_us < min_duration_us:
        max_us = min_duration_us

    out: list[tuple[int, int]] = []
    for raw_start, raw_end in intervals_us:
        start = int(raw_start)
        end = int(raw_end)
        if end - start < min_duration_us:
            continue
        while (end - start) > max_us:
            cut = start + max_us
            if cut - start >= min_duration_us:
                out.append((start, cut))
            start = cut
        if end - start >= min_duration_us:
            out.append((start, end))
    return out


def adaptive_scene_threshold(sample_scores: Sequence[float], base_threshold: float) -> float:
    if not sample_scores:
        return float(base_threshold)
    arr = np.asarray(sample_scores, dtype=float)
    med = float(np.median(arr))
    mad = float(np.median(np.abs(arr - med)))
    p85 = float(np.quantile(arr, 0.85))
    p92 = float(np.quantile(arr, 0.92))
    robust = med + (1.2 * mad)

    base = float(base_threshold)
    min_allowed = max(0.06, base * 0.70)
    if p92 < base:
        # Low-contrast consecutive shots: lower threshold with a floor.
        threshold = max(min_allowed, max(robust, p85 * 0.95))
        threshold = min(base, threshold)
    else:
        # High-motion content: keep threshold conservative to avoid false cuts.
        threshold = max(base, min(p92 * 0.98, max(robust, p85 * 0.95)))

    return float(max(0.01, min(0.98, threshold)))


def detect_boundaries_from_score_series(
    *,
    sample_times_us: Sequence[int],
    sample_scores: Sequence[float],
    base_threshold: float,
    min_shot_us: int,
) -> list[int]:
    n = min(len(sample_times_us), len(sample_scores))
    if n <= 0:
        return []

    times = [int(t) for t in sample_times_us[:n]]
    scores = [float(s) for s in sample_scores[:n]]

    threshold = adaptive_scene_threshold(scores, base_threshold)
    relaxed_threshold = max(0.06, threshold * 0.88)
    jump_floor = max(0.05, threshold * 0.35)
    gap_us = max(1, int(min_shot_us))

    boundaries: list[int] = []
    last_cut_us = -10**18

    for i, (t_us, s) in enumerate(zip(times, scores)):
        if (t_us - last_cut_us) < gap_us:
            continue

        prev_s = scores[i - 1] if i > 0 else s
        next_s = scores[i + 1] if i + 1 < n else s
        local_mean = (prev_s + next_s) * 0.5
        is_peak = s >= prev_s and s >= next_s
        if not is_peak:
            continue

        start = max(0, i - 5)
        history = scores[start:i]
        baseline = float(np.median(history)) if history else local_mean
        jump = s - baseline
        local_delta = s - local_mean
        delta_floor = max(0.025, threshold * 0.08)

        absolute_hit = s >= threshold and s >= (local_mean * 1.12) and local_delta >= delta_floor
        subtle_hit = (
            s >= relaxed_threshold
            and jump >= jump_floor
            and s >= (local_mean * 1.08)
            and local_delta >= 0.03
        )
        hard_hit = s >= min(0.98, threshold * 1.45)

        if absolute_hit or subtle_hit or hard_hit:
            boundaries.append(t_us)
            last_cut_us = t_us

    return boundaries


def build_intervals_from_boundaries(
    boundaries_us: Sequence[int],
    total_duration_us: int,
    min_duration_us: int = 1,
) -> list[tuple[int, int]]:
    total_us = max(1, int(total_duration_us))
    cleaned = sorted({int(x) for x in boundaries_us if 0 <= int(x) <= total_us})

    keep: list[int] = [0]
    for b in cleaned:
        if b <= 0 or b >= total_us:
            continue
        if b - keep[-1] >= min_duration_us:
            keep.append(b)
    if keep[-1] != total_us:
        keep.append(total_us)

    out: list[tuple[int, int]] = []
    for start, end in zip(keep, keep[1:]):
        if end - start >= min_duration_us:
            out.append((start, end))
    return out


def pick_slice_for_interval(
    sources: Sequence[SliceCursor],
    beat_index: int,
    duration_us: int,
) -> tuple[Path, int]:
    if not sources:
        raise ValueError("No video sources available.")
    if duration_us <= 0:
        raise ValueError("duration_us must be positive.")

    src = sources[beat_index % len(sources)]
    if src.duration_us <= 0:
        return src.path, 0

    if src.cursor_us + duration_us > src.duration_us:
        src.cursor_us = 0

    source_start_us = src.cursor_us
    src.cursor_us = min(src.duration_us, src.cursor_us + duration_us)
    return src.path, source_start_us


def detect_beats(
    bgm_path: Path,
    hop_length: int = 512,
) -> tuple[list[float], float, float]:
    y, sr = librosa.load(str(bgm_path), sr=None, mono=True)
    if y.size == 0 or sr <= 0:
        raise ValueError(f"Failed to read audio: {bgm_path}")

    tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr, hop_length=hop_length, trim=False)
    beat_times = librosa.frames_to_time(beat_frames, sr=sr, hop_length=hop_length).tolist()
    total_duration_s = float(len(y)) / float(sr)
    tempo_value = float(np.asarray(tempo).reshape(-1)[0]) if np.asarray(tempo).size else 0.0
    return beat_times, total_duration_s, tempo_value


def discover_videos(video_dir: Path | None, explicit_videos: Sequence[str]) -> list[Path]:
    results: list[Path] = []
    for raw in explicit_videos:
        p = Path(raw).expanduser().resolve()
        if p.exists() and p.is_file():
            results.append(p)

    if video_dir:
        for p in sorted(video_dir.glob("*")):
            if p.is_file() and p.suffix.lower() in VIDEO_EXTENSIONS:
                results.append(p.resolve())

    deduped: list[Path] = []
    seen: set[str] = set()
    for p in results:
        key = str(p).lower()
        if key not in seen:
            seen.add(key)
            deduped.append(p)
    return deduped


def discover_audios(audio_dir: Path | None, explicit_audios: Sequence[str]) -> list[Path]:
    results: list[Path] = []
    for raw in explicit_audios:
        p = Path(raw).expanduser().resolve()
        if p.exists() and p.is_file():
            results.append(p)

    if audio_dir:
        for p in sorted(audio_dir.glob("*")):
            if p.is_file() and p.suffix.lower() in AUDIO_EXTENSIONS:
                results.append(p.resolve())

    deduped: list[Path] = []
    seen: set[str] = set()
    for p in results:
        key = str(p).lower()
        if key not in seen:
            seen.add(key)
            deduped.append(p)
    return deduped


def sanitize_project_component(text: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", str(text))
    cleaned = re.sub(r"\s+", "_", cleaned.strip())
    cleaned = cleaned.strip("._")
    return cleaned or "untitled"


def sanitize_draft_project_name(text: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", str(text)).strip().strip(".")
    cleaned = re.sub(r"\s+", " ", cleaned)
    while ".." in cleaned:
        cleaned = cleaned.replace("..", "_")
    if not cleaned:
        raise ValueError("Invalid project_name: empty after sanitization.")
    return cleaned


def resolve_drafts_root_path(drafts_root: str | None) -> Path:
    root = drafts_root or get_default_drafts_root()
    return Path(root).expanduser().resolve()


def ensure_unique_project_name(project_name: str, drafts_root: str | None = None) -> str:
    sanitized = sanitize_draft_project_name(project_name)
    root = resolve_drafts_root_path(drafts_root)
    candidate = sanitized
    suffix = 2
    while (root / candidate).exists():
        candidate = f"{sanitized}_{suffix}"
        suffix += 1
    return candidate


def make_project_name_for_audio(prefix: str, bgm_path: Path, index: int) -> str:
    safe_prefix = sanitize_project_component(prefix)
    safe_stem = sanitize_project_component(bgm_path.stem)
    return f"{safe_prefix}_{index:02d}_{safe_stem}"


def make_project_name_for_video_only(prefix: str) -> str:
    safe_prefix = sanitize_project_component(prefix)
    return f"{safe_prefix}_video_only"


def add_audio_beat_segments(
    project: JyProject,
    bgm_path: Path,
    intervals_us: Sequence[tuple[int, int]],
    audio_track: str,
    audio_material: draft.AudioMaterial | None = None,
) -> int:
    if audio_track not in project.script.tracks:
        project.script.add_track(draft.TrackType.audio, audio_track)

    material = audio_material or draft.AudioMaterial(str(bgm_path))
    created = 0
    for start_us, end_us in intervals_us:
        duration_us = max(1, end_us - start_us)
        seg = draft.AudioSegment(
            material,
            trange(start_us, duration_us),
            source_timerange=trange(start_us, duration_us),
        )
        project.script.add_segment(seg, audio_track)
        created += 1
    return created


def add_video_segments_by_beats(
    project: JyProject,
    video_paths: Sequence[Path],
    intervals_us: Sequence[tuple[int, int]],
    video_track: str,
) -> int:
    sources: list[SliceCursor] = []
    for path in video_paths:
        duration_s = get_duration_ffprobe_cached(str(path))
        duration_us = max(1, int(duration_s * 1_000_000))
        sources.append(SliceCursor(path=path, duration_us=duration_us))

    created = 0
    for idx, (target_start_us, target_end_us) in enumerate(intervals_us):
        duration_us = max(1, target_end_us - target_start_us)
        source_path, source_start_us = pick_slice_for_interval(sources, idx, duration_us)
        ok = add_video_segment_compat(
            project=project,
            media_path=source_path,
            target_start_us=target_start_us,
            duration_us=duration_us,
            source_start_us=source_start_us,
            track_name=video_track,
        )
        if ok:
            created += 1
    return created


def detect_shot_intervals(
    media_path: Path,
    scene_threshold: float = 0.24,
    min_shot_sec: float = 0.12,
    analysis_fps: float = 10.0,
) -> list[tuple[int, int]]:
    total_us = max(1, int(get_duration_ffprobe_cached(str(media_path)) * 1_000_000))
    if total_us <= 1:
        return []

    try:
        import cv2  # type: ignore
    except Exception:
        return [(0, total_us)]

    cap = cv2.VideoCapture(str(media_path))
    if not cap.isOpened():
        return [(0, total_us)]

    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
    if fps <= 0:
        fps = 25.0
    target_analysis_fps = max(4.0, float(analysis_fps))
    step = max(1, int(round(fps / max(0.1, target_analysis_fps))))
    min_shot_us = max(1, int(min_shot_sec * 1_000_000))

    boundaries = [0]
    last_hist = None
    last_gray = None
    last_edge = None
    last_phash = None
    frame_index = 0
    sample_times_us: list[int] = []
    sample_scores: list[float] = []

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            if frame_index % step == 0:
                small = cv2.resize(frame, (160, 90))
                hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
                gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
                edge = cv2.Canny(gray, 64, 160)
                hist = cv2.calcHist([hsv], [0, 1], None, [16, 16], [0, 180, 0, 256])
                cv2.normalize(hist, hist, alpha=1.0, norm_type=cv2.NORM_L1)

                gray32 = cv2.resize(gray, (32, 32))
                dct = cv2.dct(np.float32(gray32))
                dct8 = dct[:8, :8]
                dct_flat = dct8.flatten()
                median = float(np.median(dct_flat[1:])) if dct_flat.size > 1 else float(np.median(dct_flat))
                phash = dct8 > median

                if last_hist is not None and last_gray is not None:
                    hist_diff = float(cv2.compareHist(last_hist, hist, cv2.HISTCMP_BHATTACHARYYA))
                    gray_diff = float(
                        cv2.norm(gray, last_gray, cv2.NORM_L1) / (gray.size * 255.0)
                    )
                    edge_diff = (
                        float(np.mean(edge != last_edge))
                        if last_edge is not None
                        else 0.0
                    )
                    phash_diff = (
                        float(np.mean(phash != last_phash))
                        if last_phash is not None
                        else 0.0
                    )
                    diff = (
                        (hist_diff * 0.42)
                        + (gray_diff * 0.20)
                        + (edge_diff * 0.18)
                        + (phash_diff * 0.20)
                    )
                    t_us = int((frame_index / fps) * 1_000_000)
                    sample_times_us.append(t_us)
                    sample_scores.append(diff)
                last_hist = hist
                last_gray = gray
                last_edge = edge
                last_phash = phash
            frame_index += 1
    finally:
        cap.release()

    boundaries.extend(
        detect_boundaries_from_score_series(
            sample_times_us=sample_times_us,
            sample_scores=sample_scores,
            base_threshold=scene_threshold,
            min_shot_us=min_shot_us,
        )
    )

    return build_intervals_from_boundaries(boundaries, total_us, min_duration_us=min_shot_us)


def add_video_segments_by_shot(
    project: JyProject,
    video_paths: Sequence[Path],
    video_track: str,
    scene_threshold: float = 0.24,
    min_shot_sec: float = 0.12,
    analysis_fps: float = 10.0,
    max_shot_sec: float = 0.0,
) -> int:
    cursor_us = 0
    created = 0
    max_shot_us = int(max(0.0, float(max_shot_sec)) * 1_000_000)
    for video in video_paths:
        shot_intervals = detect_shot_intervals(
            video,
            scene_threshold=scene_threshold,
            min_shot_sec=min_shot_sec,
            analysis_fps=analysis_fps,
        )
        if not shot_intervals:
            full_us = max(1, int(get_duration_ffprobe_cached(str(video)) * 1_000_000))
            shot_intervals = [(0, full_us)]
        shot_intervals = split_intervals_by_max_duration(
            shot_intervals,
            max_duration_us=max_shot_us,
            min_duration_us=1,
        )

        for source_start_us, source_end_us in shot_intervals:
            duration_us = max(1, source_end_us - source_start_us)
            ok = add_video_segment_compat(
                project=project,
                media_path=video,
                target_start_us=cursor_us,
                duration_us=duration_us,
                source_start_us=source_start_us,
                track_name=video_track,
            )
            if ok:
                created += 1
                cursor_us += duration_us
    return created


def add_video_segment_compat(
    *,
    project: JyProject,
    media_path: Path,
    target_start_us: int,
    duration_us: int,
    source_start_us: int = 0,
    track_name: str = "VideoTrack",
) -> bool:
    if not media_path.exists():
        return False
    if track_name not in project.script.tracks:
        project.script.add_track(draft.TrackType.video, track_name)

    try:
        mat = draft.VideoMaterial(str(media_path))
    except Exception:
        return False

    phys_duration = int(getattr(mat, "duration", 0) or 0)
    if phys_duration <= 0:
        ff_dur = get_duration_ffprobe_cached(str(media_path))
        if ff_dur > 0:
            phys_duration = int(ff_dur * 1_000_000)
            try:
                mat.duration = phys_duration
            except Exception:
                pass
    if phys_duration <= 0:
        return False

    src_start = max(0, int(source_start_us))
    available = max(1, phys_duration - src_start)
    actual_duration = max(1, min(int(duration_us), available))

    try:
        seg = draft.VideoSegment(
            mat,
            trange(int(target_start_us), actual_duration),
            source_timerange=trange(src_start, actual_duration),
        )
        project.script.add_segment(seg, track_name)
        return True
    except Exception:
        return False


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import BGM + videos into JianYing and split by every detected beat."
    )
    parser.add_argument("--bgm", help="Single background music file path.")
    parser.add_argument(
        "--bgms",
        nargs="*",
        default=[],
        help="Multiple background music files.",
    )
    parser.add_argument("--audio-dir", help="Directory containing source audios.")
    parser.add_argument("--video-dir", help="Directory containing source videos.")
    parser.add_argument(
        "--videos",
        nargs="*",
        default=[],
        help="Explicit video files (can combine with --video-dir).",
    )
    parser.add_argument("--project-name", default="BeatAutoCut_Fast", help="JianYing draft name.")
    parser.add_argument("--drafts-root", default=None, help="Optional JianYing drafts root path.")
    parser.add_argument("--audio-track", default="BGM_Beat", help="Audio track name.")
    parser.add_argument("--video-track", default="VideoTrack", help="Video track name.")
    parser.add_argument(
        "--video-cut-mode",
        default="shot",
        choices=["shot", "beat"],
        help="How to segment video: shot detection or beat slicing.",
    )
    parser.add_argument(
        "--shot-detail-level",
        default="custom",
        choices=["custom", "coarse", "medium", "fine"],
        help="Preset for video shot splitting detail level.",
    )
    parser.add_argument(
        "--shot-scene-threshold",
        type=float,
        default=0.24,
        help="Shot-cut sensitivity threshold (smaller means more cuts).",
    )
    parser.add_argument(
        "--shot-min-sec",
        type=float,
        default=0.12,
        help="Minimum shot duration in seconds.",
    )
    parser.add_argument(
        "--shot-analysis-fps",
        type=float,
        default=10.0,
        help="Frame sampling rate for shot detection.",
    )
    parser.add_argument(
        "--shot-max-sec",
        type=float,
        default=0.0,
        help="Force split long shots to this max duration in seconds (0 to disable).",
    )
    parser.add_argument(
        "--min-interval-ms",
        type=float,
        default=50.0,
        help="Skip intervals shorter than this threshold.",
    )
    parser.add_argument(
        "--report-json",
        default=str(Path(__file__).with_name("last_run_report.json")),
        help="Where to write run summary JSON.",
    )
    return parser.parse_args(argv)


def validate_inputs(bgm_path: Path | None, video_paths: Sequence[Path]) -> None:
    if bgm_path is None and not video_paths:
        raise ValueError("At least one source is required: audio or video.")
    if bgm_path is not None and (not bgm_path.exists() or not bgm_path.is_file()):
        raise FileNotFoundError(f"BGM file not found: {bgm_path}")


def run_for_media_paths(
    *,
    bgm_path: Path | None,
    video_paths: Sequence[Path],
    project_name: str,
    drafts_root: str | None = None,
    audio_track: str = "BGM_Beat",
    video_track: str = "VideoTrack",
    video_cut_mode: str = "shot",
    shot_detail_level: str = "custom",
    shot_scene_threshold: float = 0.24,
    shot_min_sec: float = 0.12,
    shot_analysis_fps: float = 10.0,
    shot_max_sec: float = 0.0,
    min_interval_ms: float = 50.0,
    report_json: str | None = None,
) -> dict:
    normalized_shot_detail_level = normalize_shot_detail_level(shot_detail_level)
    project_name = ensure_unique_project_name(project_name, drafts_root)
    resolved_shot_settings = resolve_shot_detail_settings(
        normalized_shot_detail_level,
        shot_scene_threshold=shot_scene_threshold,
        shot_min_sec=shot_min_sec,
        shot_analysis_fps=shot_analysis_fps,
        shot_max_sec=shot_max_sec,
    )
    shot_scene_threshold = resolved_shot_settings["shot_scene_threshold"]
    shot_min_sec = resolved_shot_settings["shot_min_sec"]
    shot_analysis_fps = resolved_shot_settings["shot_analysis_fps"]
    shot_max_sec = resolved_shot_settings["shot_max_sec"]

    asset_fix = ensure_pyjianying_asset_templates()
    if asset_fix["missing"]:
        missing_str = ", ".join(asset_fix["missing"])
        raise FileNotFoundError(
            f"Missing pyJianYingDraft template assets: {missing_str}. "
            f"assets_dir={asset_fix['assets_dir']}"
        )

    validate_inputs(bgm_path, video_paths)

    project = JyProject(
        project_name=project_name,
        drafts_root=drafts_root,
        overwrite=True,
    )

    beat_times: list[float] = []
    total_duration_s = 0.0
    tempo = 0.0
    intervals_us: list[tuple[int, int]] = []
    audio_segments = 0
    video_segments = 0

    if bgm_path is not None:
        beat_times, total_duration_s, tempo = detect_beats(bgm_path)
        intervals = build_intervals(
            beat_times_s=beat_times,
            total_duration_s=total_duration_s,
            min_interval_s=max(0.0, float(min_interval_ms) / 1000.0),
        )
        intervals_us = intervals_to_microseconds(intervals, total_duration_s, min_duration_us=1)
        if not intervals:
            raise RuntimeError("No valid beat intervals produced from the provided music.")
        if not intervals_us:
            raise RuntimeError("No valid microsecond intervals produced from beat intervals.")

        audio_material = draft.AudioMaterial(str(bgm_path))
        material_duration_us = int(getattr(audio_material, "duration", 0) or 0)
        if material_duration_us > 0:
            intervals_us = clamp_intervals_to_max_end(intervals_us, material_duration_us, min_duration_us=1)
            total_duration_s = min(total_duration_s, material_duration_us / 1_000_000.0)
        if not intervals_us:
            raise RuntimeError("No valid intervals remain after clamping to audio duration.")

        audio_segments = add_audio_beat_segments(
            project,
            bgm_path,
            intervals_us,
            audio_track,
            audio_material=audio_material,
        )
        if video_paths:
            if video_cut_mode == "beat":
                video_segments = add_video_segments_by_beats(
                    project, video_paths, intervals_us, video_track
                )
            else:
                video_segments = add_video_segments_by_shot(
                    project,
                    video_paths,
                    video_track,
                    scene_threshold=shot_scene_threshold,
                    min_shot_sec=shot_min_sec,
                    analysis_fps=shot_analysis_fps,
                    max_shot_sec=shot_max_sec,
                )
    else:
        video_segments = add_video_segments_by_shot(
            project,
            video_paths,
            video_track,
            scene_threshold=shot_scene_threshold,
            min_shot_sec=shot_min_sec,
            analysis_fps=shot_analysis_fps,
            max_shot_sec=shot_max_sec,
        )

    save_result = project.save()

    report = {
        "status": "SUCCESS",
        "project_name": project_name,
        "draft_path": save_result.get("draft_path"),
        "bgm_path": str(bgm_path) if bgm_path else None,
        "video_count": len(video_paths),
        "beat_count": len(beat_times),
        "interval_count": len(intervals_us),
        "audio_segment_count": audio_segments,
        "video_segment_count": video_segments,
        "video_cut_mode": video_cut_mode,
        "shot_detail_level": normalized_shot_detail_level,
        "shot_scene_threshold": shot_scene_threshold,
        "shot_min_sec": shot_min_sec,
        "shot_analysis_fps": shot_analysis_fps,
        "shot_max_sec": shot_max_sec,
        "tempo_bpm": round(tempo, 3),
        "audio_duration_s": round(total_duration_s, 3),
        "skill_root": SKILL_ROOT,
    }

    if report_json:
        report_path = Path(report_json).expanduser().resolve()
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def run_batch(
    *,
    bgm_paths: Sequence[Path],
    video_paths: Sequence[Path],
    project_name_prefix: str,
    drafts_root: str | None = None,
    audio_track: str = "BGM_Beat",
    video_track: str = "VideoTrack",
    video_cut_mode: str = "shot",
    shot_detail_level: str = "custom",
    shot_scene_threshold: float = 0.24,
    shot_min_sec: float = 0.12,
    shot_analysis_fps: float = 10.0,
    shot_max_sec: float = 0.0,
    min_interval_ms: float = 50.0,
    report_dir: str | None = None,
    progress_hook: Callable[[dict], None] | None = None,
) -> list[dict]:
    if not bgm_paths and not video_paths:
        raise ValueError("No sources found. Provide at least audio or video.")
    normalized_shot_detail_level = normalize_shot_detail_level(shot_detail_level)
    resolved_shot_settings = resolve_shot_detail_settings(
        normalized_shot_detail_level,
        shot_scene_threshold=shot_scene_threshold,
        shot_min_sec=shot_min_sec,
        shot_analysis_fps=shot_analysis_fps,
        shot_max_sec=shot_max_sec,
    )
    shot_scene_threshold = resolved_shot_settings["shot_scene_threshold"]
    shot_min_sec = resolved_shot_settings["shot_min_sec"]
    shot_analysis_fps = resolved_shot_settings["shot_analysis_fps"]
    shot_max_sec = resolved_shot_settings["shot_max_sec"]
    reports: list[dict] = []
    if not bgm_paths:
        project_name = ensure_unique_project_name(
            make_project_name_for_video_only(project_name_prefix),
            drafts_root,
        )
        if progress_hook:
            progress_hook(
                {
                    "event": "start",
                    "index": 1,
                    "total": 1,
                    "project_name": project_name,
                    "bgm_path": None,
                }
            )
        report_json = None
        if report_dir:
            report_json = str(Path(report_dir).expanduser().resolve() / f"{project_name}.json")
        report = run_for_media_paths(
            bgm_path=None,
            video_paths=video_paths,
            project_name=project_name,
            drafts_root=drafts_root,
            audio_track=audio_track,
            video_track=video_track,
            video_cut_mode=video_cut_mode,
            shot_detail_level=normalized_shot_detail_level,
            shot_scene_threshold=shot_scene_threshold,
            shot_min_sec=shot_min_sec,
            shot_analysis_fps=shot_analysis_fps,
            shot_max_sec=shot_max_sec,
            min_interval_ms=min_interval_ms,
            report_json=report_json,
        )
        reports.append(report)
        if progress_hook:
            progress_hook(
                {
                    "event": "done",
                    "index": 1,
                    "total": 1,
                    "project_name": project_name,
                    "report": report,
                }
            )
        return reports

    for idx, bgm_path in enumerate(bgm_paths, start=1):
        project_name = ensure_unique_project_name(
            make_project_name_for_audio(project_name_prefix, bgm_path, idx),
            drafts_root,
        )
        if progress_hook:
            progress_hook(
                {
                    "event": "start",
                    "index": idx,
                    "total": len(bgm_paths),
                    "project_name": project_name,
                    "bgm_path": str(bgm_path),
                }
            )
        report_json = None
        if report_dir:
            report_json = str(Path(report_dir).expanduser().resolve() / f"{project_name}.json")
        report = run_for_media_paths(
            bgm_path=bgm_path,
            video_paths=video_paths,
            project_name=project_name,
            drafts_root=drafts_root,
            audio_track=audio_track,
            video_track=video_track,
            video_cut_mode=video_cut_mode,
            shot_detail_level=normalized_shot_detail_level,
            shot_scene_threshold=shot_scene_threshold,
            shot_min_sec=shot_min_sec,
            shot_analysis_fps=shot_analysis_fps,
            shot_max_sec=shot_max_sec,
            min_interval_ms=min_interval_ms,
            report_json=report_json,
        )
        reports.append(report)
        if progress_hook:
            progress_hook(
                {
                    "event": "done",
                    "index": idx,
                    "total": len(bgm_paths),
                    "project_name": project_name,
                    "report": report,
                }
            )
    return reports


def run(argv: Sequence[str] | None = None) -> dict:
    args = parse_args(argv)
    video_dir = Path(args.video_dir).expanduser().resolve() if args.video_dir else None
    audio_dir = Path(args.audio_dir).expanduser().resolve() if args.audio_dir else None
    video_paths = discover_videos(video_dir, args.videos)

    explicit_audios: list[str] = list(args.bgms)
    if args.bgm:
        explicit_audios.append(args.bgm)
    bgm_paths = discover_audios(audio_dir, explicit_audios)

    if len(bgm_paths) == 0:
        return run_for_media_paths(
            bgm_path=None,
            video_paths=video_paths,
            project_name=make_project_name_for_video_only(args.project_name),
            drafts_root=args.drafts_root,
            audio_track=args.audio_track,
            video_track=args.video_track,
            video_cut_mode=args.video_cut_mode,
            shot_detail_level=args.shot_detail_level,
            shot_scene_threshold=args.shot_scene_threshold,
            shot_min_sec=args.shot_min_sec,
            shot_analysis_fps=args.shot_analysis_fps,
            shot_max_sec=args.shot_max_sec,
            min_interval_ms=args.min_interval_ms,
            report_json=args.report_json,
        )

    if len(bgm_paths) == 1:
        return run_for_media_paths(
            bgm_path=bgm_paths[0],
            video_paths=video_paths,
            project_name=args.project_name,
            drafts_root=args.drafts_root,
            audio_track=args.audio_track,
            video_track=args.video_track,
            video_cut_mode=args.video_cut_mode,
            shot_detail_level=args.shot_detail_level,
            shot_scene_threshold=args.shot_scene_threshold,
            shot_min_sec=args.shot_min_sec,
            shot_analysis_fps=args.shot_analysis_fps,
            shot_max_sec=args.shot_max_sec,
            min_interval_ms=args.min_interval_ms,
            report_json=args.report_json,
        )

    report_dir = str(Path(args.report_json).expanduser().resolve().parent)
    batch_reports = run_batch(
        bgm_paths=bgm_paths,
        video_paths=video_paths,
        project_name_prefix=args.project_name,
        drafts_root=args.drafts_root,
        audio_track=args.audio_track,
        video_track=args.video_track,
        video_cut_mode=args.video_cut_mode,
        shot_detail_level=args.shot_detail_level,
        shot_scene_threshold=args.shot_scene_threshold,
        shot_min_sec=args.shot_min_sec,
        shot_analysis_fps=args.shot_analysis_fps,
        shot_max_sec=args.shot_max_sec,
        min_interval_ms=args.min_interval_ms,
        report_dir=report_dir,
    )
    return {
        "status": "SUCCESS",
        "mode": "batch",
        "project_count": len(batch_reports),
        "projects": batch_reports,
        "report_dir": report_dir,
    }


def main() -> None:
    report = run()
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
