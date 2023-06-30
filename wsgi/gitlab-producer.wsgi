#!/usr/bin/python3
# SPDX-FileCopyrightText: 2015-2023 CERN
# SPDX-License-Identifier: GPL-3.0-or-later

from jens.settings import Settings
from jens.webapps.gitlabproducer import app as application

settings = Settings('jens-gitlab-producer')
settings.parse_config('/etc/jens/main.conf')
application.config['settings'] = settings
