#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import logging
from datetime import datetime

from invoke import task

FORMATTER = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

console_handler = logging.StreamHandler()
console_handler.setFormatter(FORMATTER)
logger.addHandler(console_handler)


##############################################################
# Git Release
##############################################################
def get_commit_messages(c, old_release_message):
    """Create commit message"""
    # Get last release commit id
    last_release_commit_id = c.run(
        "git log --grep '{}' --pretty='%H'|head".format(old_release_message)
    ).stdout.strip()

    # Get new commit messages from last release
    commit_messages = c.run(
        """git log {last_release_commit_id}..HEAD --pretty='- %s (%h)' \
        | grep -v "Merge branch" | sort""".format(
            last_release_commit_id=last_release_commit_id)).stdout.strip()

    return commit_messages


def update_package_version(new_version):
    """Update package version"""
    with open('package.json') as fin:
        config = json.load(fin)

        config['version'] = new_version

        with open('package.json', 'w') as fout:
            json.dump(config, fout, sort_keys=True,
                      indent=4, separators=(',', ': '))


def update_changelog(new_version, release_date, commit_messages):
    """Update CHANGELOG.md"""
    with open('CHANGELOG.md') as fin:
        changelog = fin.read()

        new_changelog = """## {new_version}
###### {release_date}
{commit_messages}""".format(
            new_version=new_version,
            release_date=release_date,
            commit_messages=commit_messages)

        new_changelog = '{}\n\n{}'.format(new_changelog, changelog)

        with open('CHANGELOG.md', 'w') as fout:
            fout.write(new_changelog)


@task
def git_release_develop(c):
    """git release develop"""
    # Flow
    # 1. Get version
    # 2. Checkout new release branch from develop branch
    # 3. Update version in:
    #    - package.json
    #    - CHANGELOG.md
    # 4. Git add files and commit
    # 5. Merge release branch into master branch
    # 6. Tag version master
    # 7. Push to origin master
    # 8. Merge from release to develop
    # 9. Delete release branch (clean up)

    # Step 1: Get version
    old_version = get_version()
    major_index, minor_index, patch_index = [
        int(t) for t in old_version.split('.')
    ]

    # Increment patch_index
    patch_index += 1

    new_version = '{}.{}.{}'.format(major_index, minor_index, patch_index)
    new_release_branch = 'release-{}'.format(new_version)

    # Step 2: Checkout new release branch from develop branch
    c.run('git checkout develop')
    c.run('git checkout -b {}'.format(new_release_branch))

    # Step 3: Update version
    update_package_version(new_version)

    release_date = datetime.now().strftime('%Y-%m-%d')

    old_release_message = 'Release version: {}'.format(old_version)
    commit_messages = get_commit_messages(c, old_release_message)

    update_changelog(new_version, release_date, commit_messages)

    # Step 4: Git add files and commit
    new_release_message = 'Release version: {}'.format(new_version)

    c.run('git add package.json CHANGELOG.md')
    c.run('git commit -m "{}"'.format(new_release_message))

    # Step 5: Merge release branch into master branch
    new_merge_message = "Merge branch '{}'".format(new_release_branch)
    c.run('git checkout master')
    c.run('git pull')

    c.run('git merge --no-ff -m "{}" {}'.format(new_merge_message,
                                                new_release_branch))

    # Step 6: Tag version master
    c.run('git tag -a {new_version} -m "{new_release_message}"'.format(
        new_version=new_version, new_release_message=new_release_message))

    # Step 7: Push to origin master
    c.run('git push origin master --tags')

    # Step 8: Merge from release to develop
    c.run('git checkout develop')
    c.run('git merge --no-ff -m "{}" {}'.format(new_merge_message,
                                                new_release_branch))
    c.run('git push origin develop')

    # Step 9: Delete release branch (clean up)
    c.run('git branch -d {}'.format((new_release_branch)))

    logger.info('Released: {}'.format(new_version))


##############################################################
# Common
##############################################################
def get_version():
    """Get version"""
    logger.info('Get version')
    with open('package.json') as fin:
        config = json.load(fin)

        version = config['version']

        return version


@task
def gen_package_dependencies_for_docker(c):
    """Generate package dependencies for Docker"""
    logger.info('Generate package dependencies for Docker')
    with open('package.json') as fin:
        config = json.load(fin)

        new_config = dict()
        new_config['license'] = config['license']
        new_config['dependencies'] = config['dependencies']
        new_config['devDependencies'] = config.get('devDependencies')

        with open('package.docker.json', 'w') as fout:
            json.dump(new_config, fout, sort_keys=True,
                      indent=4, separators=(',', ': '))
