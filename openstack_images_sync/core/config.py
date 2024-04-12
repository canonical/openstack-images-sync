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

import enum

import pydantic
import pydantic_settings

LOGGER_NAME: str = "openstack-image-sync"
LOG_FORMAT: str = (
    "%(asctime)s %(name)s.%(funcName)s:%(lineno)d %(levelname)s %(message)s"
)
LOG_LEVEL: str = "DEBUG"


class LogConfig(pydantic.BaseModel):
    """Logging configuration to be set for the server"""

    version: int = 1
    disable_existing_loggers: bool = False
    formatters: dict = {
        "default": {
            "()": "logging.Formatter",
            "fmt": LOG_FORMAT,
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    }
    handlers: dict = {
        "default": {
            "formatter": "default",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stderr",
        },
    }
    loggers: dict = {
        LOGGER_NAME: {"handlers": ["default"], "level": LOG_LEVEL},
    }


class Visibility(str, enum.Enum):
    PUBLIC = "public"
    PRIVATE = "private"
    COMMUNITY = "community"
    SHARED = "shared"


class SimpleStreamMirror(pydantic.BaseModel):
    url: str = pydantic.Field(description="URL of the mirror")
    # prefix: str = pydantic.Field(description="")
    path: str = pydantic.Field(
        description="Path to the index or products file in the mirror"
    )
    max_items: int = pydantic.Field(
        default=1, description="Store at most MAX items in the target"
    )
    keep_items: bool = pydantic.Field(
        default=False,
        description="Keep items in target up to MAX items even"
        " after they have fallen out of the source",
    )
    item_filters: list[str] = pydantic.Field(
        default=[
            "arch~(x86_64|amd64)",
            "ftype~(disk1.img|disk.img)",
        ],
        description="Filter expression for mirrored items."
        " Multiple filter arguments can be specified and will be combined with logical AND."
        " Expressions are key[!]=literal_string or key[!]~regexp.",
    )
    regions: list[str] = pydantic.Field(default=[], description="Regions to operate on")
    hypervisor_mapping: bool = pydantic.Field(
        default=False,
        description="Set hypervisor_type attribute on stored images"
        " and the virt attribute in the associated stream data."
        " This is useful in OpenStack Clouds which use"
        " multiple hypervisor types with in a single region.",
    )
    custom_properties: dict = pydantic.Field(
        default={}, description="Custom properties to add to glance image metadata"
    )
    visibility: Visibility = pydantic.Field(
        default=Visibility.PUBLIC, description="Visibility to apply to stored images"
    )
    content_id: str = pydantic.Field(
        default="%(region)s",
        description="Content ID to use for published data, may contain '%%(region)s'",
    )
    image_conversion: bool = pydantic.Field(
        default=False,
        description="Enable conversion of images to raw format"
        " using image import option in Glance.",
    )
    latest_property: bool = pydantic.Field(
        default=False,
        description="Set 'latest=true' property to latest synced os_version/architecture"
        " image metadata and remove latest property from the old images.",
    )


class Settings(pydantic_settings.BaseSettings):
    model_config = pydantic_settings.SettingsConfigDict(
        env_prefix="OIS_", yaml_file="config.yaml"
    )

    mirrors: list[SimpleStreamMirror] = [
        SimpleStreamMirror(
            url="http://cloud-images.ubuntu.com/releases",
            # prefix="ubuntu:released",
            path="streams/v1/index.sjson",
            item_filters=[
                "release~(bionic|focal|jammy)",
                "arch~(x86_64|amd64|arm64)",
                "ftype~(disk1.img|disk.img)",
            ],
            regions=["RegionOne"],
        )
    ]
    output_directory: str = "/tmp/simplestreams"
    cloud_name: str = pydantic.Field(
        default="simplestreams-glance-sync", description="Unique name for this cloud"
    )
    name_prefix: str = "auto-sync/"

    frequency: pydantic.PositiveInt = pydantic.Field(
        default=3600, description="Frequency of sync"
    )

    logging: LogConfig = LogConfig()

    @classmethod
    def load_from_dict(cls, data: dict) -> "Settings":
        return cls(**data)
