<!-- SPDX-FileCopyrightText: 2026 UnionTech Software Technology Co., Ltd.
SPDX-License-Identifier: GPL-3.0-or-later -->

# linuxdeepin 组织的 GitHub Copilot 指导

> **注意**: 这些是适用于 linuxdeepin 组织所有仓库的组织级默认指导。各个仓库可以使用特定仓库的指令来补充这些指导。

---

## 1. 双语代码审查评论

**要求**: 所有代码审查评论必须同时提供中英文双语版本。绝不能只使用英文。

### 格式模板

```
[English comment describing the issue or suggestion]

[Chinese comment - 对问题或建议的中文描述]
```

### 示例

```
This function should handle null inputs to prevent potential crashes.

此函数应处理空输入以防止潜在的崩溃。
```

---

## 2. SPDX 版权头验证

**要求**: 在审查代码更改时，自动检查 SPDX 版权头的日期格式是否正确。

### 所需格式

```cpp
// SPDX-FileCopyrightText: YYYY[-YYYY] UnionTech Software Technology Co., Ltd.
// SPDX-License-Identifier: <appropriate-license>
```

对于其他文件类型（如 CMake、Python、Shell 脚本）：

```cmake
# SPDX-FileCopyrightText: YYYY[-YYYY] UnionTech Software Technology Co., Ltd.
# SPDX-License-Identifier: <appropriate-license>
```

### 验证规则

#### 对于新文件

- **必须**包含带有当前年份的 SPDX 头

**示例:**
```cpp
// SPDX-FileCopyrightText: <当前年份> UnionTech Software Technology Co., Ltd.
// SPDX-License-Identifier: GPL-3.0-or-later
```

#### 对于修改的文件

**情况 1**: 文件在与修改相同的年份创建 → 使用单年份格式

```cpp
// SPDX-FileCopyrightText: <当前年份> UnionTech Software Technology Co., Ltd.
```

**情况 2**: 文件在更早的年份创建 → 使用年份范围格式 (YYYY-YYYY)

- 第一个 YYYY = 文件创建年份
- 第二个 YYYY = 最后修改年份

```cpp
// SPDX-FileCopyrightText: 2023-<当前年份> UnionTech Software Technology Co., Ltd.
```

**重要**: 只有当年份不同时才使用范围格式 (YYYY-YYYY)。如果年份相同，使用单年份格式。

### 检查内容

提醒开发者如果:

1. ❌ 新文件缺少 SPDX 头

2. ❌ 新文件的年份不正确（不是当前年份）

3. ❌ 修改的文件未将年份更新为当前年份

### 审查评论示例

```
Please update the SPDX copyright header to include the current year. Since this file
was created in 2023 and is being modified now, it should use the year range format:
// SPDX-FileCopyrightText: 2023-<当前年份> UnionTech Software Technology Co., Ltd.

请更新 SPDX 版权头以包含当前年份。由于此文件创建于 2023 年并在当前被修改，
应使用年份范围格式：
// SPDX-FileCopyrightText: 2023-<当前年份> UnionTech Software Technology Co., Ltd.
```

---

## 3. 双语提交消息格式

**要求**: 所有由 Copilot 生成的提交消息都必须遵循以下双语格式。

### 模板

```
<type>: <English summary>

<English detailed description>
- Key change 1
- Key change 2

Influence:
1. <Impact point 1>
2. <Impact point 2>
3. <Testing recommendation>

<type>: <中文摘要>

<中文详细描述>
- 关键变更 1
- 关键变更 2

Influence:
1. <影响点 1>
2. <影响点 2>
3. <测试建议>
```

### 提交类型

| Type | 描述 |
|------|------|
| `feat` | 新功能 |
| `fix` | 问题修复 |
| `docs` | 文档更改 |
| `style` | 代码风格/格式化 |
| `refactor` | 代码重构 |
| `perf` | 性能优化 |
| `test` | 测试添加/修改 |
| `chore` | 构建/工具变更 |

### 完整示例

参考来自 linuxdeepin/treeland 仓库：

```
fix: Correct typo in variable name from wpModle to wpModel

Fixed variable name typo throughout the codebase where "wpModle"
was incorrectly spelled instead of "wpModel". This change ensures
consistency in variable naming and improves code readability.
Additionally, temporarily disabled the smart cascaded placement
functionality by adding an early return statement for further
development.

The typo correction affects multiple workspace-related functions
including surface placement, preview management, and active surface
tracking. While the variable name change is purely cosmetic, the early
return in placeSmartCascaded indicates this feature is being reworked.

Influence:
1. Verify workspace surface management functions work correctly after
   variable name changes
2. Test surface placement and preview functionality
3. Check that active surface tracking operates as expected
4. Confirm no regression in workspace model operations

fix: 修正变量名拼写错误，将wpModle改为wpModel

修复了整个代码库中变量名拼写错误，"wpModle"被错误地拼写为"wpModel"。此更
改确保了变量命名的一致性并提高了代码可读性。此外，通过添加早期返回语句暂
时禁用了智能级联放置功能以便进一步开发。

拼写更正影响了多个工作区相关功能，包括表面放置、预览管理和活动表面跟踪。
虽然变量名称更改是纯外观上的，但placeSmartCascaded中的早期返回表明此功能
正在重新开发。

Influence:
1. 验证变量名称更改后工作区表面管理功能是否正常工作
2. 测试表面放置和预览功能
3. 检查活动表面跟踪是否按预期运行
4. 确认工作区模型操作没有回归
```

---

## 总结

这些指导确保：

1. ✅ 所有代码审查对英语和中文使用者都易于理解

2. ✅ 版权头得到正确维护并保持最新

3. ✅ 提交消息以两种语言提供全面的上下文

通过遵循这些指导，我们在所有 linuxdeepin 项目中保持一致性和清晰度。
