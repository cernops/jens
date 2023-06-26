# SPDX-FileCopyrightText: 2014-2023 CERN
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import
import re
from jens.settings import Settings

def refname_to_dirname(refname):
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
