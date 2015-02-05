#!/usr/bin/env python
"""
leampoll.py is a simple program to poll the Modeling Portal and perform
any queued tasks.  leampoll.py is typically installed in /usr/local/bin
and automatically started on system startup. 
"""
import os, sys, time
import optparse
import shutil
import re
from subprocess import call, check_call, check_output
import subprocess
import requests
import json
from xml.etree.ElementTree import tostring, fromstring

import logging
logger = logging.getLogger(__name__)

VERSION = 2.1

def init_logger(level=logging.INFO, format=None, datetime=None):
    """initialize the root logger
    """

    f = format or '%(asctime)s %(module)s: %(levelname)s: %(message)s'
    d = datetime or '%Y-%m-%d %H:%M:%S'
    logging.basicConfig(level=level, format=f, datefmt=d)


def safe_string(s):
    """Generate a string that is safe to use as filename, directory, etc.

    Designed to handle filename with path and extensions but should
    work on any string. Currently performs the following steps:
    1) removes filename extensions from basename and strip whitespace
    2a) removes any none alphabetic characters from the beginning
    2b) removes anything that does match a-z, A-Z, 0-9, _, -, or whitespace
    3) replaces remaining whitespace and dashes with a single _
    """
    s = os.path.splitext(os.path.basename(s))[0].strip()
    return re.sub('[\s-]+', '_', re.sub('^[^a-zA-Z]+|[^\w\s-]+','', s))


def runjob(tree):
    """Check out the repository and begins model execution

       @param tree configuration file as parsed xml tree
    """
    #import pdb; pdb.set_trace()

    rundir = tree.findtext('scenario/id').replace('-','_')
    if os.path.exists(rundir):
        shutil.rmtree(rundir)

    # checks for cmdline and executes it
    #cmdline = tree.findtext('scenario/cmdline')
    #if cmdline:
    #    os.mkdir(rundir)
    #    check_call(cmdline.split(), cwd=rundir)

    # no cmdline given so checkout reposity and execute startup.py
    repo = tree.findtext('scenario/repository')
    checkout = ['svn', 'co', repo, rundir]
    logger.debug("CHECKOUT = " + ' '.join(checkout))
    check_output(checkout)

    with open(os.path.join(rundir,'config.xml'), 'w') as f:
        f.write(tostring(tree))

    cmd = "python startup.py -c config.xml".split()
    errname = os.path.join(rundir, 'run.log')
    outname = os.path.join(rundir, 'run.out')
    logger.debug("Starting Model Execution")
    with open(outname, 'wb') as out, open(errname, 'wb') as err:
        retcode = call(cmd, cwd=rundir, stdout=out, stderr=err)

    # model returned non-zero (error) return code
    if retcode:
        pass

def pretty_print(xmlstr, fname='config.xml'):
    from xml.dom.minidom import parseString
    import re

    dom = parseString(xmlstr)
    ugly = dom.toprettyxml(indent='  ') 
    text_re = re.compile('>\n\s+([^<>\s].*?)\n\s+</', re.DOTALL)
    pretty = text_re.sub('>\g<1></', ugly)

    f = open(fname, 'w')
    f.write(pretty)
    f.close()


def xml_response(rsp):
    """ Handle responses formatted in XML.

    Depricated: this function is preserved to support portals using
    older versions of leam.luc.
    """
    logger.warn('DEPRICATED: xml_response, use the JSON configuration.')
    tree = fromstring(rsp.text)
    if tree.text and tree.text == 'EMPTY':
        logger.info('EMPTY QUEUE')
        return

    elif tree.text and tree.text == 'ERROR':
        logger.warn('QUEUE returned error!')
        return

    logger.info("XML Job = " + tree.findtext('scenario/title'))
    try:
        runjob(tree)
    except OSError:
        logger.exception("Job failed with OSError")
    except subprocess.CalledProcessError, e:
        logger.error(">>Job failed with non-zero return code")
        logger.error(e.output)
        logger.error(">>Continuing")
    else:
        logger.info("Job Complete")


def parse_userdata():
    """parse the AWS userdata and return user and password
    """
    pass


def get_repository(repo, jobid):
    """get the repository into a new directory

    Args:
      repo (str): command to checkout application
      jobid (str): a short name for the job

    Returns:
      (str): returns name of runtime directory
    """

    rundir = safe_string(jobid)

    # remove old rundir if it exists
    if os.path.exists(rundir):
        shutil.rmtree(rundir)

    # TODO: if the repository is misconfigured git attempts to interactively
    # ask for a password. This will hang everything!
    if repo:
        logger.debug('loading repository %s to %s' % (repo, rundir))
        cmd = repo.split() + [rundir,]
        with open(os.devnull, 'wb') as FNULL:
            check_call(cmd, stdout=FNULL, stderr=subprocess.STDOUT)
        logger.debug('repo checkout complete')
    else:
        os.mkdir(rundir)
        logger.debug('no repo specified, mkdir ' + rundir)

    return rundir


def report_error(url, msg):
    """ post error message to portal

    Args:
      url (str): URL of modeling entity
      msg (str): message to posted
    """

    if not url:
        return

    msg = 'Error: ' + msg


def report_success(url):
    """ post success message to portal

    Args:
      url (str): URL of modeling entity
      msg (str): message to posted
    """

    if not url:
        return


def json_response(rsp):
    """ Handle responses formatted in JSON.

    Exceptions: 
      This function captures all exceptions, reports error, and returns.
    """

    if rsp.get('status', '') == 'EMPTY':
        logger.debug('json_response: pop_queue returned empty')
        return

    logger.info("New Job = '%s'" % rsp.get('title'))
    on_error = rsp.get('on_error', '')

    try:
        rundir = get_repository(rsp.get('repository', ''), rsp.get('id'))

    except subprocess.CalledProcessError as e:
        report_error(on_error, 'unable to checkout repository')
        logger.error('unable to access %s, return code = %d' % 
                     (rsp.get('repository'), e.retcode))
        return

    # less likely exceptions
    except Exception as e:
        report_error(on_error, 'repository checkout: ' + str(e))
        logger.error('repository checkout: ' + str(e))
        return

    # run command line
    cmdline = rsp.get('cmdline', '')
    if not cmdline:
        report_error(rsp.get('on_error', 'no startup command given'))
        logger.error('no startup command given')
        return

    logger.debug('command line = ' + cmdline)

    try:
        with open(rundir+'.log', 'wb') as f:
            check_call(cmdline.split(), cwd=rundir, 
                       stdout=f, stderr=subprocess.STDOUT)

    except subprocess.CalledProcessError as e:
        report_error(on_error, 'start-up command failed')
        logger.error('command %s failed, return code = %d' %
                     (cmdline, e.retcode))
        return

    # less likely exceptions
    except Exception as e:
        report_error(on_error, 'start-up command: ' + str(e))
        logger.error('startup command: ' + str(e))
    
    report_success(rsp.get('on_success', ''))
    logger.debug('command completed successfully')


def main():

    usage = "usage: %prog [options] <Site URL>"

    parser = optparse.OptionParser(usage=usage)
    parser.add_option('-s', '--speed', default=20, type="int",
        help='set the polling speed to X seconds')
    parser.add_option('-i', '--idle', default=0, type="int",
        help='terminates server after number of empty polls (default=0)')
    parser.add_option('-q', '--popq', default='/pop_queue',
        help="append '/pop_queue' to the command line URL")
    parser.add_option('-p', '--preserve', default=False, action='store_true',
        help='preserve runtime dirs created for each job')
    parser.add_option('-U', '--user', default=None,
        help='Portal user name (or PORTAL_USER environmental var)')
    parser.add_option('-X', '--password', default=None,
        help='Portal password (or PORTAL_PASSWORD environmental var)')
    parser.add_option('-u', '--userdata', default=False, action='store_true',
        help='parse user data for authentication data')
    parser.add_option('-d', '--debug', default=False, action='store_true',
        help='set log level to DEBUG')
    parser.add_option('-v', '--version', default=False, action='store_true',
        help='print version and exit')

    (options, args) = parser.parse_args()

    if options.version:
        sys.stdout.write('%s version=%s\n' % (sys.argv[0],VERSION))
        sys.exit(0)

    if options.debug:
        init_logger(level=logging.DEBUG)
    else:
        init_logger()

    # make sure requests module is relatively quiet
    logging.getLogger("requests").setLevel(logging.WARNING)

    # check for authentication variables
    # If not set then log message to stderr and return error if the
    # script was started by a job monitor then it should report to
    # portal.
    user = options.user or os.environ.get('PORTAL_USER', '')
    password = options.password or os.environ.get('PORTAL_PASSWORD', '')

    # ensure user/password set in environment for modeling commands
    if user and password:
        os.environ['PORTAL_USER'] = user
        os.environ['PORTAL_PASSWORD'] = password

    else:
        logger.error('Portal user and password are required. '
                'Specify on the command line or environmental variables.\n')
        sys.exit(1)

    if len(args) != 1:
        logger.error('the URL to the Plone site is required')
        sys.exit(1)

    url = args[0]
    popq = url+options.popq
    logger.info('polling started on ' + url)

    # primary loop
    while True:
        try:
            logger.debug('Popping the Queue')
            r = requests.get(popq, auth=(user, password))
            r.raise_for_status()

        except requests.exceptions.ConnectionError:
            logger.error("Connection Error")
            time.sleep(60)
            continue

        except requests.exceptions.Timeout:
            logger.error("Connection Timeout")
            time.sleep(60)
            continue

        except requests.exceptions.HTTPError:
            logger.error("HTTP status error code = " + str(r.status_code))
            time.sleep(600)
            continue

        logger.debug('content-type: ' + r.headers['content-type'])

        if r.headers['content-type'].startswith('application/xml'):
            xml_response(r)

        elif r.headers['content-type'].startswith('application/json'):
            json_response(r.json())

        # probably an error message
        elif r.header['content-type'].startswith('text/html'):
            with open('response.log','a') as f:
                 f.write(r.content())
                 f.write('\n=======================\n')

        else:
            logger.error("popqueue returned unknown content-type '%s'",
                    r.headers['content-type'])

        time.sleep(options.speed)


if __name__ == '__main__':
    main()

