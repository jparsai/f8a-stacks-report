"""Ingestion functions used to trigger a flow."""

import logging
from selinon import run_flow
from f8a_worker.utils import MavenCoordinates
import os

logger = logging.getLogger(__name__)


def server_create_analysis(ecosystem, package, version, force=False, force_graph_sync=False):
    """Create bayesianApiFlow handling analyses for specified EPV.

    :param ecosystem: ecosystem for which the flow should be run
    :param package: package for which should be flow run
    :param version: package version
    :param force: force run flow even specified EPV exists
    :param force_graph_sync: force synchronization to graph
    :return: dispatcher ID handling flow
    """
    component = MavenCoordinates.normalize_str(package) if ecosystem == 'maven' else package

    args = {
            "ecosystem": ecosystem,
            "force": force,
            "force_graph_sync": force_graph_sync,
            "name": component,
            "recursive_limit": 0,
            "version": version
        }

    if os.environ.get("WORKER_ADMINISTRATION_REGION", "") == "api":
        return server_run_flow('bayesianApiFlow', args)
    else:
        return server_run_flow('bayesianFlow', args)


def server_run_flow(flow_name, flow_args):
    """Run a flow.

    :param flow_name: name of flow to be run as stated in YAML config file
    :param flow_args: arguments for the flow
    :return: dispatcher ID handling flow
    """
    logger.info('Running flow {} for args {}'.format(flow_name, flow_args))
    dispacher_id = run_flow(flow_name, flow_args)

    return dispacher_id
