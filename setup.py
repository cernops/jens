#!/usr/bin/env python

from __future__ import absolute_import
from distutils.core import setup

setup(name='jens',
      version='0.24',
      description='Jens is a Puppet modules/hostgroups librarian',
      classifiers=[
          'Programming Language :: Python :: 2.7',
          'Programming Language :: Python :: 3',
          'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
      ],
      author='Nacho Barrientos',
      author_email='nacho.barrientos@cern.ch',
      url='https://github.com/cernops/jens',
      package_dir={'': 'src'},
      packages=[
          'jens', 'jens.webapps'
      ],
      scripts=[
          'bin/jens-update', 'bin/jens-stats',
          'bin/jens-gitlab-producer-runner', 'bin/jens-purge-queue',
          'bin/jens-reset', 'bin/jens-gc', 'bin/jens-config'
      ],
     )
