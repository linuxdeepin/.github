# SPDX-FileCopyrightText: 2026 UnionTech Software Technology Co., Ltd.
# SPDX-License-Identifier: GPL-3.0-or-later
"""Prepare only the 17 G2 members from the merged, trusted dde configuration."""

import copy
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from urllib.parse import quote, urlencode

import yaml


sys.path.insert(0, str(Path(os.environ.get("COORDINATOR_DIR", "coordinator")) /
                       ".github/scripts"))
from release_line_checks import (  # noqa: E402
    GUARD_CONTEXT, SHA_RE, WORKFLOW_FILES, ReadinessError, _enabled, _matches,
    api, branch_info, check_member_ready, check_member_workflows,
    check_workflow_file, content, g2_members, protection_ready, read_protection, release_lines,
    release_app_id,
)


def _ancestors(api, repo, base, head):
    value = api(f"repos/{repo}/compare/{base}...{head}")
    if value["merge_base_commit"]["sha"].lower() != base.lower():
        raise RuntimeError(f"{repo} 目标分支不包含基准 {base}，禁止 force/reset/delete")


def _wait_branch(api, repo, branch, attempts=10):
    for _ in range(attempts):
        target = branch_info(api, repo, branch, missing=True)
        if target:
            return target
        time.sleep(1)
    raise RuntimeError(f"{repo}:{branch} 创建后未可读")


def _installation_repositories(api):
    result, page = set(), 1
    while True:
        value = api(f"installation/repositories?per_page=100&page={page}")
        if (not isinstance(value, dict) or type(value.get("total_count")) is not int
                or value["total_count"] < 0 or not isinstance(value.get("repositories"), list)):
            raise RuntimeError("当前 App 仓库范围响应无法确认")
        entries = value["repositories"]
        if any(not isinstance(repo, dict) or not isinstance(repo.get("full_name"), str)
               or not repo["full_name"] for repo in entries):
            raise RuntimeError("当前 App 仓库范围条目无法确认")
        names = {repo["full_name"] for repo in entries}
        if len(names) != len(entries) or result & names:
            raise RuntimeError("当前 App 仓库范围分页重复，请重跑")
        result.update(names)
        if len(result) == value["total_count"]:
            return result
        if not entries or len(result) > value["total_count"]:
            raise RuntimeError("当前 App 仓库范围分页不完整，请重跑")
        page += 1


def _creation_rules(api, repo):
    owner, name = repo.split("/")
    result, cursor = [], None
    while True:
        value = api("graphql", {"query": """
          query($owner:String!, $name:String!, $cursor:String) {
            repository(owner:$owner, name:$name) {
              branchProtectionRules(first:100, after:$cursor) {
                nodes {
                  pattern blocksCreations restrictsPushes
                  pushAllowances(first:100) {
                    totalCount nodes { actor { __typename ... on App { databaseId } } }
                  }
                }
                pageInfo { hasNextPage endCursor }
              }
            }
          }""", "variables": {"owner": owner, "name": name, "cursor": cursor}})
        rules = value["data"]["repository"]["branchProtectionRules"]
        result.extend(rules["nodes"])
        if not rules["pageInfo"]["hasNextPage"]:
            return result
        cursor = rules["pageInfo"]["endCursor"]
        if not cursor:
            raise RuntimeError(f"{repo} 创建权限分页不可确认")


def _may_create(api, repo, branch, app_id, rules):
    for rule in rules:
        if not _matches(rule["pattern"], branch):
            continue
        if rule.get("blocksCreations") is None or rule.get("restrictsPushes") is None:
            raise RuntimeError(f"{repo}:{branch} 创建保护权限未知")
        if rule["blocksCreations"] and rule["restrictsPushes"]:
            allowances = rule["pushAllowances"]
            if allowances["totalCount"] != len(allowances["nodes"]) or not any(
                    node.get("actor") and node["actor"].get("__typename") == "App"
                    and node["actor"].get("databaseId") == app_id for node in allowances["nodes"]):
                raise RuntimeError(f"{repo}:{branch} 当前 App 未获受限分支创建权限")
    effective = api(f"repos/{repo}/rules/branches/{quote(branch, safe='')}?per_page=100",
                    paginate=True)
    if not isinstance(effective, list):
        raise RuntimeError(f"{repo}:{branch} 有效创建规则不可读取")
    for rule in effective:
        if rule.get("type") != "creation":
            continue
        value = api(f"repos/{repo}/rulesets/{rule['ruleset_id']}?includes_parents=true")
        actors = value.get("bypass_actors")
        if value.get("enforcement") != "active" or not isinstance(actors, list) or not any(
                actor.get("actor_type") == "Integration" and actor.get("actor_id") == app_id
                and actor.get("bypass_mode") == "always" for actor in actors):
            raise RuntimeError(f"{repo}:{branch} 当前 App 创建权限被有效规则限制或不可确认")


def _templates(template_root, api, repo, branches):
    config = Path(template_root) / "repos" / (repo + ".json")
    entries = json.loads(config.read_text(encoding="utf-8"))
    result = {}
    for filename in WORKFLOW_FILES:
        dest = f"{repo}/.github/workflows/{filename}"
        matches = [entry for entry in entries if entry.get("dest") == dest]
        if len(matches) != 1:
            raise RuntimeError(f"{config}: 必须有唯一 {filename} 配置")
        entry = matches[0]
        patterns = entry.get("branches")
        if not isinstance(patterns, list) or not patterns or entry.get("deletelist"):
            raise RuntimeError(f"{config}: {filename} 必须用 branches 显式覆盖，不能删除入口")
        if any(not any(re.match("^" + pattern, branch) for pattern in patterns) for branch in branches):
            raise RuntimeError(f"{config}: {filename} 未覆盖默认/目标分支")
        if entry.get("src") != f"workflow-templates/{filename}":
            raise RuntimeError(f"{config}: 必须复用现有 {filename} 模板")
        result[filename] = (Path(template_root) / entry["src"]).read_text(encoding="utf-8")
        for branch in branches:
            check_workflow_file(api, repo, filename, "trusted-template", branch,
                                text=result[filename])
    return result


def _actors(value):
    if value is None:
        return None
    return {kind: [actor if isinstance(actor, str) else actor["login" if kind == "users" else "slug"]
                   for actor in value.get(kind, [])] for kind in ("users", "teams", "apps")}


def protection_payload(target, default, app_id):
    """Preserve review policy/check bindings; add only the required restrictions."""
    source = target["classic"] if target["classic"] is not None else default["classic"] or {}
    reviews = source.get("required_pull_request_reviews")
    if reviews is None and target["classic"] is not None:
        reviews = (default["classic"] or {}).get("required_pull_request_reviews")
    reviews = copy.deepcopy(reviews or {})
    reviews.pop("url", None)
    if "dismissal_restrictions" in reviews:
        reviews["dismissal_restrictions"] = _actors(reviews["dismissal_restrictions"])
    reviews["bypass_pull_request_allowances"] = {"users": [], "teams": [], "apps": []}
    reviews.setdefault("required_approving_review_count", 0)
    reviews.setdefault("dismiss_stale_reviews", False)
    reviews.setdefault("require_code_owner_reviews", False)
    reviews.setdefault("require_last_push_approval", False)
    checks = {}
    status = source.get("required_status_checks") or {}
    for check in status.get("checks", []):
        checks[check["context"]] = check.get("app_id") if check.get("app_id") is not None else -1
    for context in status.get("contexts", []):
        checks.setdefault(context, -1)
    policy_rules = target["rules"] + (default["rules"] if target["classic"] is None else [])
    for rule in policy_rules:
        parameters = rule.get("parameters", {})
        if rule["type"] == "pull_request":
            reviews["required_approving_review_count"] = max(
                reviews["required_approving_review_count"], parameters.get("required_approving_review_count", 0))
            for field in ("dismiss_stale_reviews_on_push", "require_code_owner_review",
                          "require_last_push_approval"):
                dest = {"dismiss_stale_reviews_on_push": "dismiss_stale_reviews",
                        "require_code_owner_review": "require_code_owner_reviews"}.get(field, field)
                if parameters.get(field):
                    reviews[dest] = True
        if rule["type"] == "required_status_checks":
            for check in parameters.get("required_status_checks", []):
                name, binding = check["context"], check.get("integration_id") or -1
                if name != GUARD_CONTEXT and name in checks and checks[name] != binding:
                    raise RuntimeError(f"同一必需检查 {name} 有冲突 App 绑定，不能覆盖现有规则")
                checks[name] = binding
    checks[GUARD_CONTEXT] = app_id
    payload = {
        "required_status_checks": {"strict": True, "checks": [
            {"context": context, "app_id": binding} for context, binding in checks.items()]},
        "required_pull_request_reviews": reviews,
        "enforce_admins": True,
        "restrictions": _actors(source.get("restrictions")),
        "allow_force_pushes": False,
        "allow_deletions": False,
    }
    for name in ("required_linear_history", "block_creations", "required_conversation_resolution",
                 "lock_branch", "allow_fork_syncing"):
        if name in source:
            payload[name] = _enabled(source, name)
    return payload


def verify_preserved(actual, expected, app_id):
    normalized = protection_payload(actual, {"classic": None, "rules": []}, app_id)
    for key, value in expected.items():
        if key == "required_status_checks":
            observed = {(check["context"], check["app_id"])
                        for check in normalized[key]["checks"]}
            if not all((check["context"], check["app_id"]) in observed for check in value["checks"]):
                raise ReadinessError("PROTECTION_FAILED", "读回丢失了已有必需检查或 App 绑定")
        elif normalized.get(key) != value:
            raise ReadinessError("PROTECTION_FAILED", f"保护读回未保留 {key}")


def sync_templates(api, owner):
    """Run the existing organization template sync and wait for its result."""
    repo = f"{owner}/.github"
    default = api(f"repos/{repo}")["default_branch"]
    query = urlencode({"branch": default, "event": "workflow_dispatch", "per_page": 20})
    previous = {run["id"] for run in
                api(f"repos/{repo}/actions/workflows/templates-sync.yml/runs?{query}")["workflow_runs"]}
    api(f"repos/{repo}/actions/workflows/templates-sync.yml/dispatches",
        {"ref": default}, method="POST")
    deadline = time.monotonic() + 900
    while time.monotonic() < deadline:
        runs = api(f"repos/{repo}/actions/workflows/templates-sync.yml/runs?{query}")["workflow_runs"]
        run = next((item for item in runs if item["id"] not in previous), None)
        if run and run["status"] == "completed":
            if run["conclusion"] != "success":
                raise RuntimeError(f"模板同步失败: {run['html_url']}")
            return run
        time.sleep(5)
    raise RuntimeError("模板同步超时，请查看 templates-sync 工作流")


def _report(rows):
    lines = ["| 成员 | 分支预检 | 实际状态 | 说明/待合并 PR |",
             "|---|---|---|---|"]
    for row in rows:
        lines.append(f"| {row['repo']} | {row['operation']} | {row.get('state', '预检')} | "
                     f"{row.get('detail', '').replace('|', '/').replace(chr(10), ' ')} |")
    text = "\n".join(lines) + "\n"
    print(text)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as summary:
            summary.write(text)


def prepare(api, coordinator, config_sha, template_root, line, dry_run=True,
            can_create=False, app_id=None, admin_write=False):
    info = api(f"repos/{coordinator}")
    current = branch_info(api, coordinator, info["default_branch"])["commit"]["sha"]
    if not isinstance(config_sha, str) or not SHA_RE.fullmatch(config_sha):
        raise RuntimeError("Prepare 必须从可信 dde 默认分支 checkout 的固定 SHA 读配置")
    _ancestors(api, coordinator, config_sha, current)
    cfg = yaml.safe_load(content(api, coordinator, "groups.yaml", config_sha))
    lines = release_lines(cfg)
    if line == "master" or line not in lines:
        raise RuntimeError("Prepare 只接受已合并的新增 G2 develop 发布线")
    members = g2_members(cfg, coordinator.split("/")[0])
    branch, bases = lines[line]["member_branch"], lines[line].get("bases")
    if not isinstance(bases, dict) or set(bases) != {member for member, _ in members}:
        raise RuntimeError("已合并 bases 必须恰好包含 17 个 G2 成员")
    if not can_create or type(app_id) is not int:
        raise RuntimeError("当前 App 的 Contents/Workflows/PR 写权限或身份不可确认")
    # App tokens omit permissions.push; the trusted workflow requests write grants.
    installed = _installation_repositories(api)
    rows = []
    for member, repo in members:
        row = {"repo": repo, "member": member, "operation": "conflict"}
        rows.append(row)
        try:
            sha = bases[member]
            if not isinstance(sha, str) or not SHA_RE.fullmatch(sha):
                raise RuntimeError("基准不是完整 40 字符 commit SHA")
            if repo not in installed:
                raise RuntimeError("成员仓库不在当前 App 令牌的授权范围")
            member_info = api(f"repos/{repo}")
            if member_info.get("archived") is not False or member_info.get("disabled") is not False:
                raise RuntimeError("仓库归档、禁用或状态不可确认")
            commit = api(f"repos/{repo}/git/commits/{sha}")
            if commit.get("sha", "").lower() != sha.lower():
                raise RuntimeError("基准 commit 不在对应成员仓库中")
            target = branch_info(api, repo, branch, missing=True)
            if target:
                _ancestors(api, repo, sha, target["commit"]["sha"])
                read_protection(api, repo, branch, target)
            default = member_info["default_branch"]
            read_protection(api, repo, default)
            create_rules = _creation_rules(api, repo)
            if not target:
                _may_create(api, repo, branch, app_id, create_rules)
            row.update(operation="existing" if target else "create", base=sha, default=default,
                       templates=_templates(template_root, api, repo, (default, branch)))
        except Exception as error:
            row.update(operation="conflict", detail=str(error))
    _report(rows)
    if any(row["operation"] == "conflict" for row in rows):
        raise RuntimeError("全部成员预检未通过；未创建任何分支、同步模板或保护")
    if dry_run:
        for row in rows:
            try:
                if row["operation"] == "create":
                    raise ReadinessError("BRANCH_MISSING", f"将从固定基准 {row['base']} 创建")
                if any(content(api, row["repo"], f".github/workflows/{name}", base, missing=True) != text
                       for base in dict.fromkeys((row["default"], branch))
                       for name, text in row["templates"].items()):
                    raise ReadinessError("TEMPLATE_MISSING", "正式运行将调用统一模板同步")
                check_member_ready(api, row["repo"], branch, app_id)
                row["state"] = "READY"
            except ReadinessError as error:
                row.update(state=error.state, detail=str(error))
            except Exception as error:
                row.update(state="PROTECTION_FAILED", detail=str(error))
        _report(rows)
        return rows
    live_cfg = yaml.safe_load(content(api, coordinator, "groups.yaml",
                                     branch_info(api, coordinator, info["default_branch"])["commit"]["sha"]))
    if release_lines(live_cfg).get(line) != lines[line] or g2_members(live_cfg, coordinator.split("/")[0]) != members:
        raise RuntimeError("已审核的分支/bases/成员配置在预检期间改变，请重跑")
    for row in rows:
        try:
            target = branch_info(api, row["repo"], branch, missing=True)
            if target is None:
                try:
                    api(f"repos/{row['repo']}/git/refs", {"ref": f"refs/heads/{branch}", "sha": row["base"]})
                except RuntimeError:
                    target = branch_info(api, row["repo"], branch, missing=True)
                    if target is None:
                        raise
                target = _wait_branch(api, row["repo"], branch)
            _ancestors(api, row["repo"], row["base"], target["commit"]["sha"])
        except Exception as error:
            row.update(operation="conflict", detail=str(error))
            _report(rows)
            raise RuntimeError("分支创建中断；保留所有已创建分支，重跑只补缺失项") from error
    if any(content(api, row["repo"], f".github/workflows/{name}", base, missing=True) != text
           for row in rows for base in dict.fromkeys((row["default"], branch))
           for name, text in row["templates"].items()):
        sync_templates(api, coordinator.split("/")[0])
    for row in rows:
        try:
            target = branch_info(api, row["repo"], branch)
            _ancestors(api, row["repo"], row["base"], target["commit"]["sha"])
        except Exception as error:
            row.update(operation="conflict", detail=str(error))
            _report(rows)
            raise RuntimeError("模板同步后目标分支不再包含固定基准，请人工核实") from error
    for row in rows:
        state = "TEMPLATE_MISSING"
        try:
            repo = row["repo"]
            state = "WORKFLOW_INACTIVE"
            for filename in WORKFLOW_FILES:
                workflow = api(f"repos/{repo}/actions/workflows/{filename}", missing=True)
                if workflow and workflow.get("state") in ("disabled_manually", "disabled_inactivity"):
                    api(f"repos/{repo}/actions/workflows/{filename}/enable", method="PUT")
            check_member_workflows(api, repo, branch)
            state = "PROTECTION_FAILED"
            app_source = release_app_id(app_id)
            target = read_protection(api, repo, branch)
            if not protection_ready(target, app_source):
                default = read_protection(api, repo, row["default"])
                latest_target = read_protection(api, repo, branch)
                latest_default = read_protection(api, repo, row["default"])
                if latest_target != target:
                    raise ReadinessError(state, "分支保护在预检后发生变化，请重跑 Prepare")
                payload = protection_payload(latest_target, latest_default, app_source)
                if not admin_write:
                    raise ReadinessError(state, f"{repo} App 无 Admin Write；管理员保留现有审核/检查并配置"
                                         f"保护后重跑: https://github.com/{repo}/settings/branches")
                api(f"repos/{repo}/branches/{quote(branch, safe='')}/protection", payload, method="PUT")
                observed = read_protection(api, repo, branch)
                verify_preserved(observed, payload, app_source)
            check_member_ready(api, repo, branch, app_id)
            target = branch_info(api, repo, branch)
            _ancestors(api, repo, row["base"], target["commit"]["sha"])
            row.update(state="READY", detail="已读回验证入口、workflow 启用与实际有效保护")
        except ReadinessError as error:
            row.update(state=error.state, detail=str(error))
        except Exception as error:
            row.update(state=state, detail=str(error))
    _report(rows)
    if any(row["state"] != "READY" for row in rows):
        raise RuntimeError("G2 尚未全部 READY；修复模板同步或保护配置后重跑 Prepare")
    return rows


if __name__ == "__main__":
    coordinator_dir = Path(os.environ.get("COORDINATOR_DIR", "coordinator"))
    sha = subprocess.check_output(["git", "-C", str(coordinator_dir), "rev-parse", "HEAD"],
                                  text=True).strip()
    prepare(api, os.environ["GITHUB_REPOSITORY_OWNER"] + "/dde", sha, Path.cwd(),
            os.environ["RELEASE_LINE"], os.environ.get("DRY_RUN", "true").lower() == "true",
            os.environ.get("CAN_CREATE_BRANCH") == "true", int(os.environ["APP_ID"]),
            os.environ.get("ADMIN_WRITE") == "true")
