# SPDX-FileCopyrightText: 2014-2023 CERN
# SPDX-License-Identifier: GPL-3.0-or-later

CONFIG_GRAMMAR = """
[main]
baredir = string(default='/var/lib/jens/bare')
clonedir = string(default='/var/lib/jens/clone')
environmentsdir = string(default='/var/lib/jens/environments')
debuglevel = option('INFO', 'DEBUG', 'ERROR', default='INFO')
logdir = string(default='/var/log/jens')
mandatorybranches = list(default=list("master", "qa"))
protectedenvironments = list(default=list())
environmentsmetadatadir = string(default='/var/lib/jens/metadata/environments')
repositorymetadatadir = string(default='/var/lib/jens/metadata/repository')
repositorymetadata = string(default='/var/lib/jens/metadata/repository/repositories.yaml')
cachedir = string(default='/var/lib/jens/cache')
hashprefix = string(default='commit/')
directory_environments = boolean(default=False)
common_hieradata_items = list(default=list())
mode = option('POLL', 'ONDEMAND', default='POLL')
[lock]
type = option('DISABLED', 'FILE', default='FILE')
name = string(default='jens')
[filelock]
lockdir = string(default='/run/lock/jens')
[messaging]
queuedir = string(default='/var/spool/jens-update')
[git]
ssh_cmd_path = string(default=None)
[gitlabproducer]
secret_token = string(default=None)
"""
