#!/bin/bash
owner=$1
token=$2

echo "::group::Get Repo List"
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
echo "::endgroup::"


for repo in $(cat repos_*.json | jq '.[] | .name '| xargs -i echo {});do
	echo "::group::Sync $owner/$repo"
	echo triggerSync $repo
	export GITHUB_REPOSITORY_OWNER=$owner
	export GITHUB_REPOSITORY=$owner/$repo
	id=$(jenkins-bridge-client triggerSync --token $token)
	jenkins-bridge-client printLog --token $token --runid $id
	echo "::endgroup::"
done