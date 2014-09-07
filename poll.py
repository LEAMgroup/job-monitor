#!/usr/bin/env python
import os, sys, time
import optparse
import shutil
from subprocess import call, check_call, check_output
import subprocess
import requests
import json
from xml.etree.ElementTree import tostring, fromstring

import logging
logging.basicConfig(level=logging.WARN)


def runjob(tree, model):
    """Checks out the repository and begins model execution
       WARNING: Big HACK with the model
       @param tree configuration file as parsed xml tree
       @param model total hack to use custom repository

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
    repo = tree.findtext('scenario/repository').replace('ewg', model)
    checkout = ['svn', 'co', repo, rundir]
    logging.debug("CHECKOUT = " + ' '.join(checkout))
    check_output(checkout)

    f = open(os.path.join(rundir,'config.xml'), 'w')
    f.write(tostring(tree))
    f.close()

    cmd = "python startup.py -c config.xml".split()
    errname = os.path.join(rundir, 'run.log')
    outname = os.path.join(rundir, 'run.out')
    logging.debug("Starting Model Execution")
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


def xml_response(rsp, model):
    """ Handle responses formatted in XML.

    Depricated: this function is preserved to support portals using
    oldder versions of leam.luc.
    """
    tree = fromstring(rsp.text)
    if tree.text and tree.text == 'EMPTY':
        logging.info('EMPTY QUEUE')
        return

    elif tree.text and tree.text == 'ERROR':
        logging.info('QUEUE returned error!')
        return

    logging.info("Job = " + tree.findtext('scenario/title'))
    try:
        runjob(tree, model)
    except OSError:
        logging.error("Job failed with OSError")
    except subprocess.CalledProcessError, e:
        logging.error(">>Job failed with non-zero return code")
        logging.error(e.output)
        logging.error(">>Continuing")
    else:
        logging.info("Job Complete")


def json_response(rsp, model):
    """ Handle responses formatted in JSON.
    """

    rsp = rsp.json()
    if rsp.get('status', '') == 'EMPTY':
        logging.debug('json_response: pop_queue returned empty')
        return

    rundir = rsp.get('id').replace('-','_')
    if os.path.exists(rundir):
        shutil.rmtree(rundir)
    os.mkdir(rundir)

    logging.info('Job = ' + rsp.get('title'))
    if not rsp.get('cmdline', ''):
        logging.error('No cmdline given - assuming old model')
        print json.dumps(rsp)
        r = requests.get(rsp.get('config'), auth=('admin', 'leam4z'))
        tree = fromstring(r.text)
        runjob(tree, model)
        return

    logging.debug("cmdline = '%s'" % rsp.get('cmdline'))
    try:
        check_call(rsp.get('cmdline').split(), cwd=rundir)
    except OSError:
        logging.error('Job failed with OSError')
    except subprocess.CalledProcessError, e:
        logging.error('Job failed with non-zero return code')
    else:
        logging.info('Job %s completed successfully' % rsp.get('title'))


def main():

    usage = "usage: %prog [options] <Site URL>"

    parser = optparse.OptionParser(usage=usage)
    parser.add_option('-j', '--jobdir', default='/services/jobdir',
        help='default parent directory for all jobs')
    parser.add_option('-s', '--speed', default=20, type="int",
        help='set the polling speed to X seconds')
    parser.add_option('-i', '--idle', default=230, type="int",
        help='terminates server after number of empty polls')
    parser.add_option('-r', '--region', default='test',
        help='specifies the region being modeled (depricated)')
    parser.add_option('-p', '--popq', default='/pop_queue',
        help="append '/pop_queue' to the command line URL")
    parser.add_option('-d', '--debug', default=False, action='store_true',
        help='setting logging to DEBUG')

    (opts, args) = parser.parse_args()

    if opts.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    if len(args) != 1:
        parser.error("the URL to the Plone site is required")

    url = args[0]
    model = opts.region
    logging.debug("Modeling " + model)

    popq = url+opts.popq
    logging.debug("URL = " + popq)

    # primary loop
    while True:
        try:
            logging.debug("Popping the Queue")
            r = requests.get(popq, auth=('admin', 'leam4z'))
            r.raise_for_status()

        except requests.exceptions.ConnectionError:
            logging.error("Connection Error")
            sys.exit(1)

        except requests.exceptions.Timeout:
            logging.error("Connection Timeout")
            time.sleep(opts.speed)
            continue

        except requests.exceptions.HTTPError:
            logging.error("HTTP status error code = " + str(r.status_code))
            sys.exit(1)

        logging.debug('content-type: ' + r.headers['content-type'])

        if r.headers['content-type'].startswith('application/xml'):
            xml_response(r, model)

        elif r.headers['content-type'].startswith('application/json'):
            json_response(r, model)

        else:
            logging.error("Unknown content-type '%s'" % \
                    r.headers['content-type'])

        time.sleep(opts.speed)


if __name__ == '__main__':
    main()

