# 配置化 Agent 与 Pipeline 使用指南

本文档面向开发者，介绍如何在 `forge-agent` 中：

1. 通过 YAML/JSON 配置生成 Agent（无需手写 Python 类）
2. 配置多源数据归一化
3. 组合成端到端 Pipeline 并运行
4. 添加新的专家 Agent
5. 测试与提交代码

---

## 1. 环境准备

```bash
cd /Users/popmart/Documents/python/forge-agent
source .venv/bin/activate
```

确认依赖已安装：

```bash
pip install -e ".[all]"
```

---

## 2. 快速跑通端到端 Pipeline

```bash
python -m examples.run_pipeline
```

预期输出包含：

```text
============================================================
End-to-End Sports Pipeline
============================================================

--- Member Reports ---
[赛事情报专家] verdict=lean_positive confidence=75% risk=20%
[比赛天气专家] verdict=lean_negative confidence=80% risk=40%
[历史交锋专家] verdict=lean_negative confidence=65% risk=25%
[赔率分析专家] verdict=lean_negative confidence=72% risk=35%
[情报搜索专家] verdict=lean_positive confidence=78% risk=25%
  [search] query='阿森纳 vs 利物浦 latest news injury lineup' backend=mock

--- Chief Briefing ---
verdict: lean_negative
confidence: 0.74
risk: 0.29
action: hold
```

完整配置在 `examples/configs/sports_pipeline.yaml`。

---

## 3. 通过配置生成 Agent

`forge-agent` 内置两种可配置模板：

- `prompt_agent`：基于 prompt 模板的分析型 Agent
- `search_agent`：先搜索、再分析的情报型 Agent

### 3.1 PromptAgent 配置

```yaml
agents:
  - agent_id: sports.news
    name: 赛事情报专家
    domain: sports
    template: prompt_agent
    tags: [news, briefing]
    config:
      variables:
        home: home
        away: away
      prompt: |
        你是一位足球赛事情报分析专家。
        主队：{home}，客队：{away}。
        请分析两队近期情报，输出 JSON：
        {
          "verdict": "lean_positive|neutral|lean_negative|risk",
          "confidence": 0.0-1.0,
          "risk": 0.0-1.0,
          "evidence": ["关键情报1", "关键情报2"]
        }
      output_schema:
        verdict: str
        confidence: float
        risk: float
        evidence: list[str]
      output_mapping:
        verdict: verdict
        confidence: confidence
        risk: risk
        evidence: evidence
      mock_mode: true
      mock_response: '{"verdict": "lean_positive", ...}'
```

字段说明：

| 字段 | 说明 |
|---|---|
| `agent_id` | 全局唯一标识 |
| `template` | 使用 `prompt_agent` 或 `search_agent` |
| `config.variables` | 从 payload 提取变量，`{模板变量名: payload_key}` |
| `config.prompt` | LLM prompt 模板，支持 `{变量}` 占位 |
| `config.output_schema` | 声明输出字段类型（用于解析校验） |
| `config.output_mapping` | 将 LLM 输出字段映射到 `AgentReport` |
| `config.mock_mode` | `true` 时使用 `mock_response`，不调用 LLM |
| `config.mock_response` | mock 返回的 JSON 字符串 |

### 3.2 SearchAgent 配置

```yaml
agents:
  - agent_id: sports.search
    name: 情报搜索专家
    domain: sports
    template: search_agent
    tags: [search, briefing]
    config:
      variables:
        home: home
        away: away
      query_template: "{home} vs {away} latest news injury lineup"
      search_backend: mock
      mock_results:
        - title: "赛前前瞻"
          source: "espn"
          snippet: "主队主力前锋伤愈复出。"
          published_at: "2026-06-30T10:00:00Z"
      prompt: |
        你是一位足球情报分析专家。
        搜索结果：{search_results}
        请输出 JSON：{...}
      output_schema: {...}
      output_mapping: {...}
      mock_mode: true
      mock_response: '{"verdict": "lean_positive", ...}'
```

额外字段：

| 字段 | 说明 |
|---|---|
| `query_template` | 渲染搜索 query 的模板 |
| `search_backend` | `mock` / `web` / `knowledge` |
| `mock_results` | mock 模式下的搜索结果列表 |
| `search_kwargs` | 传给后端搜索器的额外参数 |

---

## 4. 配置多源数据

`forge-agent` 通过 `field_map` + `transforms` 把异构源站数据映射到统一 schema。

```yaml
sources:
  - source_id: odds.site_a
    name: 站点 A 赔率
    source_type: mock
    normalizer: odds
    mock_payload:
      match:
        home_team: Arsenal
        away_team: Liverpool
      odds:
        home_win: "2.10"
        draw: "3.40"
        away_win: "3.20"
    field_map:
      home: match.home_team
      away: match.away_team
      home_odds: odds.home_win
      draw_odds: odds.draw
      away_odds: odds.away_win
    transforms:
      home_odds: float
      draw_odds: float
      away_odds: float
```

字段说明：

| 字段 | 说明 |
|---|---|
| `source_id` | 数据源唯一标识 |
| `source_type` | `mock` / `json_api` / `html` / `rss` |
| `normalizer` | 目标 schema，如 `odds` |
| `mock_payload` | mock 模式下的原始数据 |
| `field_map` | `{schema字段: raw字段路径}`，支持点号路径 |
| `transforms` | `{schema字段: 转换函数名}`，如 `float` / `int` / `strip` |
| `defaults` | 缺失字段的默认值 |

---

## 5. 组合成完整 Pipeline

一个完整的 Pipeline YAML 包含 5 个部分：

```yaml
mission:
  mission_id: sports.pipeline.demo
  name: 阿森纳 vs 利物浦 综合分析

match:
  home: 阿森纳
  away: 利物浦
  city: 伦敦
  date: "2026-07-01"

sources:
  - ... # 数据源配置

agents:
  - ... # Agent 配置

team:
  team_id: sports_analysis
  name: 赛事综合分析小组
  domain: sports
  agent_ids:
    - sports.news
    - sports.weather
    - sports.history
    - sports.odds
    - sports.search
  chief_id: generic.chief
  mode: parallel
```

运行方式：

```bash
python -m examples.run_pipeline
```

底层等价代码：

```python
from forge_agent.config.pipeline import PipelineLoader

loader = PipelineLoader.from_yaml("examples/configs/sports_pipeline.yaml")
board = await loader.run()
```

---

## 6. 添加新的专家 Agent

步骤：

1. 在 `examples/configs/sports_pipeline.yaml` 的 `agents` 列表新增一段配置
2. 把 `agent_id` 加入 `team.agent_ids`
3. 运行 `python -m examples.run_pipeline` 验证

示例：新增一个「伤病分析专家」

```yaml
  - agent_id: sports.injury
    name: 伤病分析专家
    domain: sports
    template: prompt_agent
    tags: [injury, briefing]
    config:
      variables:
        home: home
        away: away
      prompt: |
        分析 {home} 和 {away} 的伤病情况，输出 JSON：
        {"verdict": "...", "confidence": 0.0, "risk": 0.0, "evidence": []}
      output_schema:
        verdict: str
        confidence: float
        risk: float
        evidence: list[str]
      output_mapping:
        verdict: verdict
        confidence: confidence
        risk: risk
        evidence: evidence
      mock_mode: true
      mock_response: '{"verdict": "neutral", "confidence": 0.6, "risk": 0.3, "evidence": ["{home} 无重大伤病"]}'
```

然后修改 `team.agent_ids`：

```yaml
  agent_ids:
    - sports.news
    - sports.weather
    - sports.history
    - sports.odds
    - sports.search
    - sports.injury
```

---

## 7. 测试

### 7.1 运行所有相关测试

```bash
python -m pytest tests/test_pipeline_loader.py tests/test_search_agent.py -v
```

### 7.2 运行单个 Demo

```bash
python -m examples.configurable_sports_demo
python -m examples.multi_source_odds_demo
python -m examples.run_pipeline
```

### 7.3 代码质量检查

```bash
ruff check src/forge_agent/config src/forge_agent/core/templates src/forge_agent/core/factory.py examples/run_pipeline.py tests/test_pipeline_loader.py tests/test_search_agent.py
ruff format --check src/forge_agent/config src/forge_agent/core/templates src/forge_agent/core/factory.py examples/run_pipeline.py tests/test_pipeline_loader.py tests/test_search_agent.py
```

---

## 8. 提交代码

如果启用了 pre-commit，按以下流程：

```bash
# 1. 手动跑 pre-commit 自动修复
pre-commit run --all-files

# 2. 把自动修复后的改动重新 add
git add .

# 3. 提交
git commit -m "你的提交信息"
```

如果只想检查修改过的文件：

```bash
pre-commit run --files src/forge_agent/config/pipeline.py examples/run_pipeline.py
```

---

## 9. 常见问题

### Q1: mock_mode 有什么用？

`mock_mode: true` 时不调用真实 LLM，直接返回 `mock_response`，方便离线测试和快速验证配置。

### Q2: prompt 里的 JSON 大括号会冲突吗？

不会。`PromptAgent` 使用正则替换，只替换已知 `{变量}`，不会误伤 JSON 结构中的 `{` 和 `}`。

### Q3: 多个数据源的字段冲突怎么办？

`PipelineLoader` 会以 `match` 配置中的字段为准，数据源只贡献赔率等数值字段和 `source_evidence`。

### Q4: 如何接入真实搜索？

把 `search_backend` 改为 `web`，并提供真实的 `WebSearcher.search_fn` 或接入 Tavily/Bing/SerpAPI 等。

### Q5: 如何接入真实赔率 API？

把 `source_type` 改为 `json_api`，配置 `urls` 和 `headers`，`DataSource.fetch()` 会自动用 `httpx` 拉取。

---

## 10. 下一步

- **Phase 6**: 赛后复盘与自我迭代（准确率追踪、权重调整）
- **Phase 7**: 迁移 `guess_you_like` 的 18 个专家
- **Phase 8**: Dashboard、周期性调度、生产治理
