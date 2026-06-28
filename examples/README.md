# Examples

这里存放 `forge-agent` 的示例代码。建议按以下顺序阅读和测试：

## 推荐路径

1. **`run_pipeline.py`** — 端到端 Pipeline（最新、最完整）
   ```bash
   python -m examples.run_pipeline
   ```
   加载 `examples/configs/sports_pipeline.yaml`，自动完成：
   - 多源赔率归一化
   - 5 个配置化专家并行分析
   - Chief 汇总输出最终决策

2. **`configurable_sports_demo.py`** — 配置化 Agent 入门
   ```bash
   python -m examples.configurable_sports_demo
   ```
   展示如何用 YAML 配置生成 3 个专家 Agent。

3. **`multi_source_odds_demo.py`** — 多源数据归一化
   ```bash
   python -m examples.multi_source_odds_demo
   ```
   展示两个不同格式的赔率源如何映射到统一的 `OddsRecord`。

## 配置文件

- `configs/sports_pipeline.yaml` — 完整 Pipeline 配置
- `configs/sports_agents.yaml` — PromptAgent 专家配置
- `configs/odds_sources.yaml` — 数据源配置

## 详细文档

参见 `docs/guides/configurable-agent-pipeline.md`。
