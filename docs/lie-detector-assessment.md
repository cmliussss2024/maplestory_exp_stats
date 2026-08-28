# 测谎风险评估

对照：以前不开，从未测谎；今晚开本工具约 2 小时，测谎 2 次。源码：`window_capture.py`、`vision.py`、`app.py`、`ui/views/overlay_window.py`、`ui/layered.py`。

## 代码分析

本工具不读内存、不注入、不模拟键鼠。经验数字只来自像素。能被客户端看见的，是它为读经验条而持续接触游戏窗口的方式。

锁定后并不是「只截经验条那一小块」。WGC 会话抓整个客户区，裁切发生在本进程。

| 步骤 | 代码 | 频率 | 对游戏的接触 |
| --- | --- | --- | --- |
| 找窗 | `vision.find_game_window`：`EnumWindows` + 标题含「冒险岛」或 `maplestory` | 搜索中每 3s；锁定后不再枚举 | 只读窗口列表 |
| 开会话 | `window_capture._ensure_session`：`create_for_window(hwnd)` + `start_capture()`，并 `is_border_required = False` | 每个 HWND 一次，然后一直开着 | DWM 对该窗口注册采集会话 |
| 出帧 | `grab_hwnd` → `Direct3D11CaptureFramePool.try_get_next_frame` | 锁定后约 1s 一次（`LOCK_SCAN_MS = 1000`） | 整窗纹理拷到 CPU |
| 裁条 | `_grab_from_game_window` 按虚拟屏坐标切片 | 每次 tick | 本地裁切 |
| 识别 | `find_label` + RapidOCR + `pick_exp` | 每次 tick | 纯本地，无输入回写 |

`grab_region` 先走 `grab_hwnd` 整窗，失败才 mss 桌面截图。状态「监控中」时主路径是绑窗 WGC。

主窗 `attributes("-topmost", True)`。悬浮窗 `overrideredirect` + `WS_EX_LAYERED` + `UpdateLayeredWindow`（`ui/layered.py`）。

| 做法 | 评估 |
| --- | --- |
| `CreateForWindow` + 关采集黄框 + 持久会话 | 最强指纹。系统级「有进程在抓这个窗口」，和图色辅助同一入口。 |
| 锁定后约 1 Hz 整窗采集 | 会话一直开着，两小时约几千次出帧。 |
| 置顶分层 HUD | 像外挂皮肤；更常对应踢线/封号，不是测谎弹窗的典型路径。 |
| `EnumWindows` 找游戏 | 单独弱，和绑窗采集叠在一起才构成「这个进程在找冒险岛」。 |
| mss 回退 | 仅 WGC 失败时。 |
| OCR / 模板匹配 | 本进程算像素，游戏进程看不到。 |

没有：`OpenProcess` / `ReadProcessMemory`、DLL 注入、`SetWindowsHook`、`SendInput`。本工具不会答题。

## 总结

开本工具与测谎同时出现，以前未出现。无法看到服务端判定，只能从本仓库的采集方式评估。

若测谎与本进程有关，最吻合的是对游戏窗口的 Windows.Graphics.Capture 持久会话：`CreateForWindow`、关掉采集黄框、锁定后每秒整窗出帧。OCR 和统计不接触游戏进程。置顶 HUD 加重第三方外观，不是测谎主路径。
