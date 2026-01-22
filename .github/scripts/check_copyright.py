# SPDX-FileCopyrightText: 2026 UnionTech Software Technology Co., Ltd.
#
# SPDX-License-Identifier: CC0-1.0
import sys
import datetime
import os
import re

def main():
    # 获取环境变量中的关键字
    target_str = os.getenv("TARGET_COMPANY", "")
    targets = [t.strip() for t in target_str.split(";") if t.strip()]
    current_year = str(datetime.datetime.now().year)
    
    # 获取变动文件列表（从命令行参数传入）
    changed_files = sys.argv[1:]
    # 规范化路径，去掉开头的 ./ 方便对比
    changed_files = {f.lstrip("./") for f in changed_files}

    # 读取 stdin (reuse spdx 的输出)
    spdx_output = sys.stdin.read()
    
    # 按照 FileName 分割块
    blocks = spdx_output.split("FileName: ")
    failed_entries = []

    for block in blocks[1:]:  # 第一个分割块通常是文档头，跳过
        lines = block.splitlines()
        if not lines:
            continue
            
        file_path = lines[0].strip().lstrip("./")
        
        # 只检查本次 PR 变动的文件
        if file_path not in changed_files:
            continue

        # REUSE-IgnoreStart
        # 使用正则提取 FileCopyrightText: <text>...</text> 之间的内容
        # 因为版权信息可能跨越多行
        match = re.search(r"FileCopyrightText: <text>(.*?)</text>", block, re.DOTALL)
        # REUSE-IgnoreEnd
        if match:
            copyright_content = match.group(1).strip()
            cp_lines = copyright_content.splitlines()
            
            for line in cp_lines:
                for target in targets:
                    # 如果这一行包含目标字符串，但没包含当前年份
                    if target in line and current_year not in line:
                        failed_entries.append({
                            "file": file_path,
                            "line": line.strip(),
                            "expected": current_year
                        })

    # 输出结果供 GitHub Step Summary 使用
    if failed_entries:
        # REUSE-IgnoreStart
        print("### Copyright Year Check Failed")
        print(f"The following files contain specific companies but are missing the current year (**{current_year}**):")
        print("| File | Copyright Line |")
        print("| :--- | :--- |")
        # REUSE-IgnoreStart
        for entry in failed_entries:
            print(f"| `{entry['file']}` | `{entry['line']}` |")
        sys.exit(1)
    else:
        pass

if __name__ == "__main__":
    main()