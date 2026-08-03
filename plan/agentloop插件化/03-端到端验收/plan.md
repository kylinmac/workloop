# 阶段 3：端到端验收

- 状态：completed
- 阶段目标：确认源码插件与 Codex 安装副本均具备完整流程能力。
- 输入与约束：阶段 2 的完整插件；验证不得依赖外部服务。

## 工作项
- [x] 校验插件清单和 Skill
- [x] 校验 Python 语法和运行依赖
- [x] 执行 trivial 从初始化到 done 的完整生命周期
- [x] 验证 requirement/completion Gate 摘要与事件
- [x] 验证 composite 子流程和 epic 子 Loop 初始化
- [x] 验证项目 Schema 正例和反例
- [x] 比对插件内置流程资料与仓库源文件
- [x] 安装插件并从安装缓存执行 doctor

## 交付与验证
- 交付物：已安装的 `development-process-agentloop@development-process`
- 验证方式：完整生命周期测试、Skill 校验、插件校验、Schema 校验、资料逐目录比对和安装缓存 doctor 全部通过

## 执行记录
- 插件不包含 MCP、App Server、数据库或常驻进程。
- 插件改名后重新生成 cachebuster、安装并验证。
- Hooks 首次在新任务加载时仍需由用户检查并信任，这是 Codex 的安全要求。
