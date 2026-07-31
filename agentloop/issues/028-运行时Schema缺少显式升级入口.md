# 运行时 Schema 缺少显式升级入口

## 现象
旧项目 `.agentloop/schemas` 可长期落后于插件 Schema。
## 影响
Agent 参考旧结构编写产物，却由新插件验证。
## 根因
Schema 只在 init 时同步，恢复任务没有升级命令。
## 旧门禁为何没拦截
实际验证直接读取插件 Schema，因此不会暴露参考副本漂移。
## 修复
增加 runtime-upgrade 命令和 doctor/validate 漂移提示；命令原子覆盖 Schema 与示例。
## 回归
人为放置旧 Schema 后检测失败，执行升级后哈希一致。
## 预防规则
插件升级必须提供项目内运行时资产同步路径。
