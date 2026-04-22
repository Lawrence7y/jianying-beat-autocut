from pathlib import Path

from jianying_beat_autocut import (
    DEFAULT_SHOT_DETAIL_LEVEL,
    SHOT_DETAIL_PRESETS,
    SliceCursor,
    build_intervals_from_boundaries,
    build_intervals,
    clamp_intervals_to_max_end,
    detect_boundaries_from_score_series,
    ensure_unique_project_name,
    intervals_to_microseconds,
    match_shot_detail_level_for_settings,
    pick_slice_for_interval,
    resolve_shot_detail_settings,
    split_intervals_by_max_duration,
)


def test_build_intervals_adds_zero_and_end():
    intervals = build_intervals([0.4, 0.9, 1.5], total_duration_s=2.0, min_interval_s=0.05)
    assert intervals == [
        (0.0, 0.4),
        (0.4, 0.9),
        (0.9, 1.5),
        (1.5, 2.0),
    ]


def test_default_shot_detail_level_is_medium():
    assert DEFAULT_SHOT_DETAIL_LEVEL == "medium"


def test_resolve_shot_detail_settings_returns_coarse_preset():
    settings = resolve_shot_detail_settings("coarse")
    assert settings == SHOT_DETAIL_PRESETS["coarse"]


def test_resolve_shot_detail_settings_returns_custom_values_for_custom_mode():
    settings = resolve_shot_detail_settings(
        "custom",
        shot_scene_threshold=0.31,
        shot_min_sec=0.22,
        shot_analysis_fps=9.0,
        shot_max_sec=0.0,
    )
    assert settings == {
        "shot_scene_threshold": 0.31,
        "shot_min_sec": 0.22,
        "shot_analysis_fps": 9.0,
        "shot_max_sec": 0.0,
    }


def test_match_shot_detail_level_for_settings_returns_preset_name():
    level = match_shot_detail_level_for_settings(SHOT_DETAIL_PRESETS["fine"])
    assert level == "fine"


def test_match_shot_detail_level_for_settings_returns_custom_for_non_preset_values():
    level = match_shot_detail_level_for_settings(
        {
            "shot_scene_threshold": 0.27,
            "shot_min_sec": 0.15,
            "shot_analysis_fps": 11.0,
            "shot_max_sec": 0.0,
        }
    )
    assert level == "custom"


def test_ensure_unique_project_name_appends_suffix_when_existing(tmp_path):
    (tmp_path / "Demo_video_only").mkdir()
    (tmp_path / "Demo_video_only_2").mkdir()

    result = ensure_unique_project_name("Demo_video_only", str(tmp_path))

    assert result == "Demo_video_only_3"


def test_build_intervals_skips_too_short_segments():
    intervals = build_intervals([0.0, 0.01, 0.03, 0.2], total_duration_s=0.3, min_interval_s=0.05)
    assert intervals == [
        (0.03, 0.2),
        (0.2, 0.3),
    ]


def test_intervals_to_microseconds_is_monotonic_no_overlap():
    intervals = [
        (2.8675736961451247, 3.4829931972789114),
        (3.4829931972789114, 4.098321995464852),
    ]
    converted = intervals_to_microseconds(intervals, total_duration_s=5.2, min_duration_us=1)
    assert converted == [
        (2867573, 3482993),
        (3482993, 4098321),
    ]


def test_clamp_intervals_to_max_end_avoids_overflow():
    intervals_us = [
        (149_386_666, 154_148_343),
        (154_148_343, 154_500_000),
    ]
    out = clamp_intervals_to_max_end(intervals_us, max_end_us=154_148_000, min_duration_us=1)
    assert out == [
        (149_386_666, 154_148_000),
    ]


def test_build_intervals_from_boundaries_keeps_full_coverage():
    out = build_intervals_from_boundaries(
        boundaries_us=[0, 100_000, 150_000, 300_000],
        total_duration_us=300_000,
        min_duration_us=120_000,
    )
    assert out == [
        (0, 150_000),
        (150_000, 300_000),
    ]


def test_split_intervals_by_max_duration_splits_long_interval():
    out = split_intervals_by_max_duration(
        intervals_us=[(0, 1_000_000)],
        max_duration_us=300_000,
        min_duration_us=1,
    )
    assert out == [
        (0, 300_000),
        (300_000, 600_000),
        (600_000, 900_000),
        (900_000, 1_000_000),
    ]


def test_split_intervals_by_max_duration_disabled_when_non_positive():
    intervals = [(0, 500_000), (500_000, 900_000)]
    out = split_intervals_by_max_duration(
        intervals_us=intervals,
        max_duration_us=0,
        min_duration_us=1,
    )
    assert out == intervals


def test_detect_boundaries_from_score_series_detects_real_peaks():
    times = [100_000, 200_000, 300_000, 400_000, 500_000, 600_000]
    scores = [0.05, 0.07, 0.31, 0.08, 0.29, 0.07]
    out = detect_boundaries_from_score_series(
        sample_times_us=times,
        sample_scores=scores,
        base_threshold=0.24,
        min_shot_us=80_000,
    )
    assert out == [300_000, 500_000]


def test_detect_boundaries_from_score_series_respects_min_shot_gap():
    times = [100_000, 200_000, 300_000, 400_000]
    scores = [0.06, 0.34, 0.32, 0.06]
    out = detect_boundaries_from_score_series(
        sample_times_us=times,
        sample_scores=scores,
        base_threshold=0.24,
        min_shot_us=250_000,
    )
    assert out == [200_000]


def test_detect_boundaries_from_score_series_handles_similar_consecutive_shots():
    times = [100_000, 200_000, 300_000, 400_000, 500_000]
    scores = [0.08, 0.09, 0.17, 0.10, 0.09]
    out = detect_boundaries_from_score_series(
        sample_times_us=times,
        sample_scores=scores,
        base_threshold=0.24,
        min_shot_us=80_000,
    )
    assert out == [300_000]


def test_detect_boundaries_from_score_series_ignores_small_noise_bumps():
    times = [100_000, 200_000, 300_000, 400_000, 500_000]
    scores = [0.08, 0.10, 0.12, 0.10, 0.09]
    out = detect_boundaries_from_score_series(
        sample_times_us=times,
        sample_scores=scores,
        base_threshold=0.24,
        min_shot_us=80_000,
    )
    assert out == []


def test_detect_boundaries_from_score_series_ignores_repetitive_motion_spikes():
    times = [100_000, 200_000, 300_000, 400_000, 500_000, 600_000, 700_000, 800_000, 900_000, 1_000_000]
    scores = [0.10, 0.12, 0.17, 0.11, 0.13, 0.18, 0.12, 0.14, 0.17, 0.11]
    out = detect_boundaries_from_score_series(
        sample_times_us=times,
        sample_scores=scores,
        base_threshold=0.28,
        min_shot_us=300_000,
    )
    assert out == []


def test_pick_slice_rotates_and_resets_when_insufficient_remaining():
    sources = [
        SliceCursor(path=Path(r"C:\v1.mp4"), duration_us=2_000_000),
        SliceCursor(path=Path(r"C:\v2.mp4"), duration_us=1_000_000),
    ]
    # First pick from v1
    p1, start1 = pick_slice_for_interval(sources, beat_index=0, duration_us=900_000)
    assert p1.name == "v1.mp4"
    assert start1 == 0

    # Second pick from v2
    p2, start2 = pick_slice_for_interval(sources, beat_index=1, duration_us=900_000)
    assert p2.name == "v2.mp4"
    assert start2 == 0

    # Third pick back to v1 with advanced cursor
    p3, start3 = pick_slice_for_interval(sources, beat_index=2, duration_us=900_000)
    assert p3.name == "v1.mp4"
    assert start3 == 900_000

    # Fourth pick to v2; not enough remaining, should reset to 0
    p4, start4 = pick_slice_for_interval(sources, beat_index=3, duration_us=900_000)
    assert p4.name == "v2.mp4"
    assert start4 == 0
