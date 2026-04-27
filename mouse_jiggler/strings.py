"""UI copy for zh / en."""

from __future__ import annotations

from typing import Literal

Lang = Literal["zh", "en"]

STRINGS: dict[Lang, dict[str, str]] = {
    "zh": {
        "window_title": "滑鼠定時微動",
        "app_subtitle": "滑鼠定時微動",
        "seg_control": "控制面板",
        "seg_log": "紀錄",
        "theme_hint": "深灰色主題",
        "lang_ui": "介面語言",
        "dashboard": "主控台",
        "interval_label": "間隔",
        "interval_unit_min": "分鐘",
        "interval_unit_sec": "秒",
        "interval_hint_min": "≥ 0.1，可小數",
        "interval_hint_sec": "≥ 6，可小數",
        "pixels_label": "位移（像素）",
        "pixels_hint": "水平再還原 · {lo}–{hi}",
        "motion_burst_label": "持續微動（秒）",
        "motion_burst_hint": "每輪間隔到期後再微動多久；0 = 只微動一次 · 0–{hi:g}",
        "status_motion_burst": "狀態：執行中 · 持續微動 · 約 {cd}",
        "log_motion_burst_start": "開始持續微動約 {sec:g} 秒（至下一輪等待前）。",
        "log_start_fail_motion": "開始失敗：持續微動秒數無效。",
        "err_motion_burst": "請輸入有效的秒數（數字，0–{hi:g}）。",
        "btn_start": "開始",
        "btn_stop": "停止",
        "tray_checkbox": "關閉視窗時縮到系統匣（排程繼續）",
        "tray_switch_title": "關閉視窗時縮到系統匣",
        "tray_switch_hint": "啟用後關閉視窗將保留排程並在背景執行，可從系統匣圖示還原視窗。",
        "tray_no_pystray": "（未安裝 pystray）",
        "status_stopped": "狀態：已停止",
        "status_running_min": "狀態：執行中 · 每 {v:g} 分鐘 · 下次約 {cd}",
        "status_running_sec": "狀態：執行中 · 每 {v:g} 秒 · 下次約 {cd}",
        "log_title": "活動紀錄",
        "log_ready": "程式已就緒。",
        "log_start_fail_interval": "開始失敗：間隔設定無效。",
        "log_start_fail_pixels": "開始失敗：位移設定無效。",
        "log_started_min": "已開始，間隔 {v:g} 分鐘（約 {sec:.0f} 秒）、位移 {px} px{extra}。",
        "log_started_sec": "已開始，間隔 {v:g} 秒、位移 {px} px{extra}。",
        "log_started_motion_extra": "，每輪後持續微動 {mb:g} 秒",
        "log_stopped": "已手動停止。",
        "log_nudge": "已執行游標微動。",
        "log_nudge_zero": "已觸發排程（位移 0，未移動游標）。",
        "log_nudge_fail": "微動失敗：{err}",
        "log_exit": "結束程式。",
        "log_tray_minimize": "已縮至系統匣（排程仍執行，可從圖示還原或結束）。",
        "err_title": "輸入錯誤",
        "err_minutes": "請輸入有效的分鐘數（數字，且 ≥ {min}）。",
        "err_seconds": "請輸入有效的秒數（數字，且 ≥ {min}）。",
        "err_pixels": "請輸入有效的位移像素（整數，{lo}–{hi}）。",
        "tray_show": "顯示主視窗",
        "tray_quit": "結束程式",
        "nav_home": "首頁",
        "nav_settings": "設定",
        "nav_analytics": "分析",
        "settings_title": "設定",
        "analytics_title": "分析",
        "analytics_subtitle": "與首頁「紀錄」同步的活動紀錄。",
        "intro_title": "歡迎使用",
        "intro_body": "try-working-hard {version}\n\n"
        "本程式會依您設定的間隔，微量水平移動游標再還原，可用於簡報或閱讀時避免螢幕休眠。\n\n"
        "請僅在合法、符合公司／學校規定與服務條款的前提下使用；勿用於規避安全或監控機制。\n\n"
        "按 F1 可開啟鍵盤與無障礙說明。您的偏好設定會儲存在本機，下次開啟時自動載入。\n\n"
        "點選「確定」後不會再顯示本視窗（除非刪除設定檔）。",
        "a11y_help_title": "鍵盤與無障礙說明",
        "a11y_help_body": "try-working-hard {version}\n\n"
        "鍵盤：\n"
        "· F1 本說明\n"
        "· F2 / F3 / F4 首頁、設定、分析\n"
        "· F5 開始（首頁「控制面板」且可開始時）\n"
        "· Shift+F5 停止\n"
        "· F6 首頁切換「控制面板」/「紀錄」\n\n"
        "可點擊「間隔」「位移」或「持續微動」標籤，將焦點移到該欄位。間隔可選「分鐘」或「秒」。\n\n"
        "注意：CustomTkinter 多數控制項以畫布繪製，部分螢幕閱讀器可能無法宣讀所有元件。視窗標題與本對話框採用系統標準外觀。",
    },
    "en": {
        "window_title": "Mouse nudge",
        "app_subtitle": "Mouse nudge",
        "seg_control": "Control",
        "seg_log": "Log",
        "theme_hint": "Dark gray theme",
        "lang_ui": "Language",
        "dashboard": "Dashboard",
        "interval_label": "Interval",
        "interval_unit_min": "min",
        "interval_unit_sec": "sec",
        "interval_hint_min": "≥ 0.1, decimals allowed",
        "interval_hint_sec": "≥ 6, decimals (same minimum as 0.1 min)",
        "pixels_label": "Nudge (pixels)",
        "pixels_hint": "Horizontal move & restore · {lo}–{hi}",
        "motion_burst_label": "Active motion (sec)",
        "motion_burst_hint": "Keep nudging this long after each interval; 0 = single nudge · 0–{hi:g}",
        "status_motion_burst": "Status: running · active motion · ~{cd} left",
        "log_motion_burst_start": "Active motion for ~{sec:g} s (until next idle wait).",
        "log_start_fail_motion": "Start failed: invalid active motion duration.",
        "err_motion_burst": "Enter a valid duration in seconds (number, 0–{hi:g}).",
        "btn_start": "Start",
        "btn_stop": "Stop",
        "tray_checkbox": "Close to system tray (schedule continues)",
        "tray_switch_title": "Minimize to system tray on close",
        "tray_switch_hint": "When enabled, closing the window keeps the schedule running; restore from the tray icon.",
        "tray_no_pystray": "(pystray not installed)",
        "status_stopped": "Status: stopped",
        "status_running_min": "Status: running · every {v:g} min · next in {cd}",
        "status_running_sec": "Status: running · every {v:g} s · next in {cd}",
        "log_title": "Activity log",
        "log_ready": "Ready.",
        "log_start_fail_interval": "Start failed: invalid interval.",
        "log_start_fail_pixels": "Start failed: invalid nudge size.",
        "log_started_min": "Started: every {v:g} min (~{sec:.0f} s), nudge {px} px{extra}.",
        "log_started_sec": "Started: every {v:g} s, nudge {px} px{extra}.",
        "log_started_motion_extra": ", active motion {mb:g} s after each tick",
        "log_stopped": "Stopped manually.",
        "log_nudge": "Cursor nudge executed.",
        "log_nudge_zero": "Tick fired (0 px — cursor not moved).",
        "log_nudge_fail": "Nudge failed: {err}",
        "log_exit": "Exiting.",
        "log_tray_minimize": "Minimized to tray (schedule still running).",
        "err_title": "Invalid input",
        "err_minutes": "Enter a valid interval in minutes (number, ≥ {min}).",
        "err_seconds": "Enter a valid interval in seconds (number, ≥ {min}).",
        "err_pixels": "Enter a valid nudge size (integer, {lo}–{hi}).",
        "tray_show": "Show window",
        "tray_quit": "Quit",
        "nav_home": "Home",
        "nav_settings": "Settings",
        "nav_analytics": "Analytics",
        "settings_title": "Settings",
        "analytics_title": "Analytics",
        "analytics_subtitle": "Activity log (synced with Home → Log).",
        "intro_title": "Welcome",
        "intro_body": "try-working-hard {version}\n\n"
        "This app nudges the cursor horizontally on a timer and restores it—useful to keep the screen awake while presenting or reading.\n\n"
        "Use it only in lawful ways that comply with employer, school, and service rules; do not use it to bypass security or monitoring.\n\n"
        "Press F1 for keyboard and accessibility help. Your preferences are saved locally and loaded next time.\n\n"
        "You will not see this dialog again after you click OK (unless you delete the config file).",
        "a11y_help_title": "Keyboard and accessibility",
        "a11y_help_body": "try-working-hard {version}\n\n"
        "Keyboard:\n"
        "· F1  this help\n"
        "· F2 / F3 / F4  Home, Settings, Analytics\n"
        "· F5  Start (Home → Control, when available)\n"
        "· Shift+F5  Stop\n"
        "· F6  Home: toggle Control / Log\n\n"
        "Click the Interval, Nudge (pixels), or Active motion label to move focus to that field. Choose min or sec for the interval unit.\n\n"
        "Note: CustomTkinter draws most controls on a canvas, so not every control is exposed to all screen readers. The window title and this dialog use standard toolkit UIs.\n"
        "Tab / Shift+Tab move focus; tooltips are not used for the canvas controls.",
    },
}
