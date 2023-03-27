#!/bin/bash
# Copyright (C) 2023, CERN
# This software is distributed under the terms of the GNU General Public
# Licence version 3 (GPL Version 3), copied verbatim in the file "COPYING".
# In applying this license, CERN does not waive the privileges and immunities
# granted to it by virtue of its status as Intergovernmental Organization
# or submit itself to any jurisdiction.
#
# This script can compare two Jens instances by looking at
# random environments, random modules and hostgroups. It makes sure
# that the HEAD is the same in both instances for each tuple.
#
# Usage: script.sh MOUNTPOINT_INSTANCE_A MOUNTPOINT_INSTANCE_B ITERATIONS <ENVIRONMENT>
#
# Example: script.sh /somewhere/aijens-dev08.cern.ch /somewhere/aijens802.cern.ch 100 qa
#
# If the environment is omitted, the environment choices will be
# random too.
#
# It's a good idea to temporarily suspend updates in both instances to
# compare apples to apples.
#
# The script will stop when a test fails.

if [ $# -lt 3 ]; then
   exit 1;
fi

BASE_A=$1
BASE_B=$2
CHECKS_MAX=$3
FIXED_ENV=$4

if ! [[ -d $BASE_A ]] || ! [[ -d $BASE_B ]]; then
  "The provided mountpoints are not readable directories"
  exit 1
fi

function progress_info {
  local CHECK_COUNTER="[$CUR_CHECK/$CHECKS_MAX]"
  echo "$CHECK_COUNTER $1"
}

function compare_paths {
  local _PATH=$1
  local DIR_A="$BASE_A/$_PATH"
  local DIR_B="$BASE_B/$_PATH"

  if ! [[ -h $DIR_B ]]; then
    progress_info "FAIL $DIR_B does not exist in $BASE_B"
    exit 3
  fi
  if [[ -d $DIR_A ]] && ! [[ -d $DIR_B ]]; then
    progress_info "FAIL $DIR_A is not a broken link (it's broken in B)"
    exit 3
  elif ! [[ -d $DIR_A ]] && [[ -d $DIR_B ]]; then
    progress_info "FAIL $DIR_B is not a broken link (it's broken in A)"
    exit 3
  elif ! [[ -d $DIR_A ]] && ! [[ -d $DIR_B ]]; then
    progress_info "PASS $_PATH (broken links in both trees)"
    return 0
  fi

  pushd $DIR_A > /dev/null
  REV_A=$(git rev-parse HEAD)
  popd > /dev/null
  pushd $DIR_B > /dev/null
  REV_B=$(git rev-parse HEAD)
  popd > /dev/null

  if [ "x$REV_A" == "x$REV_B" ]; then
    progress_info "PASS $_PATH"
    echo -e "\t(A: $REV_A, B: $REV_B)"
  else
    progress_info "FAILURE $_PATH (A: $REV_A, B: $REV_B)"
    date
    pushd $DIR_A > /dev/null
    git show
    popd > /dev/null
    pushd $DIR_B > /dev/null
    git show
    popd > /dev/null
    exit 2
  fi

  return 0
}

echo "Comparing $BASE_A to $BASE_B..."

CUR_CHECK=1
while [ $CUR_CHECK -ne $((CHECKS_MAX+1)) ]; do

  if [[ -z $FIXED_ENV ]]; then
    ENV=$(ls $BASE_A/environments/ | shuf -n 1)
  else
    ENV=$4
  fi
  MODULE=$(ls $BASE_A/environments/$ENV/modules | shuf -n 1)
  HOSTGROUP=$(ls $BASE_A/environments/$ENV/hostgroups | shuf -n 1)

  compare_paths "environments/$ENV/modules/$MODULE"
  compare_paths "environments/$ENV/hostgroups/$HOSTGROUP"
  compare_paths "environments/$ENV/site"
  compare_paths "environments/$ENV/hieradata/operatingsystems"

  CUR_CHECK=$((CUR_CHECK+1))
  echo
done

echo "Done, $CHECKS_MAX tests executed"
