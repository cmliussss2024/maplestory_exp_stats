# 测谎风险评估

对照：以前不开，从未测谎；开本工具约 2 小时，测谎 2 次。那次对照时主路径仍是绑游戏 HWND 的 Windows Graphics Capture；现已改为桌面小块 mss，不再点名冒险岛窗口。源码：`vision.py`、`app.py`、`ui/views/overlay_window.py`、`ui/layered.py`。

## 代码分析

本工具不读内存、不注入、不模拟键鼠。经验数字只来自像素。

| 步骤 | 代码 | 频率 | 对游戏的接触 |
| --- | --- | --- | --- |
| 锁定采集 | `grab_region`：mss 只抓 `locked_rect` 小矩形 | 约 1s 一次 | 桌面合成小块 BitBlt，不绑 HWND |
| 丢锁搜索 | `search_exp_label`：邻域 → 逐屏底带 / 上半；搜前藏预览 | 约 3s 一次（仅丢锁 / 冷启动） | 仍是桌面小块，不按标题找窗 |
| 识别 | `find_label` + RapidOCR + `pick_exp` | 每次 tick | 纯本地，无输入回写 |

主窗 `attributes("-topmost", True)`。悬浮窗 `overrideredirect` + `WS_EX_LAYERED` + `UpdateLayeredWindow`（`ui/layered.py`）。

| 做法 | 评估 |
| --- | --- |
| 小块桌面 BitBlt | 通用截屏，不点名冒险岛进程；比旧 WGC 绑窗会话轻。 |
| 锁定后约 1 Hz 小矩形 | 只拷经验条量级像素，不是整窗纹理。 |
| 置顶分层 HUD | 像外挂皮肤；更常对应踢线/封号，不是测谎弹窗的典型路径。 |
| OCR / 模板匹配 | 本进程算像素，游戏进程看不到。 |

已去掉：`CreateForWindow`、持久 WGC 会话、按标题 `EnumWindows` 找「冒险岛」、整窗出帧。

没有：`OpenProcess` / `ReadProcessMemory`、DLL 注入、`SetWindowsHook`、`SendInput`。本工具不会答题。

## 总结

开本工具与测谎曾同时出现（当时仍是 WGC）。无法看到服务端判定。采集面已从「有进程在抓冒险岛 HWND」换成「偶尔拷桌面小块」；测谎是服务端判定，不能保证不再弹。置顶 HUD 仍加重第三方外观。

改采集前后的取舍见 [桌面小块采集：可行性与检测面](desktop-capture-evaluation.md)。
