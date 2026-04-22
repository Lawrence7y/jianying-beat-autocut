from pathlib import Path

from jianying_beat_autocut import (
    SHOT_DETAIL_PRESETS,
    make_project_name_for_audio,
    make_project_name_for_video_only,
    run_batch,
)


def test_make_project_name_for_audio_keeps_prefix_and_index():
    result = make_project_name_for_audio("MyProj", Path(r"E:\audio\beat_song.mp3"), 2)
    assert result == "MyProj_02_beat_song"


def test_make_project_name_for_audio_sanitizes_bad_chars():
    result = make_project_name_for_audio("My:Proj", Path(r"E:\audio\a<>b?.mp3"), 12)
    assert result == "My_Proj_12_a_b"


def test_run_batch_calls_worker_for_each_audio(monkeypatch, tmp_path):
    audio1 = tmp_path / "a1.mp3"
    audio2 = tmp_path / "a2.mp3"
    video = tmp_path / "v1.mp4"
    audio1.write_bytes(b"x")
    audio2.write_bytes(b"y")
    video.write_bytes(b"z")

    calls = []

    def fake_run_for_media_paths(**kwargs):
        calls.append(kwargs)
        return {"status": "SUCCESS", "project_name": kwargs["project_name"]}

    monkeypatch.setattr("jianying_beat_autocut.run_for_media_paths", fake_run_for_media_paths)

    reports = run_batch(
        bgm_paths=[audio1, audio2],
        video_paths=[video],
        project_name_prefix="BatchProj",
        report_dir=str(tmp_path / "reports"),
    )

    assert len(reports) == 2
    assert calls[0]["project_name"] == "BatchProj_01_a1"
    assert calls[1]["project_name"] == "BatchProj_02_a2"


def test_run_batch_emits_progress_events(monkeypatch, tmp_path):
    audio = tmp_path / "a1.mp3"
    video = tmp_path / "v1.mp4"
    audio.write_bytes(b"x")
    video.write_bytes(b"z")

    def fake_run_for_media_paths(**kwargs):
        return {"status": "SUCCESS", "project_name": kwargs["project_name"]}

    monkeypatch.setattr("jianying_beat_autocut.run_for_media_paths", fake_run_for_media_paths)

    events = []
    run_batch(
        bgm_paths=[audio],
        video_paths=[video],
        project_name_prefix="BatchProj",
        report_dir=str(tmp_path / "reports"),
        progress_hook=events.append,
    )

    assert len(events) == 2
    assert events[0]["event"] == "start"
    assert events[1]["event"] == "done"


def test_make_project_name_for_video_only():
    assert make_project_name_for_video_only("Demo") == "Demo_video_only"


def test_run_batch_supports_video_only(monkeypatch, tmp_path):
    video = tmp_path / "v1.mp4"
    video.write_bytes(b"z")
    calls = []

    def fake_run_for_media_paths(**kwargs):
        calls.append(kwargs)
        return {"status": "SUCCESS", "project_name": kwargs["project_name"]}

    monkeypatch.setattr("jianying_beat_autocut.run_for_media_paths", fake_run_for_media_paths)

    reports = run_batch(
        bgm_paths=[],
        video_paths=[video],
        project_name_prefix="OnlyVideo",
        report_dir=str(tmp_path / "reports"),
    )

    assert len(reports) == 1
    assert calls[0]["bgm_path"] is None
    assert calls[0]["project_name"] == "OnlyVideo_video_only"


def test_run_batch_applies_shot_detail_preset(monkeypatch, tmp_path):
    video = tmp_path / "v1.mp4"
    video.write_bytes(b"z")
    calls = []

    def fake_run_for_media_paths(**kwargs):
        calls.append(kwargs)
        return {"status": "SUCCESS", "project_name": kwargs["project_name"]}

    monkeypatch.setattr("jianying_beat_autocut.run_for_media_paths", fake_run_for_media_paths)

    run_batch(
        bgm_paths=[],
        video_paths=[video],
        project_name_prefix="PresetProj",
        shot_detail_level="coarse",
        report_dir=str(tmp_path / "reports"),
    )

    assert calls[0]["shot_scene_threshold"] == SHOT_DETAIL_PRESETS["coarse"]["shot_scene_threshold"]
    assert calls[0]["shot_min_sec"] == SHOT_DETAIL_PRESETS["coarse"]["shot_min_sec"]
    assert calls[0]["shot_analysis_fps"] == SHOT_DETAIL_PRESETS["coarse"]["shot_analysis_fps"]
    assert calls[0]["shot_max_sec"] == SHOT_DETAIL_PRESETS["coarse"]["shot_max_sec"]


def test_run_batch_uses_unique_project_name_when_same_name_exists(monkeypatch, tmp_path):
    drafts_root = tmp_path / "drafts"
    drafts_root.mkdir()
    (drafts_root / "OnlyVideo_video_only").mkdir()

    video = tmp_path / "v1.mp4"
    video.write_bytes(b"z")
    calls = []

    def fake_run_for_media_paths(**kwargs):
        calls.append(kwargs)
        return {"status": "SUCCESS", "project_name": kwargs["project_name"]}

    monkeypatch.setattr("jianying_beat_autocut.run_for_media_paths", fake_run_for_media_paths)

    run_batch(
        bgm_paths=[],
        video_paths=[video],
        project_name_prefix="OnlyVideo",
        drafts_root=str(drafts_root),
        report_dir=str(tmp_path / "reports"),
    )

    assert calls[0]["project_name"] == "OnlyVideo_video_only_2"
