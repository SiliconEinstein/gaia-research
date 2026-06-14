# EvidenceMaster Agent Test — Bug List

> Source snapshot: `/private/tmp/evidencemaster-agent-test/bug-list.md`
>
> Test round: first local EvidenceMaster agent test
>
> Captured date: 2026-06-14

测试时间: 2026-06-14  
测试环境: `/private/tmp/evidencemaster-agent-test`  
Gaia 版本: `gaia-lang 0.5.0` (dev), `gaia-research 0.1.0`

## 修复状态总览

| ID | 状态 | 本轮处理 |
|---|---|---|
| Bug #1 | Fixed | `doctor --for-agent --json` 首次即返回 credentials readiness,并检查 LKM/LLM 三变量。 |
| Bug #2 | Fixed | 同一 `run_id` resume 只追加 `run.resumed`,不重复 `run.created` 或重写 state。 |
| Bug #3 | Fixed | `query_plan.default_action` 在 resume 时生效;新 checkpoint 默认 query 为 topic。 |
| Bug #4 | Fixed | 新增 `gaia research contract query_plan`,并支持消费 `query_plan.response.json`。 |
| Bug #5 | Fixed | LLM readiness/provider adapter 只接受 `GAIA_RESEARCH_LLM_*`,旧/provider-native env 不再误报 ready。 |
| Bug #6 | Partially fixed | 契约改为显式 runtime/profile 配置,不再 hardcode model/base;团队推荐模型清单仍待产品侧确认。 |
| D1 | Open | resume 仍要求 CLI 传 `--topic`;本轮未改为可选。 |
| D2 | Fixed | `gaia research render` 已支持 `research_landscape` 和 `field_map` Markdown。 |

---

## 🐛 Bug #1: `gaia research doctor` 首次检查不充分，run 后才暴露凭证缺失

**严重性**: High (违反 agent 规则 1 — "verify readiness before first workflow")

**复现步骤**:
1. 新环境首次运行 `gaia research doctor --for-agent --json`
2. 返回 `"ok": true`, `"missing": []`, **不包含 `credentials` 检查字段**
3. 启动一个 research run: `gaia research run <pkg> --topic "..." --run-id test-1 --json`
4. Run 推进到 `query_plan` checkpoint 后停下
5. 再次运行 `gaia research doctor --for-agent --json`
6. 返回 `"ok": false`, `"missing": ["llm_model"]`, **突然出现 `credentials` 字段并报错**

**预期行为**:  
首次 doctor 应当检查所有运行时依赖(LKM key / LLM model / LLM API key),而不是等 run 实际执行后才暴露缺失项。

**影响**:  
Agent 无法在第一次 workflow 前可靠地验证就绪状态,违反 system-prompt.md 规则 1。

**建议修复**:  
Doctor 应当总是返回 `credentials` 字段,并在首次调用时就验证 LLM provider 配置完整性。

**状态**: Fixed

**验证**:
- `tests/test_agent_platform_contract.py::test_doctor_can_emit_agent_readable_json`
- `tests/test_agent_platform_contract.py::test_doctor_reports_external_credential_readiness_without_secret_values`
- `tests/test_agent_platform_contract.py::test_doctor_can_load_explicit_llm_namespace_from_env_file`

---

## 🐛 Bug #2: `gaia research run` resume 语义混乱 — 多次 emit `run.created` 事件

**严重性**: Medium (事件日志语义错乱,但不影响功能推进)

**复现步骤**:
1. 启动 run: `gaia research run <pkg> --topic "..." --run-id test-1 --json`
2. Run 停在 checkpoint: `status=waiting_for_input`, `phase=query_plan`
3. 再次调用相同命令(不带 `--query`): `gaia research run <pkg> --topic "..." --run-id test-1 --json`
4. 查看 `events.ndjson`

**观察到的异常**:
```json
{"type": "run.created", "run_id": "test-1", "ts": "2026-06-14T09:49:33Z", ...}
{"type": "run.created", "run_id": "test-1", "ts": "2026-06-14T09:57:17Z", ...}  ← 同一 run_id 再次 created
{"type": "run.created", "run_id": "test-1", "ts": "2026-06-14T09:57:38Z", ...}  ← 第三次!
```

**预期行为**:  
- Resume 已有 run 时,应当 emit `run.resumed` 或 `checkpoint.continued` 事件,而非重复 `run.created`
- 事件日志应当清楚区分 "首次启动" vs "从 checkpoint 恢复"

**影响**:  
UI 或 agent 解析事件流时无法区分是新 run 还是 resume,可能误判 run 数量或状态。

**本轮修复决策**:

同一个 `run_id` 已有 `state.json` 时不再重写 state 或重复 emit
`run.created`; 改为追加 `run.resumed` 事件。

**状态**: Fixed

**验证**:
- `tests/test_run.py::test_start_research_run_resumes_existing_run_without_duplicate_created_event`

---

## 🐛 Bug #3: `checkpoint.query_plan` 的 `default_action` 字段无实际作用

**严重性**: Low (misleading contract,但不影响实际使用)

**复现**:
1. Run 停在 `query_plan` checkpoint
2. Checkpoint 文件内容:
   ```json
   {
     "prompt": "Review or edit broad query families before live search.",
     "choices": [{"id": "continue", "label": "Continue with defaults", "recommended": true}],
     "default_action": {"action": "continue", "queries": []}
   }
   ```
3. 不带 `--query` 再次调用 `gaia research run`,引擎**不执行 `default_action`**,只是重新生成同样的 checkpoint

**预期行为**:  
- 如果 `default_action` 字段存在且有 `recommended: true`,引擎应当在 resume 时自动执行该 action
- 或者,如果 `default_action` 只是 UI 提示,应当在字段命名上体现(如 `suggested_action`)

**影响**:  
Agent 或人类用户可能误以为 "continue with defaults" 可以自动生效,实际上必须显式提供 `--query`。

**本轮修复决策**:

新建 checkpoint 的 `default_action.queries` 写入原始 topic。已有旧 checkpoint
如果 `queries=[]`,resume 时回退到 state 中的 topic。CLI 会写
`query_plan.response.json`,标记 `source=default_action`。

**状态**: Fixed

**验证**:
- `tests/test_cli_status.py::test_run_command_resumes_query_plan_with_default_topic_query`

---

## 🐛 Bug #4: Checkpoint response 协议缺少文档和可发现接口

**严重性**: Medium (阻碍 agent 手工注入 checkpoint response)

**现状**:
- `gaia research contract` 可以 print `field_map / focus / assess / propose` 的 contract
- `query_plan` checkpoint 没有对应的 contract subcommand
- 没有文档说明如何手工写 `query_plan.response.json` 并让引擎 consume

**影响**:  
Agent 只能通过 `--query` 这条「唯一正面路径」推进 checkpoint,无法在更复杂场景下手工构造 response(如批量注入多个 query families)。

**建议**:
- 补充 `gaia research contract query_plan` 或在文档中说明 response schema
- 或显式声明 query_plan checkpoint 不支持手工 response,只能用 `--query` 传参

**本轮修复决策**:

补充 `gaia research contract query_plan`,描述 checkpoint request/response 路径、
`queries` 字段和默认动作语义。

CLI 同时会在 resume 时优先消费同目录下的 `query_plan.response.json`;
若不存在 response,再回退到 checkpoint `default_action`。

**状态**: Fixed

**验证**:
- `tests/test_research_contracts.py::test_query_plan_contract_documents_checkpoint_response_shape`
- `tests/test_cli_status.py::test_run_command_resumes_query_plan_from_response_file`

---

## 🐛 Bug #5: `doctor` 把 `ANTHROPIC_API_KEY` 计入 LLM 就绪,但 `_litellm_completion` 根本不读它

**严重性**: High (doctor 误报 ready,实际 run 必然在 LLM phase 失败或长时间挂起)

**证据**:

1. `research_cli.py` 的 doctor 检查接受 4 个 api_key env var 之一:
   ```python
   "api_key": [
     "GAIA_RESEARCH_LLM_API_KEY",
     "LITELLM_PROXY_API_KEY",
     "OPENAI_API_KEY",
     "ANTHROPIC_API_KEY",
   ]
   ```
   只要任一被设置,`llm_provider.api_key_configured: true`,doctor 报 `ok: true`。

2. 但 `research_providers.py:486-496` 的实际 LiteLLM 调用代码只读 **2 组**:
   ```python
   api_base = os.environ.get("GAIA_RESEARCH_LLM_API_BASE") or os.environ.get("LITELLM_PROXY_API_BASE")
   api_key  = os.environ.get("GAIA_RESEARCH_LLM_API_KEY") or os.environ.get("LITELLM_PROXY_API_KEY")
   ```
   **完全不读 `ANTHROPIC_API_KEY` 或 `OPENAI_API_KEY`**。

3. 现实后果(本次测试观察到):
   - 环境里有 `ANTHROPIC_API_KEY=...`(指向 gpugeek 代理,给 Claude Code agent 自用)
   - Doctor 直接报 `llm_provider.ready: true` + `missing: []`
   - 实际启动 `--analysis-provider litellm` 时,LiteLLM 没拿到 api_key/api_base,会走 model 字符串里的默认 provider 路径,大概率 401 / "模型不存在" / 超时挂起

**预期行为**(三选一,需团队决策):

- (a) Doctor 的 `accepted_env` 只列实际被读的两组,删除 `ANTHROPIC_API_KEY` / `OPENAI_API_KEY`
- (b) `_litellm_env_kwargs()` 扩展支持 `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` 作为 fallback,并根据 model 前缀(`anthropic/...` / `openai/...`)自动路由
- (c) Doctor 同时报告 "key 已配置但与所选 `GAIA_RESEARCH_LLM_MODEL` 前缀不匹配" 这种 warning

**本轮修复决策**:

采用更严格的 (a) 变体: `doctor` 和 `_litellm_env_kwargs()` 都只接受
`GAIA_RESEARCH_LLM_MODEL`, `GAIA_RESEARCH_LLM_API_BASE`,
`GAIA_RESEARCH_LLM_API_KEY`。同时把 `GAIA_RESEARCH_LLM_API_BASE` 设为
agent readiness 必填项,避免 model id 与默认 provider/base URL 产生隐式绑定。
`LITELLM_PROXY_*`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY` 可继续供宿主 agent
自己使用,但不计入 Gaia Research 工作流就绪。

**影响**: 这是上面 Bug #1 的根因之一 —— doctor 的 "ready" 信号对 agent 完全不可信。

**状态**: Fixed

**验证**:
- `tests/test_agent_platform_contract.py::test_doctor_requires_explicit_gaia_research_llm_namespace`
- `tests/test_research_providers.py::test_litellm_env_kwargs_ignores_legacy_and_provider_native_keys`

---

## 🐛 Bug #6: `GAIA_RESEARCH_LLM_MODEL` 文档与实测不一致,缺少示例值

**严重性**: Medium (DX / onboarding 问题)

**现状**:

- README、capabilities、doctor 的 setup 说明里**没有给出任何可工作的 `GAIA_RESEARCH_LLM_MODEL` 示例值**
- 仓库内 3 处证据相互冲突:
  - `tests/test_research_providers.py`: 用 `openai/deepseek-chat` + `LITELLM_PROXY_API_BASE=https://api.deepseek.com`
  - `docs/execution-record.md`: 用 `--model openai/deepseek-chat`
  - 用户口头记忆: "代码里用的是 deepseek-v4-flash"(实测在 gaia-research 仓库**找不到**该 model id,只在隔壁 `propositional_logic_analysis/clustering/src/config.py` 的 mapping 表里出现)

**复现**:
1. 新用户根据 doctor 的 `setup_command` 字段尝试配置 LLM
2. 没有任何指引说明 model id 该写什么(`claude-sonnet-4-6`? `deepseek-chat`? `deepseek-v4-flash`? `openai/...`?)
3. 任意瞎填都会通过 doctor 检查(只验证非空),实际 run 时报 `模型不存在或无权限`

**建议**:

- 在 `capabilities --json` 输出里加 `recommended_models` 字段,列举团队已验证可用的 `(model, api_base)` 组合
- 在 doctor 报错消息里给出最小可用样例,例如:
  ```
  export GAIA_RESEARCH_LLM_MODEL=openai/deepseek-chat
  export GAIA_RESEARCH_LLM_API_BASE=https://api.deepseek.com
  export GAIA_RESEARCH_LLM_API_KEY=sk-...
  ```
- 在 README 增补一节 "LLM provider configuration",覆盖 DeepSeek 官方 / LiteLLM-compatible proxy / 自托管几种典型配置

**本轮修复决策**:

不在代码中 hardcode 推荐模型或默认 endpoint。由 Bohrium agent runtime 或本地
dotenv 显式配置 `(GAIA_RESEARCH_LLM_MODEL, GAIA_RESEARCH_LLM_API_BASE,
GAIA_RESEARCH_LLM_API_KEY)`。后续如果要给出团队验证组合,应放在部署文档或
profile config 中,而不是 provider adapter 默认值里。

**状态**: Partially fixed

**剩余事项**:
- 团队需要确认线上 Bohrium 可用的 `(model, api_base)` 组合。
- 确认后可在部署 spec/profile config 中列推荐组合,但不写进 provider 默认值。

---

## ⚠️ 设计可疑点(不一定是 bug)

### D1: `gaia research run` resume 时仍需传 `--topic` (必填参数)

- 已有 run 的 topic 已经记录在 `state.json` 中
- Resume 时如果 `--topic` 拼写不一致,会怎样?(未测试)
- 建议: resume 场景下 topic 应为可选,从已有 state 读取

**状态**: Open

**说明**:
本轮仅修复同 `run_id` 的 state/event resume 语义,未调整 Typer 参数结构。

### D2: LKM search 完成后,`landscape scan` phase 立即完成(耗时 1 秒),但没有生成可读的中间产物

- `scan-<timestamp>.json` 存在,但格式面向引擎内部,agent 无法快速提取"找到了哪些关键 paper"给用户看
- 建议: 提供 `gaia research render --artifact <landscape-json>` 输出可读 Markdown

**本轮修复决策**:

扩展 `gaia research render` 的 deterministic renderer,支持 `research_landscape`
和 `field_map` artifact,用于给用户展示 query、paper leads、evidence items、
candidate focuses、field buckets、coverage gaps 和 recommended expansions。

**状态**: Fixed

**验证**:
- `tests/test_research_report.py::test_report_renders_landscape_markdown_for_intermediate_review`
- `tests/test_research_report.py::test_report_renders_field_map_markdown_for_intermediate_review`

---

## 下一步压测计划

- [x] Bootstrap & doctor
- [x] Run start → query_plan checkpoint
- [x] Resume with `--query` → landscape scan → focus_analysis checkpoint
- [ ] **[暂停]** Resume with `--analysis-provider litellm` → 驱动 focus / assess phases
  - **阻塞原因**: LLM provider 配置不明 — 当前 env 里的 `ANTHROPIC_API_KEY` 不会被 gaia 读取(见 Bug #5),且没有团队验证过的 model id 可用(见 Bug #6)
  - **恢复条件**: 确定一组可用的 `(GAIA_RESEARCH_LLM_MODEL, GAIA_RESEARCH_LLM_API_BASE, GAIA_RESEARCH_LLM_API_KEY)`
- [ ] 检查最终 artifacts 结构和可读性
- [ ] 测试多次 run 的状态隔离(不同 run-id)
