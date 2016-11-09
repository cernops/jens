#!/usr/bin/env python

from distutils.core import setup

setup(name='jens',
      version='0.20',
      description='Jens is a Puppet modules/hostgroups librarian',
      author='Nacho Barrientos',
      author_email='nacho.barrientos@cern.ch',
      url='https://github.com/cernops/jens',
      package_dir= {'': 'src'},
      packages=['jens', 'jens.webapps'],
      scripts=['bin/jens-update', 'bin/jens-stats',
        'bin/jens-gitlab-producer-runner', 'bin/jens-purge-queue',
        'bin/jens-reset', 'bin/jens-gc', 'bin/jens-config'],
     )
