# mouse-jiggler

定時讓滑鼠做極小位移再移回，可用 GUI 設定間隔（分鐘）。僅供個人合法用途（例如避免簡報或閱讀時螢幕休眠），請遵守公司與服務條款。

## 環境需求

- **Windows**（使用 Win32 API 移動游標）
- **Python** 3.10 或以上
- 建議使用 **[uv](https://docs.astral.sh/uv/)** 管理環境與執行

## 安裝與執行

在專案根目錄：

```powershell
uv sync
uv run mouse-jiggler
```

或使用模組方式：

```powershell
uv run python -m mouse_jiggler
```

## 使用方式

1. 在「間隔（分鐘）」輸入數字（可為小數，例如 `0.5` 表示約 30 秒；最小 **0.1** 分鐘）。
2. 按 **開始** 啟動定時微動；**停止** 可結束。
3. 關閉視窗會一併停止背景執行。

## 技術說明

- GUI：**tkinter**（Python 標準庫）
- 滑鼠：**ctypes** 呼叫 `user32.GetCursorPos` / `SetCursorPos`
- 無額外 PyPI 依賴

## 限制與注意

- 螢幕鎖定或部分遠端桌面環境下，行為可能與本機不同。
- 請勿用於規避應有的安全、監控或合規要求。
