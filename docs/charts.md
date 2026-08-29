# 走势图

本文档是走势图的唯一规格。改点数、窗口、取值规则或文案时，先改本文档，再把 `rate_tracker.CHARTS` 与 `chart_series` 同步到代码。不要在代码里另写一套图表语义。

数据源只有**累计**（`session` 的 `gains` / `total_gained`），不用预估列。

两张图同时显示，无切换页。每秒刷新（现有 `_ui_tick` 1s）。

## 采样

图有固定点数 `count`、步长 `step` 秒。第 `i` 点（从 0）对应时刻：

```
t[i] = now - (count - 1 - i) * step
```

左端 `t[0] = now - (count-1)*step`，右端 `t[count-1] = now`。序列长度永远是 `count`，不因开刷时间缩短。

窗口开始之前没有收益的点填 **0**（左补 0）。

`gains` 是自检后的 `(时间, 该次收益)`。累计经验在时刻 `t` 等于所有 `时间 <= t` 的收益之和。

## 5分钟内秒均收益

| 项 | 值 |
| --- | --- |
| `title` | 5分钟内秒均收益 |
| `count` | 300 |
| `step` | 1 |
| `axis_start` | 5分钟前 |
| `suffix` | /秒 |
| `mode` | `step_gain` |

点值：该秒的收益，即 `(t[i] - step, t[i]]` 内所有 `gains` 的 delta 之和。没有收益则为 0。

不是从开刷起算的「秒均速率」，也不是 5 分钟滚动平均。

## 1小时累计经验

| 项 | 值 |
| --- | --- |
| `title` | 1小时累计经验 |
| `count` | 60 |
| `step` | 60 |
| `axis_start` | 1小时前 |
| `suffix` | （空） |
| `mode` | `cumulative` |

点值：该分钟采样时刻的累计经验，即所有 `时间 <= t[i]` 的收益之和。开刷之前的点为 0。

这是累计曲线在最近一小时的切片，不是这一小时从 0 重算的增量，也不是每分钟的增量。

例：1 小时前累计经验 50000，现在 150000 → 左端约为 50000（窗口左端时刻的累计），右端为 150000。满窗时左端不是 0。

## 代码对照

- 常量：`rate_tracker.CHARTS`（字段与上表一致）
- 序列：`RateTracker.chart_series(now, spec)`
- 绘制：`app.ExpRateApp._redraw_chart` 用累计 tracker + `CHARTS[0]` / `CHARTS[1]`
- 标题：`ChartSectionPanel` 从 `CHARTS` 取值
