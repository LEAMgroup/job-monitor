#INSTALL

leampoll.py is used to monitor LEAM Planning Portals for jobs that have
been placed in the *queued* state. A queued job is popped from the Portal
and execution is begun.  After the job completes leampoll.py again
enters the monitoring loop.

leampoll.py is standalone python script. It can be installed anywhere
but by convention it is place in /usr/local/bin. Something like the
following:

    sudo cp leampoll.py /usr/local/bin
    sudo chmod 0550 /usr/local/bin/leampoll.py

## Creating Runtime Directory

When a job is queued leampoll.py automatically creates a unique runtime
directory for each job. To simplify management it is easiest to create a
project specific directory where leampoll.py will run. Because the server
can be used for several projects a hierarchy such as the following can be
used.

    mkdir -p /<path>/<jobdir>/<project>

<path> - path to working space (/mnt is used on AWS servers).
<jobdir> - container for all project folders
<project> - a project specific directory

### Jobdir Directory

During execution models may require a large amount of temporary space so ensure
that the file system where <jobdir> is located has sufficient free space to
meet the needs of future jobs.

## Using Supervisor

While leampoll.py can be run from the command line it is best to manage it like
a traditional linux service. While creation of a standard init script in
/etc/init.d is possible, the recommended solution is run leampoll.py under
Supervisor (http://supervisord.org).

Supervisor can be installed using the instruction found on the Supervisor
website but Ubuntu provides a complete package that simplifies the installation
and ensures that Supervisor is started after each reboot.  The following
command will install Supervisor:

    sudo apt-get install supervisor

The Ubuntu package has a somewhat different installation from what is described
in the standard documentation, the package installs Supervisor with
/etc/supervisor/supervisord.conf as the primary configuration file and includes
any additional configurations found in /etc/supervisor/conf.d. A sample
configuration file, region.conf, that can be modified for each Portal is
provided. Copy the modified config to /etc/supervisor/conf.d to enable control
of leampoll.py for a project. 

If you prefer to follow the standard documentation you can install supervisor
using pip and then install this 
[init.d script](https://github.com/Supervisor/initscripts/blob/master/ubuntu). 
One advantage of this approach is that you get the latest version of
Supervisor as the Ubuntu maintained package appears fairly old.

A template *region.conf* file is provided for use with supervisor.  This file
can be edited for the project specifics and then either appended to the end of
the supervisord.conf file or placed into /etc/supervisor/conf.d directory.

