# 状态与 Evidence 可被手工旁路

## 现象

直接编辑 `loop.yaml` 可推进主流程或子流程状态；调用方也可手写 passed Evidence。

## 影响

控制程序的状态转换和测试执行门禁可被绕过，审计链不可信。

## 根因

状态文件没有控制字段摘要；Evidence 命令信任调用方提交的结果与覆盖 JSON。

## 旧门禁为何没拦截

Schema 只能验证形状，不能证明修改来自合法命令或测试真实运行。

## 修复

记录控制字段快照，加载时校验篡改；Evidence 由插件执行命令、生成 nonce、绑定当前提交并读取本次测试报告。

## 回归

手改 state/subflow/Gate 或复用旧报告、错 commit 报告、零断言报告均必须失败。

## 预防规则

受控状态只能由 transition/gate/evidence/checkpoint 命令改变。
