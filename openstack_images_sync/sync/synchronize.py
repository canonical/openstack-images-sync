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

import datetime
import logging as std_logging
import pathlib
import time

import simplestreams.mirrors as sstream_mirrors
import simplestreams.mirrors.glance as sstream_glance
import simplestreams.objectstores as sstream_objectstores
import simplestreams.util as sstream_util

from openstack_images_sync.core import config, logging

KEYRING = "/usr/share/keyrings/ubuntu-cloudimage-keyring.gpg"


def policy(content: str, path: str):
    if path.endswith("sjson"):
        return sstream_util.read_signed(content, keyring=KEYRING)
    else:
        return content


class LogProgressAggregator(sstream_util.ProgressAggregator):
    remaining_items: dict

    def __init__(
        self,
        logger: std_logging.Logger,
        remaining_items: dict | None = None,
    ):
        super().__init__(remaining_items)
        self.logger = logger

    def progress_callback(self, progress):
        if self.current_file != progress["name"]:
            if self.remaining_items and self.current_file is not None:
                del self.remaining_items[self.current_file]
            self.current_file = progress["name"]
            self.last_emitted = 0
            self.current_written = 0

        size = float(progress["size"])
        written = float(progress["written"])
        self.current_written += written
        self.total_written += written
        interval = self.current_written - self.last_emitted
        if interval > size / 10:
            self.last_emitted = self.current_written
            progress["written"] = self.current_written
            self.emit(progress)

    def emit(self, progress):
        size = float(progress["size"])
        written = float(progress["written"])
        self.logger.debug(
            "%.2f %s (%d of %d images) - %.2f"
            % (
                written / size,
                progress["name"],
                self.total_image_count - len(self.remaining_items) + 1,
                self.total_image_count,
                float(self.total_written) / self.total_size,
            )
        )


class SimpleStreamsSynchronizer:
    def __init__(self, settings: config.Settings):
        self.settings = settings
        self.logger = logging.get_logger()

    def run(self):
        self.logger.info("Starting simplestreams synchronizer.")

        while True:
            self.sync_mirrors()
            match self.settings.frequency:
                case config.Frequency.HOURLY:
                    frequency = 3600
                case config.Frequency.DAILY:
                    frequency = 86400
                case config.Frequency.WEEKLY:
                    frequency = 604800
                case _:
                    frequency = 3600
            next_run = datetime.datetime.now() + datetime.timedelta(seconds=frequency)
            self.logger.info("Next synchronization: %s", next_run)
            time.sleep(frequency)

    def sync_mirrors(self):
        settings = self.settings
        output_directory = pathlib.Path(settings.output_directory)
        if not output_directory.exists():
            output_directory.mkdir(parents=True)
        for mirror in settings.mirrors:
            mirror_config = {
                "max_items": mirror.max_items,
                "keep_items": mirror.keep_items,
                "cloud_name": settings.cloud_name,
                "item_filters": mirror.item_filters,
                "hypervisor_mapping": mirror.hypervisor_mapping,
                "custom_properties": [
                    f"{k}={v}" for k, v in mirror.custom_properties.items()
                ],
                "visibility": mirror.visibility.value,
                "image_import_conversion": mirror.image_conversion,
                "set_latest_property": mirror.latest_property,
            }

            mirror_url, path = sstream_util.path_from_mirror_url(
                mirror.url,
                mirror.path,
            )

            smirror = sstream_mirrors.UrlMirrorReader(mirror_url, policy=policy)

            for region in mirror.regions:
                mirror_config["content_id"] = mirror.content_id.format(region=region)
                out_directory = output_directory / region
                if not out_directory.exists():
                    out_directory.mkdir(parents=True)
                tstore = sstream_objectstores.FileStore(out_directory)
                drmirror = sstream_glance.ItemInfoDryRunMirror(
                    config=mirror_config, objectstore=tstore
                )
                self.logger.info(
                    "Fetching images to sync for region: %s from %s", region, mirror_url
                )
                drmirror.sync(smirror, path)
                progressAggregator = LogProgressAggregator(self.logger, drmirror.items)
                self.logger.info(
                    "Fetched images to sync: %s",
                    ", ".join(drmirror.items.keys()) or "no images to sync",
                )
                tmirror = sstream_glance.GlanceMirror(
                    config=mirror_config,
                    objectstore=tstore,
                    region=region,
                    name_prefix=settings.name_prefix,
                    progress_callback=progressAggregator.progress_callback,
                )
                self.logger.info("Syncing region: %s from %s", region, mirror_url)
                tmirror.sync(smirror, path)
                self.logger.info("Synced region: %s from %s", region, mirror_url)
