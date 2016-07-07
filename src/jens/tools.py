# Copyright (C) 2014, CERN
# This software is distributed under the terms of the GNU General Public
# Licence version 3 (GPL Version 3), copied verbatim in the file "COPYING".
# In applying this license, CERN does not waive the privileges and immunities
# granted to it by virtue of its status as Intergovernmental Organization
# or submit itself to any jurisdiction.

import re

def refname_to_dirname(settings, refname):
    match = ref_is_commit(settings, refname)
    if match:
        return ".%s" % match.group(1)
    return refname

def dirname_to_refname(settings, dirname):
    match = re.match("^\.([^\.]+)", dirname)
    if match:
        return "%s%s" % (settings.HASHPREFIX, match.group(1))
    return dirname

def ref_is_commit(settings, refname):
    return re.match("^%s([0-9A-Fa-f]+)" % settings.HASHPREFIX,
        refname,
        re.IGNORECASE)
