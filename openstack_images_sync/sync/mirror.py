# Copyright 2024 Canonical Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import novaclient.client as novaclient
import novaclient.v2.client as novaclient_v2
import simplestreams.mirrors.glance as sstream_glance
import simplestreams.openstack as sstream_openstack
import simplestreams.util as sstream_util

from openstack_images_sync.core import logging


class OISGlanceMirror(sstream_glance.GlanceMirror):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger = logging.get_logger()

        client = kwargs.get("client")

        if client is None:
            client = sstream_openstack
        self.keystone_creds = client.load_keystone_creds()
        service_info = sstream_openstack.get_service_conn_info(
            service="compute", **self.keystone_creds
        )
        self.nova_client: novaclient_v2.Client = novaclient.Client(
            "2.1", session=service_info["session"]
        )

    def remove_item(self, data, src, target, pedigree):
        """Remove an item from the target.

        If the item is in use, it will not be removed.
        """
        if "id" not in data:
            sstream_util.products_del(target, pedigree)
            return
        servers = self.nova_client.servers.list(
            search_opts={"all_tenants": 1, "image": data["id"]}
        )
        nb_servers = len(servers)
        if nb_servers > 0:
            self.logger.warning(
                "Not removing %s: %s. In use by %d server(s)",
                data["id"],
                data["name"],
                nb_servers,
            )
            return

        sstream_util.products_del(target, pedigree)
        self.logger.info("Removing %s: %s", data["id"], data["name"])
        self.gclient.images.delete(data["id"])
