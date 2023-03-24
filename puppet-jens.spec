Summary: Jens is a Puppet modules/hostgroups librarian
Name: puppet-jens
Version: 1.4.0
Release: 1%{?dist}

License: GPLv3
Group: Applications/System
URL: http://www.cern.ch/config
Source: %{name}-%{version}.tar.gz
BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-root
BuildArch: noarch

BuildRequires: systemd-rpm-macros, python3-devel, epel-rpm-macros
# The following requires are for the %check
BuildRequires: python3-pyyaml, python3-urllib3, python3-configobj
BuildRequires: python3-dirq, python3-flask, python3-GitPython, git

Requires: git
Requires(pre): shadow-utils

%description
Python toolkit to generate Puppet environments dynamically
based on files containing metadata.

%prep
%setup -q

%build
%py3_build

%install
%{__rm} -rf %{buildroot}
%py3_install
%{__install} -D -p -m 644 conf/main.conf %{buildroot}/%{_sysconfdir}/jens/main.conf
mkdir -m 755 -p %{buildroot}/%{_mandir}/man1
%{__install} -D -p -m 644 man/* %{buildroot}/%{_mandir}/man1
mkdir -m 750 -p %{buildroot}/var/lib/jens/bare/modules
mkdir -m 750 -p %{buildroot}/var/lib/jens/bare/hostgroups
mkdir -m 750 -p %{buildroot}/var/lib/jens/bare/common
mkdir -m 750 -p %{buildroot}/var/lib/jens/clone/modules
mkdir -m 750 -p %{buildroot}/var/lib/jens/clone/hostgroups
mkdir -m 750 -p %{buildroot}/var/lib/jens/clone/common
mkdir -m 750 -p %{buildroot}/var/lib/jens/cache/environments
mkdir -m 750 -p %{buildroot}/var/lib/jens/environments
mkdir -m 750 -p %{buildroot}/var/lib/jens/metadata
mkdir -m 750 -p %{buildroot}/var/log/jens/
mkdir -m 750 -p %{buildroot}/var/spool/jens-update/
mkdir -m 750 -p %{buildroot}/var/www/jens
%{__install} -D -p -m 755 wsgi/* %{buildroot}/var/www/jens
mkdir -p %{buildroot}%{_tmpfilesdir}
install -m 0644 jens-tmpfiles.conf %{buildroot}%{_tmpfilesdir}/%{name}.conf
mkdir -p %{buildroot}%{_unitdir}
install -p -m 644 systemd/jens-update.service %{buildroot}%{_unitdir}/jens-update.service
install -p -m 644 systemd/jens-purge-queue.service %{buildroot}%{_unitdir}/jens-purge-queue.service

%check
export EMAIL="noreply@cern.ch"
export GIT_AUTHOR_NAME="RPM build"
export GIT_COMMITTER_NAME="RPM build"
%{__python3} -m unittest

%clean
%{__rm} -rf %{buildroot}

%pre
/usr/bin/getent group jens || /usr/sbin/groupadd -r jens
/usr/bin/getent passwd jens || /usr/sbin/useradd -r -g jens -d /var/lib/jens -s /sbin/nologin jens

%files
%defattr(-,root,root,-)
%doc README.md ENVIRONMENTS.md examples
%{_mandir}/man1/*
/var/www/jens/*
%{python3_sitelib}/*
%{_bindir}/jens-*
%attr(750, jens, jens) /var/lib/jens/*
%attr(750, jens, jens) /var/log/jens
%attr(750, jens, jens) /var/spool/jens-update
%config(noreplace) %{_sysconfdir}/jens/main.conf
%{_tmpfilesdir}/%{name}.conf
%{_unitdir}/jens-update.service
%{_unitdir}/jens-purge-queue.service

%changelog
* Mon Mar 13 2023 Nacho Barrientos <nacho.barrientos@cern.ch> - 1.4.0-1
- Gitlab producer: Return 201 if the hint can be enqueued.
- Gitlab producer: Return 200 if the hinted repository is not part of the library.

* Tue Jan 17 2023 Nacho Barrientos <nacho.barrientos@cern.ch> - 1.3.0-1
- Switch to semanting versioning.
- Add support for Gitlab webhook tokens.
- Use Python's unittest runner.
- Close file descriptions explicitly.
- Some Python-3 related code changes: f-strings, super(), etc.

* Tue May 11 2021 Nacho Barrientos <nacho.barrientos@cern.ch> - 1.2-2
- Rebuild for CentOS Stream 8

* Wed Oct 28 2020 Nacho Barrientos <nacho.barrientos@cern.ch> - 1.2-1
- Ship systemd service unit files for jens-update and jens-purge-queue.

* Tue Jul 07 2020 Nacho Barrientos <nacho.barrientos@cern.ch> - 1.1-1
- Python3-only compatibility.
- Use tmpfiles.d to create the lock directory.

* Mon Jun 29 2020 Nacho Barrientos <nacho.barrientos@cern.ch> - 0.25-1
- Minor fixes to the Spec file.

* Mon Jun 11 2018 Nacho Barrientos <nacho.barrientos@cern.ch> - 0.24-1
- Migrate from optparse to argparse.

* Tue Apr 03 2018 Nacho Barrientos <nacho.barrientos@cern.ch> - 0.23-1
- Python 3.x compatibility.
- Spelling and broken links in the documentation.

* Mon Mar 20 2017 Nacho Barrientos <nacho.barrientos@cern.ch> - 0.22-1
- A big bunch of Lint fixes, no new functionality nor bugfixes.

* Wed Jan 11 2017 Nacho Barrientos <nacho.barrientos@cern.ch> - 0.21-1
- Make sure that settings.ENVIRONMENTSDIR exists.
- Add the process ID to the log messages.
- Show the new HEAD when a clone has been updated.

* Wed Nov 09 2016 Nacho Barrientos <nacho.barrientos@cern.ch> - 0.20-1
- Handle AssertionError when doing Git ops

* Tue Nov 08 2016 Nacho Barrientos <nacho.barrientos@cern.ch> - 0.19-1
- Add an option to protect environments.

* Tue Nov 01 2016 Nacho Barrientos <nacho.barrientos@cern.ch> - 0.18-1
- Add jens-purge-queue.

* Wed Jul 27 2016 Nacho Barrientos <nacho.barrientos@cern.ch> - 0.17-1
- Transform the Settings class into a Borg.
- Add an option to set GIT_SSH (fixes AI-4385).

* Tue Jul 19 2016 Nacho Barrientos <nacho.barrientos@cern.ch> - 0.16-1
- Fix git_wrapper so reset(hard=True) actually works.

* Wed Jul 13 2016 Nacho Barrientos <nacho.barrientos@cern.ch> - 0.15-1
- Configure GitPython differently to avoid leaking file descriptors as per
  upstream's recommendation.

* Tue Jul 12 2016 Nacho Barrientos <nacho.barrientos@cern.ch> - 0.14-1
- Remove support for etcd.
- Use GitPython for Git operations instead of subprocessing directly.

* Tue Mar 29 2016 Nacho Barrientos <nacho.barrientos@cern.ch> - 0.13-1
- Allow setting 'parser' in environment.conf

* Mon Jan 11 2016 Nacho Barrientos <nacho.barrientos@cern.ch> - 0.12-1
- Add on-demand mode to jens-update.
- Add webapps/gitlabproducer.

* Thu Sep 03 2015 Nacho Barrientos <nacho.barrientos@cern.ch> - 0.11-2
- Prevent RPM from replacing the configuration file.

* Thu Sep 03 2015 Nacho Barrientos <nacho.barrientos@cern.ch> - 0.11-1
- Support variable number of elements in common hieradata.

* Wed Nov 19 2014 Nacho Barrientos <nacho.barrientos@cern.ch> - 0.10-1
- Add support for directory environments
- Add tons of user documentation (README, ENVIRONMENTS, INSTALL)

* Wed Aug 13 2014 Nacho Barrientos <nacho.barrientos@cern.ch> - 0.9-1
- Reset instead of merge when refreshing metadata.
- Add a new testsuite for the metadata refreshing step.
- Add more assertion to some tests.

* Tue May 13 2014 Nacho Barrientos <nacho.barrientos@cern.ch> - 0.8-1
- Ignore malformed keys when reading the desided inventory.

* Mon Mar 31 2014 Nacho Barrientos <nacho.barrientos@cern.ch> - 0.7-1
- Set GIT_HTTP_LOW_SPEED_LIMIT
- Relative path for Git bin

* Tue Mar 18 2014 Nacho Barrientos <nacho.barrientos@cern.ch> - 0.6-1
- No hard timeouts.
- Shared objects for static clones.

* Mon Mar 10 2014 Nacho Barrientos <nacho.barrientos@cern.ch> - 0.5-1
- Add support for etcd locks.
- Add support for commits as overrides.
- Only expand required branches/commits.
- Add soft and hard timeouts for Git calls.

* Tue Oct 01 2013 Nacho Barrientos <nacho.barrientos@cern.ch> - 0.4-1
- Be more chatty about new/changed/deleted branches
- Stop checking for broken links
- Use relative links when binding environments to clones
- Use fcntl to gain the lock

* Wed Sep 11 2013 Nacho Barrientos <nacho.barrientos@cern.ch> - 0.3-1
- Only inform about broken overrides.

* Wed Sep 04 2013 Ben Jones <ben.dylan.jones@cern.ch> - 0.2-1
- git clones now reset rather than merged

* Mon Jul 09 2012 Nacho Barrientos <nacho.barrientos@cern.ch> - 0.1-1
- Initial release
