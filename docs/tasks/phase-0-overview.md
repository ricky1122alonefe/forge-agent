# Phase 0 — 打地基（总览）

> **目标**：消除"首次提交"的所有不确定性，建立干净的脚手架
> **天数**：1-2 天
> **必须性**：🔴 阻塞（不完成 → Phase 1 无法开始）
> **最后更新**：2026-06-27

---

## 任务状态总览

| ID | 任务 | 估时 | 依赖 | 状态 | 自动化验证 | 通过 |
|---|---|---|---|---|---|---|
| [T0.1](./T0.1-python-env.md) | Python 3.10+ 真环境 | 30min | — | ✅ | `python --version` ≥ 3.10 | 10:35 |
| [T0.2](./T0.2-license.md) | LICENSE 文件 | 5min | — | ✅ | `test -f LICENSE && grep MIT LICENSE` | 已有 |
| [T0.3](./T0.3-changelog.md) | CHANGELOG.md | 30min | — | ✅ | `test -f CHANGELOG.md && grep "0.3.0" CHANGELOG.md` | 10:40 |
| [T0.4](./T0.4-ci.md) | GitHub Actions CI | 2h | T0.1 | ✅ | `test -f .github/workflows/test.yml` | 10:42 |
| [T0.5](./T0.5-precommit.md) | pre-commit 配置 | 30min | T0.1 | ✅ | `test -f .pre-commit-config.yaml` | 10:42 |
| [T0.6](./T0.6-e2e-smoke.md) | 端到端冒烟测试 | 1h | T0.1, T0.2, T0.3 | ✅ | `python tests/e2e/test_smoke.py` | 10:45 |

**图例**：⬜ 未开始 · 🟡 进行中 · ✅ 已完成 · ❌ 失败

---

## 自动化验证

跑一遍所有 Phase 0 的检查：

```bash
cd /Users/popmart/Documents/python/forge-agent
bash scripts/check_phase0.sh
```

输出示例：
```
[T0.1] Python 3.10+ 真环境        ✅ PASS (3.11.7)
[T0.2] LICENSE 文件                ✅ PASS
[T0.3] CHANGELOG.md                ✅ PASS
[T0.4] GitHub Actions CI           ✅ PASS
[T0.5] pre-commit 配置             ✅ PASS
[T0.6] 端到端冒烟测试              ✅ PASS

Phase 0: 6/6 passed → 可以进入 Phase 1
```

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

- [ ] `bash scripts/check_phase0.sh` 输出 `6/6 passed`
- [ ] `pre-commit run --all-files` 干净通过
- [ ] GitHub Actions CI 3 个 Python 版本全绿

**所有勾选完毕 → 进入 Phase 1**

---

## 当前进度

- ✅ T0.1 Python 3.10+ 真环境（10:35）
- ✅ T0.2 LICENSE 文件（已有）
- ✅ T0.3 CHANGELOG.md（10:40）
- ✅ T0.4 GitHub Actions CI（10:42）
- ✅ T0.5 pre-commit 配置（10:42）
- ✅ T0.6 端到端冒烟测试（10:45）

**Phase 0 全部完成 ✅ 6/6** — 可以进入 Phase 1

完整执行记录见 [IMPLEMENTATION_LOG.md](./IMPLEMENTATION_LOG.md)
