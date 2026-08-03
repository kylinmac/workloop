---
name: workloop-memory
description: Use after a review passes or a real failure occurs, when deciding whether a lesson should enter the project failure memory.
---

# Workloop Memory：错误记忆更新

## 产物与执行者

`.workloop/memory.md`（项目级一份，模板见 `workloop/templates/memory.md`）。review pass 后由执行者更新，依据 review.md 中审查者对教训的建议；无教训时在 review.md 写"记忆更新：无"。

## 准入条件（全部满足才进）

1. 来自真实失败或 review 发现的真实问题，不是理论担忧。
2. 未来的需求可能再次触发（一次性事故不进）。
3. 能写出**触发条件**：什么信号出现时该想起这条。
4. 能写出**预防检查**：优先是可执行命令或验收标准写法；其次是 review 校验项。写不出预防检查的教训还没被理解透，先想透再进。

没有满足条件的教训时，在 review.md 里写"记忆更新：无"，不硬凑。

## 硬上限：20 条

超限时必须先做一件事再新增：合并同根因条目，或按"最近触发"列淘汰最久未触发的条目（该列由入口 skill 的铁律负责回写，没有它淘汰就无依据）。**永远不允许扩容上限**——记忆的价值在于每条都会被真的读到；一个 200 条的记忆库等于没有记忆库。

## 升级出口

同一条记忆若在多个 loop 中反复触发，说明它不该靠"记住"来防——把预防检查固化为项目里的自动化检查（测试、lint、CI、hook），然后从 memory.md 移除该条。记忆是检查的孵化器，不是终点。

## 常见错误

| 错误 | 纠正 |
|---|---|
| 把流程口号写进记忆（"要认真验证"） | 只收带具体触发条件和具体检查的条目 |
| 每个 loop 结束都硬写一条 | 无教训写"无"；低质量条目稀释整个记忆库 |
| 记忆只增不减 | 每次新增先检查可合并、可淘汰、可升级为自动化的条目 |
