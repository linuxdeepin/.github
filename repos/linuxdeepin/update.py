#!/usr/bin/python3
import json
with open('need-update','r') as f: #将你需要更新的项目放在 need-update 文件中
    jsons=f.readlines()

for i in jsons:
    with open(i.strip('\n'),'r') as f:
        data=json.load(f)
    addJson=data[0].copy()
    addJson['src']="workflow-templates/call-license-check.yml" #替换为自己需要的路径
    dest=addJson['dest'].split("/")
    dest[-1]="call-license-check.yml" #替换为自己的yaml文件
    dest="/".join(dest)
    addJson['dest']=dest
    data.append(addJson)
    js=json.dumps(data,indent=2,separators=(',', ': '))
    with open(i.strip('\n'),'w') as f:
        f.write(js)
