# Copyright (C) 2014, CERN
# This software is distributed under the terms of the GNU General Public
# Licence version 3 (GPL Version 3), copied verbatim in the file "COPYING".
# In applying this license, CERN does not waive the privileges and immunities
# granted to it by virtue of its status as Intergovernmental Organization
# or submit itself to any jurisdiction.

import re
from jens.settings import Settings

def refname_to_dirname(refname):
    settings = Settings()
    match = ref_is_commit(refname)
    if match:
        return ".%s" % match.group(1)
    return refname

def dirname_to_refname(dirname):
    settings = Settings()
    match = re.match(r'^\.([^\.]+)', dirname)
    if match:
        return "%s%s" % (settings.HASHPREFIX, match.group(1))
    return dirname

def ref_is_commit(refname):
    settings = Settings()
    return re.match(r'^%s([0-9A-Fa-f]+)' % settings.HASHPREFIX,
                    refname, re.IGNORECASE)
