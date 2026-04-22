from pathlib import Path

from jianying_beat_autocut import ensure_assets_files


def test_ensure_assets_files_copies_missing_templates(tmp_path):
    assets_dir = tmp_path / "target_assets"
    fb1 = tmp_path / "fb1"
    fb2 = tmp_path / "fb2"
    fb1.mkdir(parents=True, exist_ok=True)
    fb2.mkdir(parents=True, exist_ok=True)

    required = ["draft_content_template.json", "draft_meta_info.json"]
    (fb2 / "draft_content_template.json").write_text("{}", encoding="utf-8")
    (fb2 / "draft_meta_info.json").write_text("{}", encoding="utf-8")

    copied = ensure_assets_files(
        assets_dir=assets_dir,
        required_filenames=required,
        fallback_dirs=[fb1, fb2],
    )

    assert len(copied) == 2
    assert (assets_dir / "draft_content_template.json").exists()
    assert (assets_dir / "draft_meta_info.json").exists()
