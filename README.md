# 在路上 · 骑跑双修

这是一个基于 Intervals.icu 数据的骑行/跑步年报页面，包含：

- 年度骑行距离、跑步距离
- 总运动时间
- 海拔累计
- 最近一次骑行/跑步
- 年度目标进度
- 运行状态信息
- 自动同步数据

## 目录结构

- `index.html`：前端页面
- `data.json`：自动生成的统计数据
- `icu2json.py`：同步 API 并生成 JSON
- `.github/workflows/sync-icu.yml`：自动同步动作

## 环境变量 / Secrets

在 GitHub 仓库中设置以下 Secrets：

- `ICU_API_KEY`
- `ICU_ATHLETE_ID`
- `OSS_KEY`
- `OSS_SECRET`
- `OSS_ENDPOINT`
- `OSS_BUCKET`

## 本地运行

```bash
pip install requests oss2
python icu2json.py
