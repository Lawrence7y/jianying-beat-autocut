from __future__ import annotations

import datetime as dt
import traceback
from pathlib import Path

from flask import Flask, render_template_string, request
from werkzeug.utils import secure_filename

from jianying_beat_autocut import AUDIO_EXTENSIONS, VIDEO_EXTENSIONS, run_batch


APP_DIR = Path(__file__).resolve().parent
UPLOAD_ROOT = APP_DIR / "uploads"
REPORT_ROOT = APP_DIR / "reports"

UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
REPORT_ROOT.mkdir(parents=True, exist_ok=True)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024 * 1024  # 10GB


PAGE = """
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>剪映节拍自动切分应用</title>
  <style>
    :root {
      --bg1: #f7f9ef;
      --bg2: #eef5ff;
      --ink: #1f2a37;
      --brand: #0f766e;
      --brand-2: #f59e0b;
      --line: #dbe4ee;
      --card: rgba(255,255,255,0.82);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: "Avenir Next", "Segoe UI", "PingFang SC", sans-serif;
      color: var(--ink);
      background:
        radial-gradient(circle at 10% 15%, rgba(15,118,110,.12), transparent 30%),
        radial-gradient(circle at 90% 85%, rgba(245,158,11,.14), transparent 35%),
        linear-gradient(125deg, var(--bg1), var(--bg2));
      min-height: 100vh;
      padding: 28px 16px;
    }
    .wrap { max-width: 980px; margin: 0 auto; }
    .hero {
      border: 1px solid var(--line);
      background: var(--card);
      backdrop-filter: blur(4px);
      border-radius: 18px;
      padding: 20px 22px;
      margin-bottom: 16px;
    }
    h1 { margin: 0 0 8px; font-size: 28px; }
    p { margin: 0; line-height: 1.5; }
    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
      gap: 12px;
      margin-top: 16px;
    }
    .card {
      border: 1px solid var(--line);
      border-radius: 14px;
      background: var(--card);
      padding: 14px;
    }
    label { display: block; font-size: 13px; margin-bottom: 6px; color: #334155; }
    input[type="text"], input[type="number"], input[type="file"] {
      width: 100%;
      border: 1px solid #c9d6e3;
      border-radius: 10px;
      padding: 10px;
      font-size: 14px;
      background: #fff;
    }
    .btn {
      margin-top: 14px;
      appearance: none;
      border: 0;
      border-radius: 12px;
      padding: 11px 18px;
      background: linear-gradient(92deg, var(--brand), #2563eb);
      color: #fff;
      font-weight: 650;
      cursor: pointer;
    }
    .btn:hover { filter: brightness(1.05); }
    .ok, .err {
      margin-top: 14px;
      border-radius: 12px;
      padding: 10px 12px;
      font-size: 13px;
      white-space: pre-wrap;
    }
    .ok { background: #ecfdf5; border: 1px solid #86efac; }
    .err { background: #fef2f2; border: 1px solid #fca5a5; }
    table {
      width: 100%;
      border-collapse: collapse;
      margin-top: 10px;
      font-size: 13px;
    }
    th, td {
      border-bottom: 1px solid var(--line);
      text-align: left;
      padding: 8px 6px;
      vertical-align: top;
    }
    th { color: #334155; }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="hero">
      <h1>剪映节拍自动切分应用</h1>
      <p>可上传多条视频或多条音频。视频按镜头切分完整放轨；音频会按每拍切分。</p>
    </div>

    <form class="card" method="post" enctype="multipart/form-data">
      <div class="grid">
        <div>
          <label>视频素材（可多选）</label>
          <input name="videos" type="file" multiple>
        </div>
        <div>
          <label>配乐音频（可多选）</label>
          <input name="audios" type="file" multiple>
        </div>
        <div>
          <label>项目名前缀</label>
          <input name="project_prefix" type="text" value="BeatAutoCutApp">
        </div>
        <div>
          <label>最小片段时长（毫秒）</label>
          <input name="min_interval_ms" type="number" value="50" min="1" step="1">
        </div>
        <div>
          <label>草稿目录（可选）</label>
          <input name="drafts_root" type="text" placeholder="不填则使用剪映默认草稿目录">
        </div>
      </div>
      <button class="btn" type="submit">开始批量生成</button>
    </form>

    {% if message %}
      <div class="ok">{{ message }}</div>
    {% endif %}

    {% if error %}
      <div class="err">{{ error }}</div>
    {% endif %}

    {% if reports %}
      <div class="card" style="margin-top:14px;">
        <h3 style="margin:0 0 8px;">处理结果</h3>
        <table>
          <thead>
            <tr>
              <th>项目名</th>
              <th>音频</th>
              <th>节拍数</th>
              <th>视频片段</th>
              <th>草稿路径</th>
            </tr>
          </thead>
          <tbody>
          {% for r in reports %}
            <tr>
              <td>{{ r.get("project_name") }}</td>
              <td>{{ r.get("bgm_path") }}</td>
              <td>{{ r.get("beat_count") }}</td>
              <td>{{ r.get("video_segment_count") }}</td>
              <td>{{ r.get("draft_path") }}</td>
            </tr>
          {% endfor %}
          </tbody>
        </table>
      </div>
    {% endif %}
  </div>
</body>
</html>
"""


def _save_files(files, target_dir: Path, allowed_exts: set[str]) -> list[Path]:
    target_dir.mkdir(parents=True, exist_ok=True)
    saved: list[Path] = []
    for storage in files:
        if not storage or not storage.filename:
            continue
        filename = secure_filename(storage.filename)
        if not filename:
            continue
        ext = Path(filename).suffix.lower()
        if ext not in allowed_exts:
            continue
        dest = target_dir / filename
        counter = 1
        while dest.exists():
            dest = target_dir / f"{dest.stem}_{counter}{dest.suffix}"
            counter += 1
        storage.save(dest)
        saved.append(dest.resolve())
    return saved


@app.route("/", methods=["GET", "POST"])
def index():
    reports = []
    error = ""
    message = ""

    if request.method == "POST":
        try:
            now = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
            job_id = f"job_{now}"
            job_root = UPLOAD_ROOT / job_id
            report_root = REPORT_ROOT / job_id

            videos = _save_files(
                request.files.getlist("videos"), job_root / "videos", VIDEO_EXTENSIONS
            )
            audios = _save_files(
                request.files.getlist("audios"), job_root / "audios", AUDIO_EXTENSIONS
            )
            if not videos and not audios:
                raise ValueError(
                    "没有可用素材文件，请至少上传视频或音频中的一种。"
                )

            project_prefix = request.form.get("project_prefix", "BeatAutoCutApp").strip() or "BeatAutoCutApp"
            min_interval_ms = float(request.form.get("min_interval_ms", "50") or 50.0)
            drafts_root = request.form.get("drafts_root", "").strip() or None

            reports = run_batch(
                bgm_paths=audios,
                video_paths=videos,
                project_name_prefix=project_prefix,
                drafts_root=drafts_root,
                min_interval_ms=min_interval_ms,
                report_dir=str(report_root),
            )
            message = f"完成：共生成 {len(reports)} 个草稿。上传目录：{job_root}"
        except Exception as exc:
            error = f"{exc}\n\n{traceback.format_exc()}"

    return render_template_string(PAGE, reports=reports, error=error, message=message)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
