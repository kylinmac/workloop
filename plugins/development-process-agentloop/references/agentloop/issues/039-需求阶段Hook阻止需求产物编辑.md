# 需求阶段 Hook 阻止需求产物编辑

## 现象

Loop 位于 `draft` 或 `clarifying` 时，PreToolUse Hook 拒绝编辑该 Loop 的 `requirement.md` 和非受控 `loop.yaml` 需求字段，并提示先通过需求 Gate。

## 影响

需求产物尚未生成就被要求通过依赖该产物的 Gate，形成恢复不可达的循环依赖。

## 根因

Hook 将所有非开发状态统一视为不可编辑，没有区分项目源码与当前 Loop 的需求控制产物；同时绝对路径没有归一化为项目相对路径，合法 scope 可能被误判为越界。

## 旧门禁为何没拦截

Hook 回归只验证非法修改受控 `state` 会被拒绝，没有覆盖需求阶段写入和绝对路径输入。

## 修复

- `draft/clarifying` 允许编辑当前 Loop 的需求文件和非受控 `loop.yaml` 需求字段。
- `state`、Gate、transition、Evidence 等受控字段继续拒绝直接编辑。
- Patch 路径先归一化为项目相对路径再做 scope 比较。

## 回归

使用绝对路径模拟需求文件 Patch，确认 Hook 不拒绝；原非法状态修改用例继续拒绝。

## 预防规则

每个 Hook 禁止规则必须配套验证同阶段的合法写入路径，禁止只测拒绝路径而不测恢复入口。
