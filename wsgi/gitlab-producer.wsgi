#!/usr/bin/env python
# Copyright (C) 2015, CERN
# This software is distributed under the terms of the GNU General Public
# Licence version 3 (GPL Version 3), copied verbatim in the file "COPYING".
# In applying this license, CERN does not waive the privileges and immunities
# granted to it by virtue of its status as Intergovernmental Organization
# or submit itself to any jurisdiction.

from jens.settings import Settings
from jens.webapps.gitlabproducer import app as application

settings = Settings('jens-gitlab-producer')
settings.parse_config('/etc/jens/main.conf')
application.config['settings'] = settings
