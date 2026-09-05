## Why

当前主路径绑冒险岛 HWND 做 Graphics Capture，检测面重；已有评估要改成桌面小块 BitBlt。若搜索仍抓整张虚拟桌面外接矩形、盲目多尺度匹配，多屏下浪费大，且本工具预览里的 EXP 图会误匹配。需要在去掉绑窗采集的同时，用专业级漏斗把搜索成本压到「尽量少抓、少匹配」。

## What Changes

- 去掉绑游戏 HWND 的 WGC / 按标题找「冒险岛」；锁定后每秒只 mss 抓 `locked_rect` 小块。
- 定位 / 重新定位改为**逐屏**搜索（`mss.monitors[1..n]`），不用 `monitors[0]` 外接大图。
- 搜索漏斗：搜前隐藏自身预览（高度不变）→ 有上次矩形则先邻域匹配 → 按「上次命中屏优先」逐屏：先底部 HUD 带，未命中再搜该屏剩余上半（同屏回退）→ 再下一屏；按屏 DPI 选模板尺度；复用长寿命 `mss` 实例。冷启动不依赖窗口贴底。
- 同步更新 `docs/desktop-capture-evaluation.md` 与 `docs/todos/desktop-capture.md`，与上述行为一致。
- **BREAKING**（对采集面）：不再依赖游戏窗口句柄；被遮挡时读到的是遮挡物像素（评估已接受）。

## Capabilities

### New Capabilities

- `desktop-capture`: 桌面小块采集与多屏经验条搜索（锁定抓小块、逐屏漏斗搜索、预览隐藏、mss 复用；不再绑游戏 HWND）

### Modified Capabilities

- （无；`openspec/specs/` 尚无既有 capability）

## Impact

- 代码：`vision.py`（抓屏 / `find_label` / `capture_for_search`）、`locator.py`（保留上次矩形与上次屏）、`app.py`（搜前藏预览、接新搜索 API）、`window_capture.py`（删除或停用 `CreateForWindow` 路径）、相关测试与 `scripts/crop_exp_assets.py`。
- 文档：`docs/desktop-capture-evaluation.md`、`docs/todos/desktop-capture.md`；验收仍对照 `docs/display.md`（屏 1 @1.5×、屏 2 @1.0×）。
- 依赖：仍用 `mss` + OpenCV；不上 DXGI / GPU 匹配（检测面与收益不划算）。
