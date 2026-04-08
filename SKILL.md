---
name: travel
description: 智能旅行助手，根据实时天气推荐旅游景点
---

# 旅行助手 Skill

根据用户指定的城市，查询实时天气并推荐合适的旅游景点。

## 依赖

```
pip install openai requests tavily-python
```

## 环境变量

运行前请设置以下环境变量：

| 变量名 | 说明 |
|---|---|
| `OPENAI_API_KEY` | OpenAI 兼容接口的 API Key |
| `OPENAI_BASE_URL` | OpenAI 兼容接口的 Base URL |
| `MODEL_ID` | 模型 ID |
| `TAVILY_API_KEY` | Tavily 搜索 API Key |

## 运行

```bash
cd /Users/bo/.openclaw/skills/travel/scripts
python entry.py
```

## 可用工具

- `get_weather(city)` — 查询指定城市的实时天气（via wttr.in）
- `get_attraction(city, weather)` — 根据城市和天气搜索推荐的旅游景点（via Tavily）