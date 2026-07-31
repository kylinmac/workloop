# Transition 接受不存在的 Git 提交

## 现象

`transition --git-commit` 接受拼错或不存在的 40 位 SHA，并原样写入验证交接。

## 影响

tested_commit 与 Evidence 永远无法匹配，且审计记录引用不存在的对象。

## 根因

transition 只把参数当字符串保存，没有交给 Git 解析和验证。

## 旧门禁为何没拦截

测试只使用当前 HEAD 或省略参数，没有负向提交对象用例。

## 修复

所有主流程和子流程 transition 在修改状态前使用 Git 验证 commit 对象，并将短 SHA 规范化为完整提交 ID；不存在时不写状态。

## 回归

不存在的 40 位 SHA 必须失败且状态不变；合法短 SHA 必须保存为完整 SHA。

## 预防规则

协议中的 Git 标识必须由 Git 解析，不能信任调用方字符串。
