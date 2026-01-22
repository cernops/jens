#!/usr/bin/python3
# SPDX-FileCopyrightText: 2014-2023 CERN
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import
from setuptools import setup

try:
    with open("requirements.txt", encoding='utf-8') as requirements:
        INSTALL_REQUIRES = [req.strip() for req in requirements.readlines()]
except OSError:
    INSTALL_REQUIRES = None

setup(name='jens',
      version='1.4.1',
      description='Jens is a Puppet modules/hostgroups librarian',
      classifiers=[
          'Programming Language :: Python :: 3',
          'Programming Language :: Python :: 3 :: Only',
          'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
      ],
      author='Nacho Barrientos',
      author_email='nacho.barrientos@cern.ch',
      url='https://github.com/cernops/jens',
      install_requires=INSTALL_REQUIRES,
      packages=[
          'jens', 'jens.webapps'
      ],
      scripts=[
          'bin/jens-update', 'bin/jens-stats',
          'bin/jens-gitlab-producer-runner', 'bin/jens-purge-queue',
          'bin/jens-reset', 'bin/jens-gc', 'bin/jens-config'
      ],
     )
