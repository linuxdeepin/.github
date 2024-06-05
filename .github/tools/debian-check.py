import getGithubChangeInfo
import os

# debian检查下仓库白名单
exProjectLstForDebian = ["dev-ops-jenkins-shared-library", "dev-ops-pipeline-tools", "gerrit-pipeline", "gerrit-utp-pipeline"]
# debian前缀检查文件白名单
exFilesLstForDebian = ["debian/changelog", "debian/copyright", "debian/compat", "debian/source/format"]
# 敏感词检查文件后缀白名单
exSuffLstForKeys = ['js','vue','ts','less','html','go','css','json','txt','doc','jpg','png','svg','py','yml','md']
# 环境设置敏感词检查仓库白名单
exProjectLstForEnvKeys = ["deviceos/oem/base/agent", "deviceos/oem/gw/oem", "deviceos/oem/html/oem", "deviceos/oem/html/oemadmin"]

# debian前缀检查
def debianPreCheck(repo, pull_number, token):
    resulyJson = getGithubChangeInfo.get_change_files(repo, pull_number, token)
    # NoNeedDebianExpFiles = [ "debian/patches/*","debian/manpage.*", "debian/*.manpages"]
    resultLst = []
    for fileName in resulyJson:
      # print(f'file is {file}')
      if fileName.startswith("debian/"):
        needCheckStatus = True
        if fileName in exFilesLstForDebian:
          if fileName == 'debian/changelog':
            debianVersionCheck(repo, token)
          needCheckStatus = False
        if fileName.startswith('debian/patches/') or fileName.startswith('debian/manpage.'):
          needCheckStatus = False
        if fileName.endswith('.manpages'):
          needCheckStatus = False
        if needCheckStatus:
          resultLst.append(fileName)
    if resultLst:
      writeCommentFile(f"[FAIL]: debian前缀检查不通过{resultLst}")
      exit(1)
    else:
      print("[PASS]: debian前缀检查通过")

# 敏感词检查
def debianKeyWordsCheck(repo, pull_number, token, keyLst, logFile):
  # checkType: 1, 在增加和修改内容筛选敏感词
  # checkType: 2, 在修改,删除和增加内容筛选敏感词
  try:
    checkType = '1'
    showStr = ''
    if 'export' in keyLst:
      if repo in exProjectLstForEnvKeys:
        exit(0)
      checkType = '2'
      showStr = '环境设置'
    resulyJson = getGithubChangeInfo.filter_keywords(repo, pull_number, token, keyLst, exSuffLstForKeys, logFile, checkType)
    # showStr = '环境设置' if 'export' in keyLst else ''
    if resulyJson:
      writeCommentFile(f"[FAIL]: {showStr}敏感词检查不通过{list(resulyJson.keys())}")
      exit(1)
    else:
      print(f"[PASS]: {showStr}敏感词检查通过")
  except Exception as e:
    writeCommentFile(f"[ERR]: {showStr}异常报错-{e}")
    exit(1)
    
# debian/changelog版本检查
def debianVersionCheck():
    with os.popen("dpkg-parsechangelog -l debian/changelog -n 2 | awk -F'[()]' '{print $2}'|grep -v '^$\|^Task\|^Bug\|^Influence'|awk -F'-' '{print $1}'") as fin:
      versionLst = fin.readlines()
      if len(versionLst) == 2:
        version0 = versionLst[0].rstrip('\n')
        version1 = versionLst[1].rstrip('\n')
        if os.system(f'dpkg --compare-versions {version0} gt {version1}') == 0:
          print(f'[PASS]: 版本检查通过:{version0}|{version1}')
        else:
          writeCommentFile(f'[FAIL]: 版本检查不通过:{version0}|{version1}')
          exit(1)
      else:
        if len(versionLst) != 1:
          writeCommentFile(f'[ERR]: 版本检查异常:{versionLst}')
          exit(1)
        else:
          print(f'[PASS]: 版本检查通过:{versionLst}')

# 写comment文件
def writeCommentFile(commentMsg):
  try:
    print(commentMsg)
    with open('comment.txt', "a+") as fout:
      fout.write(commentMsg+'\n')
  except Exception as e:
    print(f"[ERR]: writeCommentFile异常报错-{e}")

# 写comment文件第一行run链接
def writeHeadToCommentFile(filename, content):
    temp_filename = filename + '.tmp']
    # 写入新内容到临时文件
    with open(temp_filename, 'w', encoding='utf-8') as temp_file:
        temp_file.write(content + '\n')
    # 追加原始文件的内容到临时文件
    with open(filename, 'r', encoding='utf-8') as original_file, open(temp_filename, 'a', encoding='utf-8') as temp_file:
        temp_file.writelines(original_file)
    os.replace(temp_filename, filename)

# 检查完成后处理comment文件
def postStep(repo, token, sha, job_name):
    if os.path.isfile('comment.txt'):
      with open('comment.txt', 'r', encoding='utf-8') as commentFile:
        lines = commentFile.readlines()
        html_url = getGithubChangeInfo.get_ref_runs(repo, sha, token, job_name)
        if f"Debian检查:{html_url}" not in lines:
          writeHeadToCommentFile(f"Debian检查:{html_url}", 'comment.txt')

# 检查开始前过滤debian项目
def preStep(repo):
  if type == 'debian-check':
    if repo.startswith('autotest_') or repo in exProjectLstForDebian:
      exit(0)

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--type", required=True, help="检查类型")
    # parser.add_argument("--repo", required=True, help="所有者和存储库名称。 例如, octocat/Hello-World")
    # parser.add_argument("--pr", required=True, help="pr number")
    # parser.add_argument("--token", required=True, help="github access token")
    parser.add_argument("--keys", required=False, help="查询关键字，逗号分隔")
    # parser.add_argument("--exclude", required=False, help="不进行敏感词筛选的文件后缀")
    parser.add_argument("--log", required=False, help="输出日志文件名")
    # parser.add_argument("--ref", required=False, help="commit sha")
    args = parser.parse_args()

    repository = os.getenv('repository')
    pull_number = os.getenv('pull_number')
    access_token = os.getenv('access_token')
    job_name = os.getenv('job_name')
    # exclude_files = os.getenv('exclude_files')
    head_ref= os.getenv('head_ref')
    ref_type = os.getenv('ref_type')
    sha = 'heads/'+head_ref if ref_type == 'branch' else ''
    
    preStep(repository)
    if args.type == 'pre-check':
      # head_ref = args.ref if args.ref else ''
      debianPreCheck(repository, pull_number, access_token)
    elif args.type == 'keys-check':
      keyLst = args.keys.split(",") if args.keys else []
      # excludeSuffLst = exclude_files.split(',') if exclude_files else []
      # excludeSuffLst = args.exclude.split(',') if args.exclude else []
      logFile = args.log if args.log else 'githubResult.json'
      debianKeyWordsCheck(repository, pull_number, access_token, keyLst, logFile)
    postStep(repository, access_token, sha, job_name)