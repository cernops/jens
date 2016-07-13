Summary: Jens is a Puppet modules/hostgroups librarian
Name: puppet-jens
Version: 0.15
Release: 1%{?dist}

License: GPL
Group: Applications/System
URL: http://www.cern.ch/config
Source: %{name}-%{version}.tar.gz
BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-root
BuildArch: noarch

Requires: python-configobj, python-argparse, git, PyYAML, python-dirq, GitPython >= 1.0.1
Requires: python-flask
Requires(pre): shadow-utils

%description
Python toolkit to generate Puppet environments dynamically
based on files containing metadata.

%prep
%setup -q

%build
CFLAGS="%{optflags}" %{__python} setup.py build

%install
%{__rm} -rf %{buildroot}
%{__python} setup.py install --skip-build --root %{buildroot}
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
mkdir -m 750 -p %{buildroot}/var/lock/jens/
mkdir -m 750 -p %{buildroot}/var/spool/jens-update/
mkdir -m 750 -p %{buildroot}/var/www/jens
%{__install} -D -p -m 755 wsgi/* %{buildroot}/var/www/jens

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
%{python_sitelib}/*
%{_bindir}/jens-*
%attr(750, jens, jens) /var/lib/jens/*
%attr(750, jens, jens) /var/log/jens
%attr(750, jens, jens) /var/lock/jens
%attr(750, jens, jens) /var/spool/jens-update
%config(noreplace) %{_sysconfdir}/jens/main.conf

%changelog
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

* Fri Sep 03 2015 Nacho Barrientos <nacho.barrientos@cern.ch> - 0.11-2
- Prevent RPM from replacing the configuration file.

* Fri Sep 03 2015 Nacho Barrientos <nacho.barrientos@cern.ch> - 0.11-1
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

* Fri Mar 10 2014 Nacho Barrientos <nacho.barrientos@cern.ch> - 0.5-1
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

* Tue Jul 09 2012 Nacho Barrientos <nacho.barrientos@cern.ch> - 0.1-1
- Initial release
