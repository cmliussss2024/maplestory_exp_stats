# TODO：桌面小块采集

依据：[桌面小块采集：可行性与检测面](../desktop-capture-evaluation.md)

- [ ] `grab_region` 只走小块 mss，去掉每秒整窗（不再 `_grab_from_game_window`）
- [ ] 搜索改整张虚拟桌面匹配，排除本工具窗口矩形
- [ ] 删除 `window_capture` 的 `CreateForWindow` 路径，以及按标题找「冒险岛」的 `EnumWindows`
