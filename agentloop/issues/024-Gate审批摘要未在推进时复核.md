# Gate 审批摘要未在推进时复核

## 现象
审批时保存 subject digest，后续不重新计算。
## 影响
审批对象被修改后旧批准仍有效。
## 根因
摘要只被当作审计字段，没有进入 Gate 有效性判断。
## 旧门禁为何没拦截
转换只读取 Gate status。
## 修复
validate、相关 transition 和聚合重新计算当前 subject manifest；不一致时拒绝并使当前批准失效。
## 回归
批准后修改 requirement 或 completion subject，推进必须失败；恢复原内容后可继续。
## 预防规则
任何绑定摘要都必须同时定义消费位置和失效行为。
