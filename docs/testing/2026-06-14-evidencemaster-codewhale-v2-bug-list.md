# EvidenceMaster CodeWhale Test — V2 Bug List

> Source snapshot: `/private/tmp/evidencemaster-agent-test/bug-list.md`
>
> Test round: v2 local EvidenceMaster agent test
>
> Captured date: 2026-06-14
>
> Environment: CodeWhale + Gaia Research 0.1.0 / Gaia Core 0.5.0
>
> Workspace: `/private/tmp/evidencemaster-agent-test`

---

## 问题总览

| # | 问题 | 严重程度 | 状态 |
|---|------|----------|------|
| 1 | macOS 安全框架阻止 `uv` 访问用户缓存 | 🟡 中 | 已绕过，待根治 |
| 2 | Checkpoint 推进机制不明显 | 🟡 中 | 已找到方法，待文档化 |
| 3 | `approval` 配置字段名不确定 | 🟡 中 | 待确认 |

---

## 问题 1：macOS 安全框架 + `uv` 缓存冲突

### 现象

```text
Error: uv add failed: error: failed to open file
`/Users/dp/.cache/uv/sdists-v9/.git`: Operation not permitted (os error 1)
```

`gaia research run` 在内部调用 `uv add` 生成源码包时，`uv` 需要操作
`~/.cache/uv/` 下的 `.git` 标记文件，macOS TCC/Sandbox 阻止了 CodeWhale
shell 进程的访问。

### 根因

CodeWhale 的 shell 进程运行在受 macOS 安全框架约束的环境中，对用户家目录下的
`~/.cache/uv/` 没有写入权限。删除缓存（`rm -rf ~/.cache/uv`）同样被拦截。

### 临时解决

```bash
export UV_CACHE_DIR=/private/tmp/evidencemaster-agent-test/.uv-cache
```

将 `uv` 缓存重定向到工作区内的可写路径。

### 建议根治

1. 在 CodeWhale 项目配置中预设环境变量，避免每次手动 export
2. Gaia 端检测 macOS 沙箱环境，自动将 `uv` 缓存切换到包内 `.gaia/` 目录
3. 或在 README 的 "Runtime Configuration" 中注明此事项

---

## 问题 2：Checkpoint 推进机制不够直观

### 现象

agent 将 checkpoint response 写入 `checkpoints/query_plan.response.json` 后，
状态没有自动推进。重复调用 `gaia research status` 显示状态仍为
`waiting_for_input`。

### 根因

Gaia 的状态机不会主动轮询 response 文件。写入 response 只是一个状态记录，
实际的推进需要重新调用 `gaia research run` 并保持相同的 `--run-id`，此时
Gaia 检测到已处理的 checkpoint + 已有 response 文件，从而继续执行下一阶段。

### 正确的 checkpoint 推进 SOP

```text
1. gaia research run <pkg> --topic "..." --run-id xxx --json
2. 读取 checkpoints/<phase>.request.json
3. 写入 checkpoints/<phase>.response.json
4. gaia research run <pkg> --topic "..." --run-id xxx --json  ← 相同参数
5. 状态机从 checkpoint 继续
```

### 建议

在 `system-prompt.md` 或 agent skills 中将此 SOP 文档化，减少 agent 的试错成本。

### 本轮处理

已将 checkpoint 推进 SOP 写入 `gaia-research-run` skill：agent 在写入
`query_plan.response.json` 后必须用相同 `pkg/topic/run-id/profile/config/env-file`
重新调用 `gaia research run ... --json`，而不是等待 `status` 自动推进。

---

## 问题 3：`approval` 配置字段名不确定

### 现象

在 `~/.codewhale/config.toml` 的项目块中添加 `approval = "auto"` 后重启会话，
runtime 标签仍显示 `approval="suggest"`。

```toml
[projects."/private/tmp/evidencemaster-agent-test"]
trust_level = "trusted"
allow_shell = true
approval = "auto"          # ← 未生效
```

### 根因

CodeWhale 项目级别审批策略的配置字段名可能不是 `approval`，而是：

- `approval_mode`
- `auto_approve`
- 或其他

需查阅 CodeWhale 文档确认。

### 建议

在 CodeWhale 文档中确认正确的字段名后更新配置。

---

## 已验证正常的项

- `doctor` / `capabilities` 双命令通过（LLM 凭证 + LKM 凭证齐全）
- `.env.local` 作为凭证文件的路径可用（替代 README 中缺失的 `research.dummy.env`）
- 搜索链路完整：7 个查询全部返回结果（70 原始结果 → 67 论文线索）
- `landscape` 产物成功生成
