#!/usr/bin/env python
# -*- coding: latin-1 -*-
##
# Copyright 2013-2013 Ghent University
#
# This file is part of vsc-jobs,
# originally created by the HPC team of Ghent University (http://ugent.be/hpc/en),
# with support of Ghent University (http://ugent.be/hpc),
# the Flemish Supercomputer Centre (VSC) (https://vscentrum.be/nl/en),
# the Hercules foundation (http://www.herculesstichting.be/in_English)
# and the Department of Economy, Science and Innovation (EWI) (http://www.ewi-vlaanderen.be/en).
#
# All rights reserved.
#
##
"""
All things moab that are similar to all moab commands from which we want output.

@author Andy Georges
"""
import cPickle
import os
import pwd

from vsc.utils.cache import FileCache
from vsc.utils.fancylogger import getLogger
from vsc.utils.run import RunAsyncLoop


class MoabCommand(object):
    """Base class for Moab commands.

    Allows assembling information from a moab command output and store the relevant data somewhere.
    Allows caching of information to handle temporary failure of a target host/cluster.

    This class should be subclassed to allow actual running things
    """

    def __init__(self, cache_pickle=False, dry_run=False):
        """Initialise"""

        # data type for the resulting information
        self.info = None

        # dict mapping hosts to {master: FQN, showq_path: path}
        self.clusters = None

        # key to index the cache store
        self.cache_key = 'default'

        self.dry_run = dry_run
        self.cache_pickle = cache_pickle
        self.logger = getLogger(self.__class__.__name__)

    def _cache_pickle_directory(self):
        """Return the directory where we need to store the cached pickle file. Defaults to root's home."""
        home = pwd.getpwnam('root')[5]

        if not os.path.isdir(home):
            self.logger.raiseException("Homedir %s of root not found" % (home))

        return home

    def _cache_pickle_name(self, host):
        """Return the name of the pickle file to cache the retrieved information from the moab command."""
        pass

    def _load_pickle_cluster_file(self, host, raw=True):
        """Load the data from the pickled files.

        @type host: string

        @param host: cluster for which we load data

        @returns: representation of the showq output.
        """
        source = os.path.join(self._cache_pickle_directory(), self._cache_pickle_name(host))

        if raw:
            f = open(source, 'r')
            output = cPickle.load(f)
            f.close()
            return output
        else:
            cache = FileCache(source)
            return cache.load(self.cache_key)

    def _store_pickle_cluster_file(self, host, output, raw=True):
        """Store the result of the showq command in the relevant pickle file.

        @type output: string

        @param output: showq output information
        """

        dest = os.path.join(self._cache_pickle_directory(), self._cache_pickle_name(host))

        if not self.dry_run:
            if raw:
                f = open(dest, 'w')
                cPickle.dump(output, f)
                f.close()
            else:
                cache = FileCache(dest)
                cache.update(self.cache_key, output, 0)  # no retention of old data
                cache.close()
        else:
            self.logger.info("Dry run: skipping actually storing pickle files for cluster data")

    def _process_attributes(self, xml, attributes):
        """Fill in the attributes from the XML data.

        @type xml: etree structure for a job
        @type attributes: list of strings

        @param job: the XML returned by the moab command
        @param attributes: list of attributes we'd like to find in the XML

        Only places the attributes than are found in the description in the resulting disctionary, so no
        extraneous keys are put in the dict.
        """
        d = {}
        for attribute in attributes:
            try:
                d[attribute] = xml.attrib[attribute]
            except KeyError, err:
                self.logger.error("Failed to find attribute name %s in %s" % (attribute, xml.attrib))

        return d

    def _command(self, path, master):
        """If needed, transform the command prior to execution"""
        return [path]

    def _run_moab_command(self, commandlist, cluster, options):
        """Run the moab command and return the (processed) oututput.

        @type commandlist: list of strings
        @type cluster: string
        @type options: list of strings

        @param commandlist: path to the checkjob executable
        @param cluster: name of the cluster we are asking for information
        @param options: The options to pass to the checkjob command.

        @return: string if no processing is done, dict with the job information otherwise
        """
        (exit_code, output) = RunAsyncLoop.run(commandlist + options)

        if exit_code != 0:
            if self.cache_pickle:
                output = self._load_pickle_cluster_file(cluster)
            else:
                return None
        else:
            if self.cache_pickle:
                self._store_pickle_cluster_file(cluster, output)

        if not output:
            return None

        parsed = self.parser(cluster, output)
        if parsed:
            self.logger.debug("Returning parsed output for cluster %s" % (cluster))
            return parsed
        else:
            self.logger.debug("Returning raw output")
            return output

    def parser(self, host, txt):
        """Parse the returned XML into the desired data structure for further processing."""
        self.logger.debug("Empty parser used.")
        return None

    def get_moab_command_information(self):
        """Accumulate the checkjob information for the users on the given hosts.

        @type path: absolute path to the executable moab command
        @type master: the master that will provide the information
        """

        job_information = self.info()
        failed_hosts = []
        reported_hosts = []

        # Obtain the information from all specified hosts
        for (host, info) in self.clusters.items():

            master = info['master']
            path = info['path']
            command = self._command(path, master)

            host_job_information = self._run_moab_command(command, host, ["--host=%s" % (master), "--xml"])

            if not host_job_information:
                failed_hosts.append(host)
                self.logger.error("Couldn't collect info for host %s" % (host))
                self.logger.info("Trying to load cached pickle file for host %s" % (host))
            else:
                job_information.update(host_job_information)
                reported_hosts.append(host)

        return (job_information, reported_hosts, failed_hosts)


class SshMoabCommand(MoabCommand):
    """Similar to MaobCommand, but use ssh to contact the Moab master."""

    def _command(self, path, master):
        """Wrap the command in an ssh shell."""
        return ['ssh', master, path]
