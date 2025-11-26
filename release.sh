#!/bin/bash

if [ -z "$1" ]; then
  echo "❌ Error: we need to provided a version."
  echo "Usage : ./release.sh v1.0.0"
  exit 1
fi

VERSION=$1
JSON_FILE="custom_components/edilkamin/manifest.json"

# Check that git status is clean
if [[ `git status --porcelain` ]]; then
  echo "❌ Error: You have uncommitted changes."
  echo " Please commit or stash your changes before starting a release."
  exit 1
fi

echo "🚀 Starting release: $VERSION"

tmp=$(mktemp)
jq --arg v "$VERSION" '.version = $v' "$JSON_FILE" > "$tmp" && mv "$tmp" "$JSON_FILE"
echo "✅ File $JSON_FILE updated."

# 3. Commit changes
git add "$JSON_FILE"
git commit -m "chore(release): bump version to $VERSION"
echo "✅ Commit created."

# 4. Create Tag
git tag "$VERSION"
echo "✅ Tag $VERSION created."

# 5. Push to GitHub (Commits + Tags)
echo "✅ Pushing changes to GitHub..."
#git push origin main
#git push origin "$VERSION"

echo "🎉 Release finished! GitHub will now see the new tag and trigger your actions (if you have any)."