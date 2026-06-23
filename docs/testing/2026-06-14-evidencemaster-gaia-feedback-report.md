# Gaia Research (EvidenceMaster) 反馈报告

> Run: cuprate-theory-004 | 模型: openai/deepseek-v4-flash | 日期: 2026-06-14
> 审核人: CodeWhale agent (deepseek-v4-pro)
> 范围: 端到端质量审查 + bug 挖掘

---

## 一、Bug Reports

### BUG-1: `stop.json` 的 `assessment_grounded_paper_leads` 计算错误（严重）

**现象:**

```json
// stop.json 报告:
"assessment_grounded_paper_leads": 0,
"assessment_grounded_paper_lead_ratio": 0.0
```

**实际数据:**

通过交叉对比 expand landscape、combined landscape（scan ∪ coverage）和 assessment evidence_packet：

| 指标 | stop.json | 实际 |
|------|-----------|------|
| expand 新增论文 | 13 | 13 ✅ |
| 其中被 assessment 引用 | **0** | **2**（15%） |

被引用的 2 篇 expand 新增论文：
- `867768552394850501` "Orbital-dependent effects of electron correlations..."
- `867751672242242064` "Reemergeing electronic nematicity in heavily hole-doped Fe-based..."

**复现步骤:**
1. 提取 `expand-*.json` 中的所有 paper_id
2. 减去 `scan-*.json` ∪ `coverage-*.json` 的 paper_id → 得到 `new_paper_leads`
3. 与 `assessment-*.json` 的 `evidence_packet.items[].source.paper_id` 交集 → 得到 `grounded`
4. 结果应为 2，而非 0

**疑似根因:**
Stop 决策器（`stop.json` 生成逻辑）在计算 `assessment_grounded_paper_leads` 时可能使用了错误的引用匹配路径——例如只检查了 `relations[].source_refs` 中的 `variable_id` 而非逐级展开到 `paper_id`，或者使用了与 assessment 不同步的 landscape 快照。

**影响:**
`query_novelty` 维度评分被错误压低（0.0 vs 实际 0.15），可能触发不必要的额外搜索迭代，浪费 token 和时间。

**严重级别:** 🔴 High

---

### BUG-2: `uv` 缓存在 macOS 上因 SIP 扩展属性导致 `uv add` 失败

**现象:**
```
Error: failed to add generated source package: uv add failed:
error: failed to open file `/Users/dp/.cache/uv/sdists-v9/.git`:
Operation not permitted (os error 1)
```

**根因:**
`/Users/dp/.cache/uv/sdists-v9/.git` 和 `.gitignore` 是两个 0 字节文件，带有 `com.apple.provenance` 扩展属性。macOS SIP/TCC 阻止了 `uv` 打开这些文件。

文件创建时间: 2025-11-14，可能是之前某次 `uv` 安装操作的残留。

**Workaround:**
设置 `UV_CACHE_DIR` 环境变量指向可写目录：
```bash
UV_CACHE_DIR=/tmp/uv-cache gaia research run ...
```

**建议修复:**
Gaia Research CLI 应在启动前执行 `uv cache clean` 或检测 uv 缓存目录的可访问性。或者 Gaia 应在调用 `uv` 之前主动设置 `UV_CACHE_DIR` 到工作空间内的 `.uv-cache/`。

**严重级别:** 🟡 Medium（有 workaround，但会阻塞首次用户体验）

---

### BUG-3: `report_plan` 阶段的 LLM 调用可能静默挂起，无超时恢复

**现象:**
`cuprate-theory-003` 在 `report_plan` 阶段启动了 LLM 调用（事件 `provider.started` at 12:18:30Z），但从那之后：
- 没有 `provider.completed` 事件
- 没有 `report_plan.output.json` 产出
- 状态停留在 `running`，但实际已僵死
- 没有超时日志或错误事件写入 `events.ndjson`

**影响:**
用户看到的 run 永远是 `running`，无法判断是正在执行还是已挂起。只能通过新建 run-id 绕过。

**建议修复:**
1. 每个 `provider.started` 应伴随一个 TTL 超时
2. 超时后应写入 `provider.timeout` 或 `provider.failed` 事件
3. `gaia research status` 应能区分 `running`（活跃）和 `stalled`（停滞）

**严重级别:** 🟡 Medium

---

## 二、设计缺陷

### ISSUE-1: Epistemic status 在最终报告中丢失

Assessment 阶段为每条 relation 标注了 `epistemic_status`：

| claim | status |
|-------|--------|
| 机械发射证据 | `candidate` |
| Zn掺杂 Mott 转变 | `provisional` |
| NMR 空穴掺杂 | `candidate` |
| DMFT 理论 | `provisional` |
| Kondo 绝缘体替代 | `candidate` |

但最终报告将所有声明以相同置信度呈现，读者无法区分"初步证据"和"较可靠证据"。`candidate`（需要更多验证）和 `provisional`（当前证据下暂定成立）之间的区别被完全抹平。

**建议:** `report_plan` 或 `report_section` 的 prompt 应要求 LLM 为每条声明附加 epistemic status 的表述（如"初步证据表明""较可靠证据支持"等定性措辞）。

---

### ISSUE-2: Candidate obligations 未传导到报告

Assessment 生成了 2 条 `candidate_obligations`：
1. 需要实验区分 Mott vs Kondo 绝缘体（`needs_more_evidence`）
2. 评估 DMFT 在低掺杂区的定量可靠性（`needs_method_check`）

这两条 obligations 在 `assessment-*.json` 中明确存在，但最终报告完全没有提及。它们本应出现在"局限性"或"未来工作"章节。

**建议:** `report_plan` 的 input 中应显式包含 `candidate_obligations` 字段，并要求 LLM 在报告中覆盖它们。

---

### ISSUE-3: 覆盖缺口未在报告中声明

原始主题包含 5 个子领域：

| 子领域 | 状态 |
|--------|------|
| 掺杂 Mott 绝缘体 | ✅ 选定为焦点 |
| 自旋涨落介导配对 | ⚠️ `needs_expand` |
| 赝能隙相 | ❌ 完全缺失（missing_bucket） |
| 奇异金属行为 | ❌ 完全缺失（missing_bucket） |
| d 波配对对称性 | ❌ 薄覆盖（thin_bucket） |

报告聚焦于第一个，但对后 4 个的缺失**完全没有声明**。读者会误以为这就是铜基超导理论的完整循证分析。

**建议:** `report_plan` prompt 应要求 LLM 在报告开头加入"范围说明"段落，列出已覆盖和未覆盖的子领域及其原因。

---

### ISSUE-4: 报告 LLM 可以"越级引用"未被 structured assessment 处理的证据

报告第 6 篇引用（LaAlO₃–SrTiO₃ 界面赝能隙论文）：
- 存在于 assessment `evidence_packet.items` 中
- **但未被任何 structured relation 引用**
- 由 `report_stitch` 阶段的 LLM 自行引入

这绕过了 structured assessment 的质量控制——读者无法追溯这个推理在评估框架中的出处。

**建议:** 报告 prompt 应区分"被 structured assessment 处理过的证据"和"仅存在于 evidence_packet 中但未被评估的证据"，并要求对不同来源的引用使用不同措辞（如"额外证据表明"vs"评估表明"）。

---

### ISSUE-5: 评估 LLM 忽略 expand 搜索的新增论文

Expand（定向）搜索找到了 13 篇新论文，其中：
- 5 篇确实相关但未被评估 LLM 引用（slave-boson Hubbard、Mott transistor、DMET、vertex divergences、VMC bilayer phase diagram）
- 3 篇是搜索噪声（YBCO 输运、涡旋 Mott）——这是搜索精度问题

**疑似根因:**
`assess_analysis` 的 prompt 将 12 篇已有 evidence items 与 13 篇 expand 新增论文混合输入，但没有显式标注"以下为本轮新增"。LLM 倾向于沿用已有证据（锚定效应）。

**建议:**
1. `assess_analysis.input.json` 中应对 expand 来源的 items 添加 `"is_new": true` 标记
2. Prompt 应包含指令："优先评估以下标记为本轮新增的证据项"
3. 或者将新增论文单独作为一批发送给 LLM，而非与已有证据混排

---

## 三、总结

| ID | 类型 | 严重度 | 一句话 |
|----|------|--------|--------|
| BUG-1 | Bug | 🔴 高 | stop.json 落地率计算错误（0 vs 15%） |
| BUG-2 | Bug | 🟡 中 | uv 缓存权限导致 run 启动失败 |
| BUG-3 | Bug | 🟡 中 | report_plan LLM 调用无超时恢复 |
| ISSUE-1 | 设计 | 🟡 中 | epistemic status 在报告中丢失 |
| ISSUE-2 | 设计 | 🟡 中 | obligations 未传导到报告 |
| ISSUE-3 | 设计 | 🟡 中 | 覆盖缺口未声明 |
| ISSUE-4 | 设计 | 🟢 低 | 越级引用不受控 |
| ISSUE-5 | 设计 | 🟡 中 | 新增论文未被评估 LLM 有效利用 |

**最关键的两个修复项:**
1. **BUG-1**：修复 stop 决策的论文落地率计算，否则会扭曲 search/assess 迭代的停止决策
2. **ISSUE-5**：在评估 prompt 中用 `is_new` 标记突出新增论文，可显著提升 `query_novelty` 指标

---

> 附：本反馈所有数据均可复现，证据文件路径：
> - `workspace-gaia/.gaia/research/runs/cuprate-theory-004/trace/stop.json`
> - `workspace-gaia/.gaia/research/assessments/assessment-doped-mott-insulator-*.json`
> - `workspace-gaia/.gaia/research/landscapes/expand-*.json`
> - `analyze_grounding.py`（复现脚本）
