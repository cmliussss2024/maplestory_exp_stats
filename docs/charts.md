# 走势图

本文档是走势图的唯一规格。改点数、窗口、取值规则、数据源或文案时，先改本文档，再把 `rate_tracker.CHARTS` 与绘制代码同步。不要在代码里另写一套图表语义。

两张图同时显示，无切换页。每秒刷新（现有 `_ui_tick` 1s）。数据源按图分别来自「效率」或「累计」列，见下表 `source`。OCR 读数同时写入两列：收益是内存里的这一波（可单独重置，1 分钟无增长自动清），累计写入 `exp_history.jsonl`。重置累计会连收益一起清；重置收益不影响累计。

## 采样

图有固定点数 `count`、步长 `step` 秒。第 `i` 点（从 0）对应时刻：

```
t[i] = now - (count - 1 - i) * step
```

左端 `t[0] = now - (count-1)*step`，右端 `t[count-1] = now`。序列长度永远是 `count`，不因开刷时间缩短。

窗口开始之前没有收益的点填 **0**（左补 0）。

`gains` 是对应 tracker 自检后的 `(时间, 该次收益)`。该 tracker 的累计经验在时刻 `t` 等于所有 `时间 <= t` 的收益之和。

`source`：`current` 为「效率」列（`self.current`），`session` 为「累计」列（`self.session`）。

## 效率

| 项 | 值 |
| --- | --- |
| `title` | 效率 |
| `count` | 300 |
| `step` | 1 |
| `axis_start` | 5分钟前 |
| `suffix` | /秒 |
| `mode` | `per_sec_rate` |
| `source` | `current`（效率） |

点值：该时刻效率列的「/秒」，即从这波开刷到 `t[i]` 的平均秒收益：

```
elapsed = t[i] - first_gain_at
若已会话重启且 t[i] >= resumed_at：elapsed -= paused
点值 = round(这波经验(t[i]) / max(elapsed, 1))
```

`paused` 是进程退出到再次打开的离线空隙，只从 `resumed_at`（重启时刻）起扣。更早的采样点不扣：那一时刻这段空隙还没发生；若提前扣，重启后左半段曲线会变成 0。右端点在重启之后，与即时「/秒」一样扣 `paused`。

`t[i]` 不晚于首次收益、或这波经验为 0、或 `elapsed <= 0` 时为 0。

这是近 5 分钟里效率怎么变，不是那一秒打到的经验。休息时这波经验不变、时间在走，曲线会往下掉。例：刚才 100/秒，休息 1 分钟后降到 95/秒，这一分钟是下降段。右端点与即时「/秒」一致。重置效率或空闲重置后，图跟效率一起归零，累计不动。

## 累计经验

| 项 | 值 |
| --- | --- |
| `title` | 累计经验 |
| `count` | 60 |
| `step` | 60 |
| `axis_start` | 1小时前 |
| `suffix` | （空） |
| `mode` | `cumulative` |
| `source` | `session`（累计） |

点值：该分钟采样时刻的累计经验，即所有 `时间 <= t[i]` 的收益之和。开刷之前的点为 0。

这是累计曲线在最近一小时的切片，不是这一小时从 0 重算的增量，也不是每分钟的增量。

例：1 小时前累计经验 50000，现在 150000 → 左端约为 50000（窗口左端时刻的累计），右端为 150000。满窗时左端不是 0。

## 代码对照

- 常量：`rate_tracker.CHARTS`（字段与上表一致，含 `source`）
- 序列：`RateTracker.chart_series(now, spec)`，tracker 由 `spec.source` 选择
- 绘制：`app.ExpRateApp._redraw_chart` 用 `current` / `session` 对应 `CHARTS`
- 标题：`ChartSectionPanel` 从 `CHARTS` 取值
