# Copyright (C) 2014, CERN
# This software is distributed under the terms of the GNU General Public
# Licence version 3 (GPL Version 3), copied verbatim in the file "COPYING".
# In applying this license, CERN does not waive the privileges and immunities
# granted to it by virtue of its status as Intergovernmental Organization
# or submit itself to any jurisdiction.

import os
import yaml
import tempfile
import shutil
import time
import pickle
import logging
from subprocess import Popen, PIPE
from datetime import datetime
from dirq.queue import Queue, QueueError, QueueLockError

from jens.errors import JensGitError
from jens.messaging import MSG_SCHEMA

GITBINPATH = "git"

def _git(args, gitdir=None, gitworkingtree=None):
    env = os.environ.copy()
    if gitdir is not None:
        logging.debug("Setting GIT_DIR to %s" % gitdir)
        env['GIT_DIR'] = gitdir
    if gitworkingtree is not None:
        logging.debug("Setting GIT_WORK_TREE to %s" % gitworkingtree)
        env['GIT_WORK_TREE'] = gitworkingtree
    args = [GITBINPATH] + args
    logging.debug("Executing git %s" % args)
    (returncode, stdout, stderr) = _exec(args, env)
    if returncode != 0:
        raise JensGitError("Couldn't execute %s (%s)" % \
            (args, stderr.strip()))
    return (stdout, returncode)

def _exec(args, environment):
    git = Popen(args, stdout = PIPE, stderr=PIPE, env=environment)
    (stdout, stderr) = git.communicate()
    return (git.returncode, stdout, stderr)

def init_sandbox(path):
    dirs = [
        "%s/lib/bare/common" % path,
        "%s/lib/bare/modules" % path,
        "%s/lib/bare/hostgroups" % path,
        "%s/lib/clone/common" % path,
        "%s/lib/clone/modules" % path,
        "%s/lib/clone/hostgroups" % path,
        "%s/lib/cache/environments" % path,
        "%s/lib/environments" % path,
        "%s/lib/metadata/environments" % path,
        "%s/lib/metadata/repositories" % path,
        "%s/log" % path,
        "%s/etc" % path,
        "%s/spool" % path,
        "%s/repos/user" % path,
        "%s/repos/bare" % path]
    map(os.makedirs, dirs)

def destroy_sandbox(path):
    shutil.rmtree(path)

def ensure_environment(settings, envname, default,
        modules=[], hostgroups=[], common=[], parser=None):
    environment = {'notifications': 'higgs@example.org'}
    if default is not None:
        environment['default'] = default

    if len(modules) + len(hostgroups) + len(common) > 0:
        environment['overrides'] = {}

    if len(modules) >= 1:
        environment['overrides']['modules'] = {}
    for module in modules:
        name, override = module.split(':')
        environment['overrides']['modules'][name] = override

    if len(hostgroups) >= 1:
        environment['overrides']['hostgroups'] = {}
    for hostgroup in hostgroups:
        name, override = hostgroup.split(':')
        environment['overrides']['hostgroups'][name] = override

    if parser:
        environment['parser'] = parser

    environment_file = open("%s/%s.yaml" % (settings.ENV_METADATADIR, envname), 'w+')
    yaml.dump(environment, environment_file, default_flow_style=False)
    environment_file.close()

def destroy_environment(settings, envname):
    os.remove("%s/%s.yaml" % (settings.ENV_METADATADIR, envname))

def init_repositories(settings):
    data = {'repositories': {'modules': {},
        'hostgroups': {},
        'common': {}}}
    repositories_file = open(settings.REPO_METADATA, 'w+')
    yaml.dump(data, repositories_file, default_flow_style=False)
    repositories_file.close()

def add_repository(settings, partition, name, url):
    repositories_file = open(settings.REPO_METADATA, 'r')
    data = yaml.load(repositories_file)
    repositories_file.close()
    data['repositories'][partition][name] = 'file://' + url
    repositories_file = open(settings.REPO_METADATA, 'w+')
    yaml.dump(data, repositories_file, default_flow_style=False)
    repositories_file.close()

def del_repository(settings, partition, name):
    repositories_file = open(settings.REPO_METADATA, 'r')
    data = yaml.load(repositories_file)
    repositories_file.close()
    del data['repositories'][partition][name]
    repositories_file = open(settings.REPO_METADATA, 'w+')
    yaml.dump(data, repositories_file, default_flow_style=False)
    repositories_file.close()

def create_folder_not_repository(settings, base):
    not_repo_path = tempfile.mkdtemp(dir="%s/repos/user" % base)
    return not_repo_path

def create_fake_repository(settings, base, branches=[]):
    bare_repo_path = tempfile.mkdtemp(dir="%s/repos/bare" % base)
    gitdir = "%s" % bare_repo_path
    args = ["init", "--bare"]
    _git(args, gitdir=gitdir)
    repo_path = bare_repo_path.replace('/repos/bare/', '/repos/user/')
    gitdir = "%s/.git" % repo_path
    args = ["clone", bare_repo_path, repo_path]
    _git(args)
    fake_file = open("%s/dummy" % repo_path, 'w+')
    fake_file.write("foo")
    fake_file.close()
    os.mkdir("%s/code" % repo_path)
    os.mkdir("%s/data" % repo_path)
    os.mkdir("%s/data/fqdns" % repo_path)
    os.mkdir("%s/data/hostgroup" % repo_path)
    os.mkdir("%s/data/operatingsystems" % repo_path)
    os.mkdir("%s/data/datacentres" % repo_path)
    os.mkdir("%s/data/hardware" % repo_path)
    os.mkdir("%s/data/environments" % repo_path)
    shutil.copy("%s/dummy" % repo_path, "%s/code" % repo_path)
    shutil.copy("%s/dummy" % repo_path, "%s/data/hostgroup" % repo_path)
    shutil.copy("%s/dummy" % repo_path, "%s/data/fqdns" % repo_path)
    shutil.copy("%s/dummy" % repo_path, "%s/data/common.yaml" % repo_path)
    shutil.copy("%s/dummy" % repo_path, "%s/data/operatingsystems" % repo_path)
    shutil.copy("%s/dummy" % repo_path, "%s/data/datacentres" % repo_path)
    shutil.copy("%s/dummy" % repo_path, "%s/data/hardware" % repo_path)
    shutil.copy("%s/dummy" % repo_path, "%s/data/environments" % repo_path)
    shutil.copy("%s/dummy" % repo_path, "%s/repositories.yaml" % repo_path)
    gitdir = "%s/.git" % repo_path
    args = ["init"]
    _git(args, gitdir=gitdir, gitworkingtree=repo_path)
    args = ["add", "dummy", "code", "data", "repositories.yaml"]
    _git(args, gitdir=gitdir, gitworkingtree=repo_path)
    args = ["commit", "-m", "init"]
    _git(args, gitdir=gitdir, gitworkingtree=repo_path)
    for branch in branches:
        args = ["checkout", "-b", branch]
        _git(args, gitdir=gitdir, gitworkingtree=repo_path)
        args = ["push", "origin", branch]
        _git(args, gitdir=gitdir, gitworkingtree=repo_path)
    args = ["checkout", "master"]
    _git(args, gitdir=gitdir, gitworkingtree=repo_path)
    fake_file = open("%s/dummy" % repo_path, 'w+')
    fake_file.write("bar")
    fake_file.close()
    args = ["commit", "-a", "-m", "init"]
    _git(args, gitdir=gitdir, gitworkingtree=repo_path)
    fake_file = open("%s/dummy" % repo_path, 'w+')
    fake_file.write("baz")
    fake_file.close()
    args = ["commit", "-a", "-m", "init"]
    _git(args, gitdir=gitdir, gitworkingtree=repo_path)
    args = ["push", "origin", "master"]
    _git(args, gitdir=gitdir, gitworkingtree=repo_path)
    # To simulate client activity, operations like committing,
    # removing a branch etc should be done thru repo_path,
    # bare_repo_path is returned to be added to the lib only.
    return (bare_repo_path, repo_path)

def get_repository_head(settings, repo_path):
    args = ["rev-parse", "HEAD"]
    gitdir = "%s/.git" % repo_path
    (out, code) =_git(args, gitdir=gitdir, gitworkingtree=repo_path)
    return out.strip()

def add_branch_to_repo(settings, repo_path, branch):
    gitdir = "%s/.git" % repo_path
    args = ["checkout", "-b", branch]
    _git(args, gitdir=gitdir, gitworkingtree=repo_path)
    args = ["push", "origin", branch]
    _git(args, gitdir=gitdir, gitworkingtree=repo_path)

def add_commit_to_branch(settings, repo_path, branch, force=False):
    gitdir = "%s/.git" % repo_path
    args = ["checkout", branch]
    _git(args, gitdir=gitdir, gitworkingtree=repo_path)
    fake_file_path = "%s/%s" % (repo_path, time.time())
    fake_file = open(fake_file_path, 'w+')
    fake_file.write("foo")
    fake_file.close()
    args = ["add", fake_file_path]
    _git(args, gitdir=gitdir, gitworkingtree=repo_path)
    args = ["commit", "-a", "-m", "update"]
    _git(args, gitdir=gitdir, gitworkingtree=repo_path)
    args = ["push", "origin", branch]
    if force:
        args.append("--force")
    _git(args, gitdir=gitdir, gitworkingtree=repo_path)
    return get_repository_head(settings, repo_path)

def remove_branch_from_repo(settings, repo_path, branch):
    gitdir = "%s/.git" % repo_path
    args = ["checkout", "master"]
    _git(args, gitdir=gitdir, gitworkingtree=repo_path)
    args = ["branch", "-D", branch]
    _git(args, gitdir=gitdir, gitworkingtree=repo_path)
    args = ["push", "origin", ":%s" % branch]
    _git(args, gitdir=gitdir, gitworkingtree=repo_path)

def reset_branch_to(settings, repo_path, branch, commit_id):
    gitdir = "%s/.git" % repo_path
    args = ["checkout", branch]
    _git(args, gitdir=gitdir, gitworkingtree=repo_path)
    args = ["reset", "--hard", commit_id]
    _git(args, gitdir=gitdir, gitworkingtree=repo_path)

## Messaging

def add_msg_to_queue(settings, msg):
    queue = Queue(settings.MESSAGING_QUEUEDIR, schema=MSG_SCHEMA)
    queue.enqueue(msg)

def create_module_event(settings, module):
    msg = {'time': datetime.now().isoformat(),
        'data': pickle.dumps({'modules': [module]})}
    add_msg_to_queue(settings, msg)

def create_hostgroup_event(settings, hostgroup):
    msg = {'time': datetime.now().isoformat(),
        'data': pickle.dumps({'hostgroups': [hostgroup]})}
    add_msg_to_queue(settings, msg)

def create_common_event(settings, element):
    msg = {'time': datetime.now().isoformat(),
        'data': pickle.dumps({'common': [element]})}
    add_msg_to_queue(settings, msg)
