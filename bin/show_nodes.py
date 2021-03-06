#!/usr/bin/python
# #
# Copyright 2013-2013 Ghent University
#
# This file is part of vsc-jobs,
# originally created by the HPC team of Ghent University (http://ugent.be/hpc/en),
# with support of Ghent University (http://ugent.be/hpc),
# the Flemish Supercomputer Centre (VSC) (https://vscentrum.be/nl/en),
# the Hercules foundation (http://www.herculesstichting.be/in_English)
# and the Department of Economy, Science and Innovation (EWI) (http://www.ewi-vlaanderen.be/en).
#
# http://github.com/hpcugent/vsc-jobs
#
# vsc-jobs is free software: you can redistribute it and/or modify
# it under the terms of the GNU Library General Public License as
# published by the Free Software Foundation, either version 2 of
# the License, or (at your option) any later version.
#
# vsc-jobs is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Library General Public License for more details.
#
# You should have received a copy of the GNU Library General Public License
# along with vsc-jobs. If not, see <http://www.gnu.org/licenses/>.
# #
"""
show_nodes prints nodes and node state information

@author: Stijn De Weirdt (Ghent University)
"""

import sys
from vsc import fancylogger
from vsc.utils.generaloption import simple_option
from vsc.utils.missing import any
from vsc.jobs.pbs.nodes import get_nodes, collect_nodeinfo, NDNAG_CRITICAL, NDNAG_WARNING, NDNAG_OK
from vsc.jobs.pbs.nodes import ND_NAGIOS_CRITICAL, ND_NAGIOS_WARNING, ND_NAGIOS_OK, ND_down, ND_offline, ND_free
from vsc.jobs.pbs.nodes import  ND_state_unknown, ND_bad, ND_error, ND_idle, ND_down_on_error, ND_job_exclusive
from vsc.jobs.pbs.moab import get_nodes_dict as moab_get_nodes_dict

_log = fancylogger.getLogger('show_nodes')

options = {
    'nagios':('Report in nagios format', None, 'store_true', False, 'n'),
    'regex':('Filter on regexp, data for first match', None, 'regex', None, 'r'),
    'allregex':('Combined with --regex/-r, return all data', None, 'store_true', False, 'A'),
    'anystate':('Matches any state (eg down_on_error node will also list as error)',
                None, 'store_true', False, 'a') ,
    'down':('Down nodes', None, 'store_true', False, 'D'),
    'downonerror':('Down on error nodes', None, 'store_true', False, 'E'),
    'offline':('Offline nodes', None, 'store_true', False, 'o'),
    'free':('Free nodes', None, 'store_true', False, 'f'),
    'job-exclusive':('Job-exclusive nodes', None, 'store_true', False, 'x'),
    'unknown':('State unknown nodes', None, 'store_true', False, 'u'),
    'bad':('Bad nodes (broken jobregex)', None, 'store_true', False, 'b'),
    'error':('Error nodes', None, 'store_true', False, 'e'),
    'idle':('Idle nodes', None, 'store_true', False, 'i'),
    'singlenodeinfo':(('Single (most-frequent) node information in key=value format'
                       '(no combination with other options)'), None, 'store_true', False, 'I'),
    'reportnodeinfo':('Report node information (no combination with other options)',
                      None, 'store_true', False, 'R'),
    'moab':('Use moab information (mdiag -n)', None, 'store_true', False, 'm'),
    'moabxml':('Use xml moab data from file (for testing)', None, 'store', None),
    'shorthost':('Return (short) hostname', None, 'store_true', False, 's'),
    }

go = simple_option(options)

all_states = ND_NAGIOS_CRITICAL + ND_NAGIOS_WARNING + ND_NAGIOS_OK
report_states = []
if go.options.down:
    report_states.append(ND_down)
if go.options.downonerror:
    report_states.append(ND_down_on_error)
if go.options.offline:
    report_states.append(ND_offline)
if go.options.free:
    report_states.append(ND_free)
if go.options.job_exclusive:
    report_states.append(ND_job_exclusive)
if go.options.unknown:
    report_states.append(ND_state_unknown)
if go.options.bad:
    report_states.append(ND_bad)
if go.options.error:
    report_states.append(ND_error)
if go.options.idle:
    report_states.append(ND_idle)

if len(report_states) == 0:
    report_states = all_states

if go.options.singlenodeinfo or go.options.reportnodeinfo:
    nodeinfo = collect_nodeinfo()[2]
    if len(nodeinfo) == 0:
        _log.error('No nodeinfo found')
        sys.exit(1)

    ordered = sorted(nodeinfo.items(), key=lambda x: x[1], reverse=True)

    if go.options.singlenodeinfo:
        if len(nodeinfo) > 1:
            msg = "Not all nodes have same parameters. Using most frequent ones."
            if go.options.reportnodeinfo:
                _log.warning(msg)
            else:
                _log.error(msg)

        # usage: export `./show_nodes -I` ; env |grep SHOWNODES_
        most_freq = ordered[0][0]
        msg = []
        msg.append("SHOWNODES_PPN=%d" % most_freq[0])
        msg.append("SHOWNODES_PHYSMEMMB=%d" % most_freq[1] / 1024 ** 2)
    else:
        msg = []
        for info, freq in ordered:
            msg.append("%d nodes with %d cores and %s MB physmem" % (freq, info[0], info[1] / 1024 ** 2))

    print "\n".join(msg)
    sys.exit(0)

if go.options.moab:

    if go.options.moabxml:
        try:
            moabxml = open(go.options.moabxml).read()
        except:
            _log.error('Failed to read moab xml from %s' % go.options.moabxml)
    else:
        moabxml = None
    nodes_dict = moab_get_nodes_dict(xml=moabxml)

    nodes = get_nodes(nodes_dict)
else:
    nodes = get_nodes()


# WARNING first, since that is the one that gives dependency on others
nagiosstatesorder = [NDNAG_WARNING, NDNAG_CRITICAL, NDNAG_OK]
nagiosexit = {
              NDNAG_CRITICAL: 2,
              NDNAG_WARNING: 1,
              NDNAG_OK: 0,
              }

nagios_res = {}
detailed_res = {}
nodes_found = []

for name, full_state in nodes:
    if go.options.regex and not go.options.regex.search(name):
        continue

    nagios_state = full_state['derived']['nagiosstate']
    if not nagios_state in nagios_res:
        nagios_res[nagios_state] = []

    state = full_state['derived']['state']
    states = full_state['derived']['states']

    if state == ND_free and ND_idle in states:
        state = ND_idle  # special case for idle
    if not state in detailed_res:
        detailed_res[state] = []

    if go.options.anystate:
        states_to_check = states
    else:
        states_to_check = [state]

    # filter the allowed states
    if any(x for x in states_to_check if x in report_states):
        nagios_res[nagios_state].append(states)
        detailed_res[state].append(states)
        nodes_found.append(name)

        if go.options.regex and not go.options.allregex:
            break


if go.options.regex and not go.options.allregex:
    # there should only be one node
    nagios_state, all_states = nagios_res.items()[0]
    states = all_states[0]
    if go.options.nagios:
        txt = "show_nodes %s - %s" % (nagios_state, ",".join(states))
        print txt
        sys.exit(nagiosexit[nagios_state])
    else:
        txt = "%s %s" % (nagios_state, ",".join(states))
        print txt
else:
    if go.options.nagios:
        header = 'show_nodes '
        txt = []
        total = 0
        for state in all_states:
            if state in detailed_res:
                nr = len(detailed_res[state])
            else:
                nr = 0
            total += nr
            txt.append("%s=%s" % (state, nr))
        txt.append("total=%s" % total)

        reported_state = [str(NDNAG_OK), '']
        if ND_bad in detailed_res:
            reported_state[0] = NDNAG_CRITICAL
            reported_state[1] = ' - %s bad nodes' % (len(detailed_res[ND_bad]))
        print "%s %s%s | %s" % (header, reported_state[0], reported_state[1], " ".join(txt))
        sys.exit(nagiosexit[reported_state[0]])
    else:
        # just print the nodes
        if go.options.shorthost:
            nodes_found = [x.split('.')[0] for x in nodes_found]
        print ' '.join(nodes_found)
