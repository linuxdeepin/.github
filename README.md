# .github

The github tools

## 同步模板文件

同步模板文件到组织的所有仓库中, 可以修改 repos 目录下的配置文件, [文档](https://github.com/linuxdeepin/action-sync)

## 开关仓库功能

开启或关闭仓库功能, 如 wiki/project/issue, 可以修改 organization.yaml, [文档](https://github.com/linuxdeepin/action-organization-manager)

## 团队

添加成员, 添加关联的仓库、项目并修改权限,可以修改 teams.yaml, [文档](https://github.com/linuxdeepin/action-teams-manager)

## 静态代码检查

开启或关闭仓库功能, 如 wiki/project/issue, 可以修改 organization.yaml, [文档](https://github.com/linuxdeepin/action-cppcheck)

## 工作流模板

### backup-to-gitlab

备份仓库到gitee和内网的gitlab

### call-build-deb

编译构建检查

### call-chatOps

合并机器人

### call-commitlint

commit信息检查

### cppcheck

cpp代码静态检查

### call-verify-group-version

校验 DDE 组成员 PR 的 `debian/changelog` 版本。普通代码 PR 不改版本时通过；改版 PR 须匹配
同组织 `dde` 仓库的原始发布记录，包括完整成员目标版本、成员仓库、自动化分支、目标分支和 PR 创建时间。
组目标不带 epoch；G2 成员保留现有 epoch，去掉 epoch 后须与组目标一致。
首轮成员起始版本可以不同，完整目标仍须高于当前版本。
缺少成员版本字段的旧记录继续按原组目标校验，不改变已有发布。
旧 epoch 组基线完成后，新记录按不带 epoch 的组版本判断是否过期，成员仍校验完整目标。

成员使用 `workflow-templates/call-verify-group-version.yml`，通过 `pull_request_target` 调用
`verify-group-version.yml`。工作流只读取 PR 文件，不检出或执行 PR 代码；使用本仓库的
`GITHUB_TOKEN` 把 `group-version-guard` 状态写到 PR 的 head 提交，不需要 GitHub App Secret。

`repos/linuxdeepin/*.json` 已为 25 个组成员配置此模板。dtk6log 已归档，其模板同步配置停用。
上线前先完成成员首用准备，包括 go-lib 的发布入口；合入共享工作流和模板配置，
确认成员入口安装完成后上线 DDE 协调器。带 epoch 的新发布须等协调器与成员校验均更新后触发。
默认分支上的入口文件接入后，给所有成员发布目标分支
启用 `group-version-guard` 必需检查，来源选择 GitHub Actions；同时要求 PR、分支保持最新，
禁止直接推送、强推和绕过。工作流本身不能阻止未受保护分支上的直接推送。

成员启用保护后，后续模板更新须通过 PR 合入；自动创建模板 PR 的工具升级另行安排，也可手工创建 PR。
模板同步和发布机器人均不配置保护绕过。
最终关联 PR 列表或 PR 状态查询失败时，guard 发布失败状态，工作流同时失败；不会沿用之前的成功结果。
版本校验后会保存 PR 的提交、来源和目标分支；发布成功状态前再次核对开放 PR 集合和这些身份。
校验期间改投目标或出现其他 PR 变化时，本次结果写为失败，等待新事件重新检查。
