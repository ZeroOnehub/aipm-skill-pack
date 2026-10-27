# 17 个 Agent 组件参考实现

每个组件一个文件夹：`README.md` 讲它解决什么问题、怎么工作、生产级要点；`code.py` 是可以直接运行的最小实现。架构方案选中了哪些组件，研发交接时就把哪些复制进交接包，给写代码的人或编码 AI 参考。

**参考，不照抄。** 这些实现是为了讲清机制写的，按产品的需要改写，不要整份复制进产品代码。

| 域 | 组件 | 什么时候需要 |
|---|---|---|
| 行动 | [s01 Agent Loop](s01_agent_loop/) · [s02 工具系统](s02_tool_use/) · [s14 MCP 插件](s14_mcp_plugin/) | 一切基础；要接一整套外部工具生态时加 s14 |
| 约束 | [s03 权限系统](s03_permission/) · [s04 钩子系统](s04_hooks/) | 删除、支付、发消息、隐私数据等敏感操作；审计、拦截、埋点 |
| 认知 | [s05 任务规划](s05_todo_write/) · [s07 技能加载](s07_skill_loading/) · [s09 记忆系统](s09_memory/) · [s17 目标闭环](s17_goal_loop/) | 要跟踪进度；知识库大；跨会话记偏好；自动判断何时算完成 |
| 上下文 | [s06 子 Agent](s06_subagent/) · [s08 上下文压缩](s08_context_compact/) | 子任务会撑爆上下文或可以并行；长会话、日志量大 |
| 协作 | [s10 任务系统](s10_task_system/) · [s11 后台任务](s11_background_tasks/) · [s12 定时调度](s12_cron_scheduler/) · [s13 Agent 团队](s13_agent_teams/) | 目标要持久化续跑；慢操作不能阻塞；定时触发；多任务并行且隔离 |
| 编排 | [s15 集成 Harness](s15_integrated_harness/) · [s16 工作流运行时](s16_workflow_runtime/) | 选了 3 个以上可选组件要归一；流程固定可以写死 |

## 怎么运行

```sh
cd <参考组件目录>
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env        # 填 ANTHROPIC_API_KEY
.venv/bin/python s01_agent_loop/code.py
```

- 所有 `code.py` 都依赖同一目录下的 `common/`（读 `.env`、检查 Key、出错时给一句中文提示），单独拷走一个文件跑不起来，要连同 `common/` 一起。
- s13、s15、s16 用到 `fcntl`，只能在 macOS 和 Linux 上运行。
- 参考实现会执行 Shell 命令、读写文件，请在空的测试目录里跑，不要在放着重要文件的地方跑。
