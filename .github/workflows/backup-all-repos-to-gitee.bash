#!/bin/bash
owner=$1
token=$2
rm repos_*.json || true
while true;do
	let page++
	sleep 1
	wget "https://api.github.com/users/$owner/repos?per_page=100&page=$page" -O repos_$page.json
	n=`cat repos_$page.json | jq '.[]|.full_name' | wc -l`
	echo $n
	if [ "x$n" != "x100" ]; then
      		break
  	fi
done
for repo in $(cat repos_*.json | jq '.[] | .name '| xargs -i echo {});do
	echo $repo
	rm -rf .git
	git clone --bare https://github.com/$owner/$repo.git .git
	if [ "$repo"x == ".github"x ];then
		repo="github"
	fi
	homepage="https://github.com/linuxdeepin/${repo}"
	description="mirror of ${homepage}"
	# create repo
	curl -X POST --header 'Content-Type: application/json;charset=UTF-8' "https://gitee.com/api/v5/enterprises/$owner/repos" -d '{"private": 1,"access_token":"'"$token"'","name":"'"$repo"'","description":"'"$description"'","homepage":"'"$homepage"'","has_issues":"false","has_wiki":"false","can_comment":"false"}' || true
	# setting repo
	curl -X PATCH --header 'Content-Type: application/json;charset=UTF-8' "https://gitee.com/api/v5/repos/$owner/$repo" -d '{"access_token":"'"$token"'","name":"'"$repo"'","description":"'"$description"'","homepage":"'"$homepage"'","has_issues":"false","has_wiki":"false","can_comment":"false","private":"false","pull_requests_enabled":"false"}'
	# push repo
	git remote set-url origin https://myml:$token@gitee.com/$owner/${repo}.git
	git push -f --all --prune origin
	git push -f --tags origin
done