# 非 UI Flow 缺少断言报告约束

## 现象
code/command flow 可以只凭退出码通过。
## 影响
空脚本或只启动不断言的流程可形成 passed Evidence。
## 根因
nonce、commit、断言和步骤覆盖只强制于 UI。
## 旧门禁为何没拦截
把真实执行等同于有效业务断言。
## 修复
所有 `flow_id` Evidence 要求本次运行生成统一报告；targeted check 仍可按命令退出码验证构建、lint 等确定结果。
## 回归
非 UI flow 无报告、零断言或漏步骤失败；完整报告通过。
## 预防规则
执行器不同不改变 flow 级证据身份与断言底线。
