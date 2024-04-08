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

import pathlib
import sys
from logging.config import dictConfig

import click
import yaml

from openstack_images_sync.core import config as core_config
from openstack_images_sync.sync import synchronize

CONTEXT_SETTINGS = {"help_option_names": ["-h", "--help"]}


@click.group("openstack-images-sync", context_settings=CONTEXT_SETTINGS)
def cli():
    """Simple daemon to synchronize simplestreams sources to an OpenStack cloud."""
    pass


@cli.command()
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True, dir_okay=False, path_type=pathlib.Path),
    help="The configuration file to use.",
)
def sync(config: pathlib.Path | None):
    """Synchronize the images."""
    if config is None:
        settings = core_config.Settings()
    else:
        settings = core_config.Settings.load_from_dict(yaml.safe_load(config.read_text()))
    dictConfig(settings.logging.model_dump())
    synchronizer = synchronize.SimpleStreamsSynchronizer(settings)
    synchronizer.run()


@cli.command()
def generate_config():
    """Generate a default configuration file."""
    settings = core_config.Settings()
    yaml.dump(settings.model_dump(mode="json"), stream=sys.stdout)


if __name__ == "__main__":
    cli()
