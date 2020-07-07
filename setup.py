#!/usr/bin/python3

from __future__ import absolute_import
from distutils.core import setup

setup(name='jens',
      version='1.1',
      description='Jens is a Puppet modules/hostgroups librarian',
      classifiers=[
          'Programming Language :: Python :: 3',
          'Programming Language :: Python :: 3 :: Only',
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
