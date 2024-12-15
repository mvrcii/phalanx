#!/usr/bin/env sh
set -e

# Extract the current version from pyproject.toml
old_version=$(grep '^version = ' pyproject.toml | sed 's/version = "\(.*\)"/\1/')

# Split the version into parts by '.'
IFS='.' read -r major minor patch <<< "$old_version"

# Increment the patch number
patch=$((patch + 1))

# Form the new version
new_version="$major.$minor.$patch"

# Update pyproject.toml with the new version
sed -i.bak "s/version = \"$old_version\"/version = \"$new_version\"/" pyproject.toml

echo "Updated version: $old_version -> $new_version"

# Remove old distribution files
rm -rf dist

# Build the package
python -m build

# Upload the new distribution
twine upload dist/*