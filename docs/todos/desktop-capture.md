# TODO：桌面小块采集

依据：[桌面小块采集：可行性与检测面](../desktop-capture-evaluation.md)

- [x] `grab_region` 只走小块 mss，复用长寿命 mss（不再 `_grab_from_game_window`）
- [x] 搜索漏斗：搜前藏预览（高度不变）→ 邻域 → 逐屏底带 30% → 同屏上半 70%（上次屏优先）；按屏 DPI 短名单；不用 `monitors[0]`
- [x] Locator 保留 `last_rect` / 上次屏索引跨重新定位
- [x] 删除 `window_capture` 的 `CreateForWindow` 路径，以及运行时按标题找「冒险岛」的 `EnumWindows`
- [x] 双屏实机验收（屏1/屏2 锁定、邻域重锁、预览不误匹配）
