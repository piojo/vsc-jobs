#!/usr/bin/python

from vsc import fancylogger
from vsc.jobs.pbs.jobs import get_jobs_dict
from vsc.jobs.pbs.nodes import get_nodes_dict

_log = fancylogger.getLogger('show_mem')

ns = {}
for node, details in get_nodes_dict().items():
    derived = details['derived']

    if not 'np' in derived:
        _log.warning('np not in derived from node %s' % node)
        continue
    np = derived['np']

    if not 'physmem' in derived:
        _log.warning('physmem not in derived from node %s' % node)
        continue
    mem = derived['physmem']

    ns[node] = {
                'np': np,
                'mem': mem,
                'avg': int(mem / np),
                }

toomuch = {}

for name, details in get_jobs_dict():
    derived = details['derived']
    if not derived['state'] in ('R',):
        continue

    if not 'user' in derived:
        _log.warning("no user in derived job name %s" % name)
        continue
    user = derived['user']

    if not 'used_mem' in derived:
        _log.warning("no used_mem in derived job name %s" % name)
        continue
    used_mem = derived['used_mem']

    if not 'exec_hosts' in derived:
        _log.warning("no exec_hosts in derived job name %s" % name)
        continue
    exec_hosts = derived['exec_hosts']

    cores = sum(exec_hosts.values())

    used_avg_mem = int(mem / cores)

    for host in exec_hosts.keys():
        # more then avg on node?
        if used_avg_mem > ns[host]['avg']:
            if not user in toomuch:
                toomuch[user] = {}
            if not host in toomuch[user]:
                toomuch[user][host] = []
            toomuch[user][host].append(name)

users = toomuch.keys()
users.sort()

txt = []
for user in users:
    txt.append("%s:" % user)
    for host, jobs in toomuch[user].items():
        txt += "\t%s:\t%s\n" % (host, ' '.join(jobs))

print "\n".join(txt)
