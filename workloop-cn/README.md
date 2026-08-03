# Workloop 中文对照版

本目录是英文主版本的人类可读中文对照，覆盖核心协议、六个方法 Skill、插件控制 Skill、四个模板和一个完整示例。

英文主版本是唯一可执行来源：

- `../workloop-skills/`：独立方法 Skill；
- `../workloop-plugin/`：插件打包、控制脚本、Hook 和测试；
- `../docs/`：英文协议。

本目录不参与插件发现，也不复制 Python 控制器。命令、文件名、稳定 ID 和状态值保留英文，因为它们属于机器接口；其余说明全部使用中文。修改规则时，应先修改并验证英文主版本，再同步这里的同路径中文内容。

对应关系：

```text
README.md                              ↔ workloop-cn/README.md
docs/                                  ↔ workloop-cn/docs/
workloop-skills/                       ↔ workloop-cn/workloop-skills/
workloop-plugin/skills/workloop-controls/
                                       ↔ workloop-cn/workloop-plugin/skills/workloop-controls/
```
