# Copyright 2016 Cisco Systems, Inc.  All rights reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import os
import subprocess
import yaml

from log import LOG


class TrafficServerException(Exception):
    pass

class TrafficServer(object):
    """Base class for traffic servers."""

class TRexTrafficServer(TrafficServer):
    """Creates configuration file for TRex and runs server."""

    def __init__(self, trex_base_dir='/opt/trex'):
        contents = os.listdir(trex_base_dir)
        # only one version of TRex should be supported in container
        assert len(contents) == 1
        self.trex_dir = os.path.join(trex_base_dir, contents[0])

    def run_server(self, generator_config, filename='/etc/trex_cfg.yaml'):
        """Run TRex server for specified traffic profile.

        :param traffic_profile: traffic profile object based on config file
        :param filename: path where to save TRex config file
        """
        cfg = self.__save_config(generator_config, filename)
        cores = generator_config.cores
        vtep_vlan = generator_config.gen_config.get('vtep_vlan')
        sw_mode = "--software" if generator_config.software_mode else ""
        vlan_opt = "--vlan" if (generator_config.vlan_tagging or vtep_vlan) else ""
        if generator_config.mbuf_factor:
            mbuf_opt = "--mbuf-factor " + str(generator_config.mbuf_factor)
        else:
            mbuf_opt = ""
        subprocess.Popen(['nohup', '/bin/bash', '-c',
                          './t-rex-64 -i -c {} --iom 0 --no-scapy-server --close-at-end {} '
                          '{} {} --cfg {} &> /tmp/trex.log & disown'.format(cores, sw_mode,
                                                                            vlan_opt,
                                                                            mbuf_opt, cfg)],
                         cwd=self.trex_dir)
        LOG.info('TRex server is running...')

    def __save_config(self, generator_config, filename):
        ifs = ",".join([repr(pci) for pci in generator_config.pcis])

        result = """# Config generated by NFVbench
        - port_limit : 2
          version    : 2
          zmq_pub_port : {zmq_pub_port}
          zmq_rpc_port : {zmq_rpc_port}
          prefix       : {prefix}
          limit_memory : {limit_memory}
          interfaces : [{ifs}]""".format(zmq_pub_port=generator_config.zmq_pub_port,
                                         zmq_rpc_port=generator_config.zmq_rpc_port,
                                         prefix=generator_config.name,
                                         limit_memory=generator_config.limit_memory,
                                         ifs=ifs)
        if hasattr(generator_config, 'platform'):
            if generator_config.platform.master_thread_id \
                    and generator_config.platform.latency_thread_id:
                platform = """
          platform     :
            master_thread_id  : {master_thread_id}
            latency_thread_id : {latency_thread_id}
            dual_if:""".format(master_thread_id=generator_config.platform.master_thread_id,
                               latency_thread_id=generator_config.platform.latency_thread_id)
                result += platform

                for core in generator_config.platform.dual_if:
                    threads = ""
                    try:
                        threads = ",".join([repr(thread) for thread in core.threads])
                    except TypeError:
                        LOG.warn("No threads defined for socket %s", core.socket)
                    core_result = """
                  - socket : {socket}
                    threads : [{threads}]""".format(socket=core.socket, threads=threads)
                    result += core_result
            else:
                LOG.info("Generator profile 'platform' sub-properties are set but not filled in \
                         config file. TRex will use default values.")

        yaml.safe_load(result)
        if os.path.exists(filename):
            os.remove(filename)
        with open(filename, 'w') as f:
            f.write(result)

        return filename
