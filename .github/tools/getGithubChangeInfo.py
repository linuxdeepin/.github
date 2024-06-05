import requests
import os
import json
import sys

def getHeaders(access_token):
    # 设置头信息，包括使用access token进行认证
    headers = {
        "Authorization": f"Bearer {access_token}",
        "X-GitHub-Api-Version": "2022-11-28",
        "Accept": "application/vnd.github+json" 
    }
    return headers

# 获取两次提交之间的差异
def get_commit_diff(repo, commit_sha1, commit_sha2, token):
    url = f'https://api.github.com/repos/{repo}/compare/{commit_sha1}...{commit_sha2}'
    response = requests.get(url, headers=getHeaders(token))
    return response.json()
 
# 获取指定commit的文件列表
def get_commit_info(repo, commit_sha, token):
    url = f'https://api.github.com/repos/{repo}/commits/{commit_sha}'
    response = requests.get(url, headers=getHeaders(token))
    return response.json()

# 获取指定pr信息
def get_pull_info(repo, pull_number, token):
    url = f'https://api.github.com/repos/{repo}/pulls/{pull_number}'
    print(f'apiurl is {url}')
    response = requests.get(url, headers=getHeaders(token))
    # print(f"response is {response.json()}")
    # writeJson(response.json(), 'r.json')
    return response.json()

# 获取指定pr的commit信息
def get_pull_commit_info(repo, pull_number, token):
    url = f'https://api.github.com/repos/{repo}/pulls/{pull_number}/commits'
    print(f'apiurl is {url}')
    response = requests.get(url, headers=getHeaders(token))
    # print(f"response is {response.json()}")
    return response.json()

def get_pulls_files(repo, pull_number, token):
    url = f'https://api.github.com/repos/{repo}/pulls/{pull_number}/files'
    print(f'apiurl is {url}')
    response = requests.get(url, headers=getHeaders(token))
    # print(f"response is {response.json()}")
    if response.status_code == 200:
        return response.json()
    else:
        print(response.json())

# 获取commit的run链接地址
def get_ref_runs(repo, commitSHA, token, job_name):
    url = f'https://api.github.com/repos/{repo}/commits/{commitSHA}/check-runs'
    print(f'apiurl is {url}')
    response = requests.get(url, headers=getHeaders(token))
    if response.status_code == 200:
        writeJson(response.json(), 'r.json')
        for jobInfo in response.json()['check_runs']:
            if jobInfo['name'] == job_name:
                return jobInfo['html_url']
    else:
        print(response.json())

def get_repo_languages(repo, token):
    url = f'https://api.github.com/repos/{repo}/languages'
    # print(f'apiurl is {url}')
    response = requests.get(url, headers=getHeaders(token))
    if response.status_code == 200:
        print(list(response.json().keys())[0])
    else:
        print(response.json())
# 写json文件
def writeJson(originInfo, logFile, infoType=dict):
    with open(logFile, "w+") as fout:
        if isinstance(originInfo, infoType):
            fout.write(json.dumps(originInfo, indent=4, ensure_ascii=False))
            
# 写文件
def writeFile(originInfo, logFile, infoType=str):
    with open(logFile, "a+") as fout:
        if isinstance(originInfo, infoType):
            fout.write(originInfo+'\n')

def get_pr_files(repo, pull_number, token):
    try:
        originInfo = {}
        
        pfInfo = get_pulls_files(repo, pull_number, token)

        for fileTemp in pfInfo:
            originInfo[fileTemp['filename']] = {
                "a": [],
                "b": []
            }
            filePatch = fileTemp['patch']
            fileContent = filePatch.splitlines()
            for line in fileContent:
                if line.startswith("-"):
                    originInfo[fileTemp['filename']]["a"].append(line.lstrip("-"))
                elif line.startswith("+"):
                    originInfo[fileTemp['filename']]["b"].append(line.lstrip("+"))
                    
        # writeJson(originInfo)
        return originInfo
    except Exception as e:
        print(f"[ERR]: get_pr_files异常报错-{e}")


def get_change_files(repo, pull_number, token):
    try:
        originInfo = {}
        originInfoStr = ''
        pfInfo = get_pulls_files(repo, pull_number, token)
        for fileTemp in pfInfo:
            originInfo[fileTemp['filename']] = fileTemp['status']
            originInfoStr += fileTemp['filename'] + ':' + fileTemp['status'] + '\n'
            # writeFile(originInfo)
        print(originInfoStr)
        return originInfo
    except Exception as e:
        print(f"[ERR]: 异常报错-{e}")
        

# 在增加和修改内容中筛选敏感词
# checkType: 1, 在增加和修改内容筛选敏感词
def filter_keys_type1(content, keyLst):
    strJson = {}
    for fileName, patchContent in content.items():
        for lineContent in patchContent['b']:
            for keyStr in keyLst:
                if keyStr in lineContent:
                    if keyStr not in list(strJson.keys()):
                        strJson[keyStr] = {}
                    if fileName not in list(strJson[keyStr].keys()):
                        strJson[keyStr][fileName] = []
                    strJson[keyStr][fileName].append(lineContent)
    return strJson

# 在增加，删除和修改内容中筛选敏感词
# checkType: 2, 在修改,删除和增加内容筛选敏感词
def filter_keys_type2(content, keyLst):
    strJson = {}
    for fileName, patchContent in content.items():
            for keyStr in keyLst:
                for actionType, actionTypePatchConten in patchContent.items():
                    for lineContent in actionTypePatchConten:
                        if keyStr in lineContent:
                            if keyStr not in list(strJson.keys()):
                                strJson[keyStr] = {}
                            if fileName not in list(strJson[keyStr].keys()):
                                strJson[keyStr][fileName] = {}
                            if actionType not in list(strJson[keyStr][fileName].keys()):
                                strJson[keyStr][fileName][actionType] = []
                            strJson[keyStr][fileName][actionType].append(lineContent)
    return strJson

def filter_keywords(repo, pull_number, token, keyLst, excludeSuffLst, logFile, checkType):
    content = get_pr_files(repo, pull_number, token)
    originInfo = {}
    with open(logFile, "w+") as fout:
        if isinstance(content, dict):
            if len(excludeSuffLst) != 0:
                for suffStr in excludeSuffLst:
                    for fileName in list(content.keys()):
                        if fileName.endswith(suffStr):
                            content.pop(fileName)
            if checkType == '1':
                originInfo = filter_keys_type1(content, keyLst)
            if checkType == '2':
                originInfo = filter_keys_type2(content, keyLst)
        fout.write(json.dumps(originInfo, indent=4, ensure_ascii=False))
    return originInfo

if __name__ == '__main__':
    repo = sys.argv[1]
    token = sys.argv[2]
    get_repo_languages(repo, token)