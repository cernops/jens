# Copyright (C) 2014, CERN
# This software is distributed under the terms of the GNU General Public
# Licence version 3 (GPL Version 3), copied verbatim in the file "COPYING".
# In applying this license, CERN does not waive the privileges and immunities
# granted to it by virtue of its status as Intergovernmental Organization
# or submit itself to any jurisdiction.

CONFIG_GRAMMAR = """
[main]
baredir = string(default='/var/lib/jens/bare')
clonedir = string(default='/var/lib/jens/clone')
environmentsdir = string(default='/var/lib/jens/environments')
debuglevel = option('INFO', 'DEBUG', 'ERROR', default='INFO')
logdir = string(default='/var/log/jens')
mandatorybranches = list(default=list("master", "qa"))
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
lockdir = string(default='/var/lock/jens')
[messaging]
queuedir = string(default='/var/spool/jens-update')
"""
