# Copyright (C) 2014, CERN
# This software is distributed under the terms of the GNU General Public
# Licence version 3 (GPL Version 3), copied verbatim in the file "COPYING".
# In applying this license, CERN does not waive the privileges and immunities
# granted to it by virtue of its status as Intergovernmental Organization
# or submit itself to any jurisdiction.

class JensError(Exception):
    pass

class JensConfigError(JensError):
    pass

class JensRepositoriesError(JensError):
    pass

class JensEnvironmentsError(JensError):
    pass

class JensGitError(JensError):
    pass

class JensLockError(JensError):
    pass

class JensLockExistsError(JensLockError):
    pass
