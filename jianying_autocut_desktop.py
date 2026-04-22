from __future__ import annotations

import datetime as dt
import threading
import traceback
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from jianying_beat_autocut import (
    AUDIO_EXTENSIONS,
    VIDEO_EXTENSIONS,
    DEFAULT_SHOT_DETAIL_LEVEL,
    match_shot_detail_level_for_settings,
    resolve_shot_detail_settings,
    run_batch,
)


APP_DIR = Path(__file__).resolve().parent
REPORT_ROOT = APP_DIR / "reports"
REPORT_ROOT.mkdir(parents=True, exist_ok=True)

SHOT_DETAIL_LEVEL_TO_LABEL = {
    "coarse": "粗剪",
    "medium": "中度",
    "fine": "精细",
    "custom": "自定义",
}
SHOT_DETAIL_LABEL_TO_LEVEL = {label: level for level, label in SHOT_DETAIL_LEVEL_TO_LABEL.items()}


class AutoCutDesktopApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("剪映自动切分（桌面版）")
        self.root.geometry("1020x720")
        self.root.minsize(920, 640)

        self.video_paths: list[Path] = []
        self.audio_paths: list[Path] = []
        self.running = False
        self._syncing_shot_detail = False

        default_shot_settings = resolve_shot_detail_settings(DEFAULT_SHOT_DETAIL_LEVEL)

        self.project_prefix_var = tk.StringVar(value="BeatAutoCutApp")
        self.min_interval_var = tk.StringVar(value="50")
        self.shot_detail_level_var = tk.StringVar(value=SHOT_DETAIL_LEVEL_TO_LABEL[DEFAULT_SHOT_DETAIL_LEVEL])
        self.shot_threshold_var = tk.StringVar(value=self._format_float(default_shot_settings["shot_scene_threshold"]))
        self.shot_min_sec_var = tk.StringVar(value=self._format_float(default_shot_settings["shot_min_sec"]))
        self.shot_fps_var = tk.StringVar(value=self._format_float(default_shot_settings["shot_analysis_fps"]))
        self.shot_max_sec_var = tk.StringVar(value=self._format_float(default_shot_settings["shot_max_sec"]))
        self.drafts_root_var = tk.StringVar(value="")

        self._build_ui()
        self._bind_shot_setting_watchers()

    def _build_ui(self) -> None:
        style = ttk.Style()
        style.theme_use("clam")

        top = ttk.Frame(self.root, padding=12)
        top.pack(fill="both", expand=True)
        top.columnconfigure(0, weight=1)
        top.columnconfigure(1, weight=1)
        top.rowconfigure(2, weight=1)
        top.rowconfigure(5, weight=1)

        title = ttk.Label(top, text="剪映自动切分（桌面版）", font=("Microsoft YaHei UI", 16, "bold"))
        title.grid(row=0, column=0, columnspan=2, sticky="w")

        desc = ttk.Label(
            top,
            text="支持多条视频和音频。视频按真实镜头切分并完整放轨，音频按节拍切分。",
            font=("Microsoft YaHei UI", 10),
        )
        desc.grid(row=1, column=0, columnspan=2, sticky="w", pady=(2, 10))

        media_frame = ttk.Frame(top)
        media_frame.grid(row=2, column=0, columnspan=2, sticky="nsew")
        media_frame.columnconfigure(0, weight=1)
        media_frame.columnconfigure(1, weight=1)
        media_frame.rowconfigure(1, weight=1)

        ttk.Label(media_frame, text="视频素材").grid(row=0, column=0, sticky="w")
        ttk.Label(media_frame, text="音频素材").grid(row=0, column=1, sticky="w")

        video_box = ttk.Frame(media_frame)
        video_box.grid(row=1, column=0, sticky="nsew", padx=(0, 8))
        video_box.rowconfigure(0, weight=1)
        video_box.columnconfigure(0, weight=1)

        audio_box = ttk.Frame(media_frame)
        audio_box.grid(row=1, column=1, sticky="nsew", padx=(8, 0))
        audio_box.rowconfigure(0, weight=1)
        audio_box.columnconfigure(0, weight=1)

        self.video_list = tk.Listbox(video_box, selectmode=tk.EXTENDED, height=14)
        self.video_list.grid(row=0, column=0, sticky="nsew")
        ttk.Button(video_box, text="添加视频", command=self.add_videos).grid(row=1, column=0, sticky="ew", pady=(6, 0))
        ttk.Button(video_box, text="移除选中", command=self.remove_selected_videos).grid(
            row=2, column=0, sticky="ew", pady=(6, 0)
        )
        ttk.Button(video_box, text="清空视频", command=self.clear_videos).grid(row=3, column=0, sticky="ew", pady=(6, 0))

        self.audio_list = tk.Listbox(audio_box, selectmode=tk.EXTENDED, height=14)
        self.audio_list.grid(row=0, column=0, sticky="nsew")
        ttk.Button(audio_box, text="添加音频", command=self.add_audios).grid(row=1, column=0, sticky="ew", pady=(6, 0))
        ttk.Button(audio_box, text="移除选中", command=self.remove_selected_audios).grid(
            row=2, column=0, sticky="ew", pady=(6, 0)
        )
        ttk.Button(audio_box, text="清空音频", command=self.clear_audios).grid(row=3, column=0, sticky="ew", pady=(6, 0))

        options = ttk.Frame(top, padding=(0, 10, 0, 0))
        options.grid(row=3, column=0, columnspan=2, sticky="ew")
        options.columnconfigure(1, weight=1)
        options.columnconfigure(3, weight=1)

        ttk.Label(options, text="项目前缀").grid(row=0, column=0, sticky="w")
        ttk.Entry(options, textvariable=self.project_prefix_var).grid(row=0, column=1, sticky="ew", padx=(8, 12))

        ttk.Label(options, text="最小节拍间隔(ms)").grid(row=0, column=2, sticky="w")
        ttk.Entry(options, width=12, textvariable=self.min_interval_var).grid(row=0, column=3, sticky="ew", padx=(8, 0))

        ttk.Label(options, text="切分精细度").grid(row=1, column=0, sticky="w", pady=(8, 0))
        self.shot_detail_combo = ttk.Combobox(
            options,
            textvariable=self.shot_detail_level_var,
            values=[SHOT_DETAIL_LEVEL_TO_LABEL[level] for level in ("coarse", "medium", "fine", "custom")],
            state="readonly",
            width=12,
        )
        self.shot_detail_combo.grid(row=1, column=1, sticky="w", padx=(8, 12), pady=(8, 0))
        self.shot_detail_combo.bind("<<ComboboxSelected>>", self._on_shot_detail_selected)

        ttk.Label(options, text="镜头阈值").grid(row=1, column=2, sticky="w", pady=(8, 0))
        ttk.Entry(options, width=12, textvariable=self.shot_threshold_var).grid(
            row=1, column=3, sticky="w", padx=(8, 0), pady=(8, 0)
        )

        ttk.Label(options, text="最短镜头(s)").grid(row=2, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(options, width=12, textvariable=self.shot_min_sec_var).grid(
            row=2, column=1, sticky="w", padx=(8, 12), pady=(8, 0)
        )

        ttk.Label(options, text="分析FPS").grid(row=2, column=2, sticky="w", pady=(8, 0))
        ttk.Entry(options, width=12, textvariable=self.shot_fps_var).grid(
            row=2, column=3, sticky="w", padx=(8, 0), pady=(8, 0)
        )

        ttk.Label(options, text="最大镜头(s,0关闭)").grid(row=3, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(options, width=12, textvariable=self.shot_max_sec_var).grid(
            row=3, column=1, sticky="w", padx=(8, 12), pady=(8, 0)
        )

        ttk.Label(options, text="草稿目录(可选)").grid(row=3, column=2, sticky="w", pady=(8, 0))
        ttk.Entry(options, textvariable=self.drafts_root_var).grid(
            row=3, column=3, sticky="ew", padx=(8, 0), pady=(8, 0)
        )

        preset_hint = ttk.Label(
            options,
            text="提示：选择粗剪/中度/精细会自动带出参数，手动修改参数会切换为“自定义”。",
            font=("Microsoft YaHei UI", 9),
        )
        preset_hint.grid(row=4, column=0, columnspan=4, sticky="w", pady=(8, 0))

        action_bar = ttk.Frame(top, padding=(0, 10, 0, 0))
        action_bar.grid(row=4, column=0, columnspan=2, sticky="ew")
        self.run_button = ttk.Button(action_bar, text="开始批量生成草稿", command=self.start_run)
        self.run_button.pack(side="left")

        self.status_var = tk.StringVar(value="就绪")
        ttk.Label(action_bar, textvariable=self.status_var).pack(side="left", padx=12)

        log_frame = ttk.Frame(top, padding=(0, 8, 0, 0))
        log_frame.grid(row=5, column=0, columnspan=2, sticky="nsew")
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        self.log_text = tk.Text(log_frame, height=10, wrap="word")
        self.log_text.grid(row=0, column=0, sticky="nsew")

    def _bind_shot_setting_watchers(self) -> None:
        for var in (
            self.shot_threshold_var,
            self.shot_min_sec_var,
            self.shot_fps_var,
            self.shot_max_sec_var,
        ):
            var.trace_add("write", self._on_shot_settings_changed)

    @staticmethod
    def _format_float(value: float) -> str:
        return format(float(value), "g")

    def _collect_shot_settings(self) -> dict[str, float]:
        return {
            "shot_scene_threshold": float(self.shot_threshold_var.get().strip() or "0"),
            "shot_min_sec": float(self.shot_min_sec_var.get().strip() or "0"),
            "shot_analysis_fps": float(self.shot_fps_var.get().strip() or "0"),
            "shot_max_sec": float(self.shot_max_sec_var.get().strip() or "0"),
        }

    def _set_shot_detail_label(self, level: str) -> None:
        self._syncing_shot_detail = True
        try:
            self.shot_detail_level_var.set(SHOT_DETAIL_LEVEL_TO_LABEL[level])
        finally:
            self._syncing_shot_detail = False

    def _apply_shot_detail_level(self, level: str) -> None:
        if level == "custom":
            self._set_shot_detail_label("custom")
            return

        settings = resolve_shot_detail_settings(level)
        self._syncing_shot_detail = True
        try:
            self.shot_detail_level_var.set(SHOT_DETAIL_LEVEL_TO_LABEL[level])
            self.shot_threshold_var.set(self._format_float(settings["shot_scene_threshold"]))
            self.shot_min_sec_var.set(self._format_float(settings["shot_min_sec"]))
            self.shot_fps_var.set(self._format_float(settings["shot_analysis_fps"]))
            self.shot_max_sec_var.set(self._format_float(settings["shot_max_sec"]))
        finally:
            self._syncing_shot_detail = False

    def _on_shot_detail_selected(self, _event=None) -> None:
        if self._syncing_shot_detail:
            return
        level = SHOT_DETAIL_LABEL_TO_LEVEL.get(self.shot_detail_level_var.get(), "custom")
        self._apply_shot_detail_level(level)

    def _on_shot_settings_changed(self, *_args) -> None:
        if self._syncing_shot_detail:
            return
        try:
            current_settings = self._collect_shot_settings()
        except ValueError:
            self._set_shot_detail_label("custom")
            return

        matched_level = match_shot_detail_level_for_settings(current_settings)
        self._set_shot_detail_label(matched_level)

    def add_videos(self) -> None:
        paths = filedialog.askopenfilenames(
            title="选择视频文件",
            filetypes=[("Video Files", " ".join(f"*{e}" for e in sorted(VIDEO_EXTENSIONS))), ("All Files", "*.*")],
        )
        self.video_paths = self._merge_paths(self.video_paths, [Path(p) for p in paths])
        self._refresh_list(self.video_list, self.video_paths)

    def add_audios(self) -> None:
        paths = filedialog.askopenfilenames(
            title="选择音频文件",
            filetypes=[("Audio Files", " ".join(f"*{e}" for e in sorted(AUDIO_EXTENSIONS))), ("All Files", "*.*")],
        )
        self.audio_paths = self._merge_paths(self.audio_paths, [Path(p) for p in paths])
        self._refresh_list(self.audio_list, self.audio_paths)

    def remove_selected_videos(self) -> None:
        indexes = set(self.video_list.curselection())
        self.video_paths = [p for i, p in enumerate(self.video_paths) if i not in indexes]
        self._refresh_list(self.video_list, self.video_paths)

    def remove_selected_audios(self) -> None:
        indexes = set(self.audio_list.curselection())
        self.audio_paths = [p for i, p in enumerate(self.audio_paths) if i not in indexes]
        self._refresh_list(self.audio_list, self.audio_paths)

    def clear_videos(self) -> None:
        self.video_paths = []
        self._refresh_list(self.video_list, self.video_paths)

    def clear_audios(self) -> None:
        self.audio_paths = []
        self._refresh_list(self.audio_list, self.audio_paths)

    def start_run(self) -> None:
        if self.running:
            return
        if not self.video_paths and not self.audio_paths:
            messagebox.showerror("缺少素材", "请至少添加视频或音频中的一种素材。")
            return

        try:
            min_interval_ms = float(self.min_interval_var.get().strip() or "50")
            if min_interval_ms <= 0:
                raise ValueError("最小节拍间隔必须大于 0")
            shot_settings = self._collect_shot_settings()
            shot_threshold = shot_settings["shot_scene_threshold"]
            shot_min_sec = shot_settings["shot_min_sec"]
            shot_fps = shot_settings["shot_analysis_fps"]
            shot_max_sec = shot_settings["shot_max_sec"]
            if not (0 < shot_threshold < 1):
                raise ValueError("镜头阈值必须在 0 到 1 之间")
            if shot_min_sec <= 0 or shot_fps <= 0 or shot_max_sec < 0:
                raise ValueError("最短镜头和分析FPS必须大于 0，最大镜头需大于等于 0")
        except Exception:
            messagebox.showerror(
                "参数错误",
                "请检查参数：最小节拍间隔>0，镜头阈值在(0,1)，最短镜头/分析FPS>0，最大镜头>=0。",
            )
            return

        self.running = True
        self.run_button.state(["disabled"])
        self.status_var.set("处理中...")
        self._append_log("开始处理任务。")

        worker = threading.Thread(target=self._run_worker, daemon=True)
        worker.start()

    def _run_worker(self) -> None:
        try:
            prefix = self.project_prefix_var.get().strip() or "BeatAutoCutApp"
            drafts_root = self.drafts_root_var.get().strip() or None
            min_interval_ms = float(self.min_interval_var.get().strip() or "50")
            shot_settings = self._collect_shot_settings()
            shot_detail_level = SHOT_DETAIL_LABEL_TO_LEVEL.get(self.shot_detail_level_var.get(), "custom")
            now = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
            report_dir = REPORT_ROOT / f"desktop_{now}"

            def progress(event: dict) -> None:
                if event.get("event") == "start":
                    self._ui(self._append_log, f"[{event['index']}/{event['total']}] 开始：{event['project_name']}")
                elif event.get("event") == "done":
                    report = event.get("report", {})
                    self._ui(
                        self._append_log,
                        f"[{event['index']}/{event['total']}] 完成：{report.get('project_name')} -> {report.get('draft_path')}",
                    )

            reports = run_batch(
                bgm_paths=self.audio_paths,
                video_paths=self.video_paths,
                project_name_prefix=prefix,
                drafts_root=drafts_root,
                shot_detail_level=shot_detail_level,
                shot_scene_threshold=shot_settings["shot_scene_threshold"],
                shot_min_sec=shot_settings["shot_min_sec"],
                shot_analysis_fps=shot_settings["shot_analysis_fps"],
                shot_max_sec=shot_settings["shot_max_sec"],
                min_interval_ms=min_interval_ms,
                report_dir=str(report_dir),
                progress_hook=progress,
            )
            self._ui(self._append_log, f"全部完成，共生成 {len(reports)} 个草稿。报告目录：{report_dir}")
            self._ui(self.status_var.set, "完成")
        except Exception:
            self._ui(self._append_log, "处理失败：\n" + traceback.format_exc())
            self._ui(self.status_var.set, "失败")
        finally:
            self._ui(self._set_idle)

    def _set_idle(self) -> None:
        self.running = False
        self.run_button.state(["!disabled"])

    def _append_log(self, text: str) -> None:
        stamp = dt.datetime.now().strftime("%H:%M:%S")
        self.log_text.insert("end", f"[{stamp}] {text}\n")
        self.log_text.see("end")

    def _ui(self, func, *args) -> None:
        self.root.after(0, lambda: func(*args))

    @staticmethod
    def _merge_paths(old: list[Path], new: list[Path]) -> list[Path]:
        seen = {str(p.resolve()).lower() for p in old}
        result = list(old)
        for p in new:
            rp = p.resolve()
            key = str(rp).lower()
            if key not in seen and rp.exists() and rp.is_file():
                seen.add(key)
                result.append(rp)
        return result

    @staticmethod
    def _refresh_list(listbox: tk.Listbox, paths: list[Path]) -> None:
        listbox.delete(0, "end")
        for p in paths:
            listbox.insert("end", str(p))


def main() -> None:
    root = tk.Tk()
    AutoCutDesktopApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
