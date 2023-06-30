# SPDX-FileCopyrightText: 2014-2023 CERN
# SPDX-License-Identifier: GPL-3.0-or-later

class JensError(Exception):
    pass

class JensConfigError(JensError):
    pass

class JensMessagingError(JensError):
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
