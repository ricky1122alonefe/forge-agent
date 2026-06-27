# Phase 0 — 打地基（总览）

> **目标**：消除"首次提交"的所有不确定性，建立干净的脚手架
> **天数**：1-2 天
> **必须性**：🔴 阻塞（不完成 → Phase 1 无法开始）

---

## 任务卡片清单

| ID | 任务 | 估时 | 依赖 | 状态 |
|---|---|---|---|---|
| [T0.1](./T0.1-python-env.md) | Python 3.10+ 真环境 | 30min | — | ⬜ |
| [T0.2](./T0.2-license.md) | LICENSE 文件 | 5min | — | ⬜ |
| [T0.3](./T0.3-changelog.md) | CHANGELOG.md | 30min | — | ⬜ |
| [T0.4](./T0.4-ci.md) | GitHub Actions CI | 2h | T0.1 | ⬜ |
| [T0.5](./T0.5-precommit.md) | pre-commit 配置 | 30min | T0.1 | ⬜ |
| [T0.6](./T0.6-e2e-smoke.md) | 端到端冒烟测试 | 1h | T0.1, T0.2, T0.3 | ⬜ |

---

## 执行顺序

```
T0.1 (并行) T0.2 (并行) T0.3
    ↓
T0.4 (并行) T0.5
    ↓
T0.6
```

---

## 出口标准（Phase 0 完成定义）

- [ ] Python 3.10+ 环境可用
- [ ] `LICENSE` 文件存在
- [ ] `CHANGELOG.md` 文件存在
- [ ] GitHub Actions CI 全绿（3 个 Python 版本）
- [ ] pre-commit 配置就绪
- [ ] 端到端冒烟测试通过

**所有勾选完毕 → 进入 Phase 1**

---

## 当前进度

- ⬜ T0.1 Python 3.10+ 真环境
- ⬜ T0.2 LICENSE 文件
- ⬜ T0.3 CHANGELOG.md
- ⬜ T0.4 GitHub Actions CI
- ⬜ T0.5 pre-commit 配置
- ⬜ T0.6 端到端冒烟测试

**下一步**：执行 T0.1
