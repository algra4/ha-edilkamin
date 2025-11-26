#!/bin/bash

if [ -z "$1" ]; then
  echo "❌ Error: you need to provide a version."
  echo "Usage: ./release.sh v1.0.0"
  exit 1
fi

VERSION=$1
JSON_FILE="custom_components/edilkamin/manifest.json"
BRANCH="main"

CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
if [ "$CURRENT_BRANCH" != "$BRANCH" ]; then
	echo "❌ Error: You must be on the main branch ($BRANCH) to create a release."
	exit 1
fi

# Check that git status is clean
if [[ $(git status --porcelain) ]]; then
  echo "❌ Error: You have uncommitted changes."
  echo " Please commit or stash your changes before starting a release."
  exit 1
fi

echo "🚀 Starting release: $VERSION"

# Check if jq is installed
if ! command -v jq >/dev/null 2>&1; then
  echo "❌ Error: jq is not installed. Please install jq to continue."
  exit 1
fi

# Check if JSON file exists
if [ ! -f "$JSON_FILE" ]; then
  echo "❌ Error: JSON file '$JSON_FILE' does not exist."
  exit 1
fi

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
git push origin "$BRANCH"
git push origin "$VERSION"

echo "🎉 Release finished! GitHub will now see the new tag and trigger your actions (if you have any)."