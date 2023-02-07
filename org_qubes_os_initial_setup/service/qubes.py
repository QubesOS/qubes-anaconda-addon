#
# The Qubes OS Project, https://www.qubes-os.org/
#
# Copyright (C) 2019 Marek Marczykowski-Górecki
#                           <marmarek@invisiblethingslab.com>
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public
# License as published by the Free Software Foundation; either
# version 2 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU General Public
# License along with this library; if not, see <https://www.gnu.org/licenses/>.
import logging

from dasbus.signal import Signal
from pyanaconda.core.dbus import DBus
from pyanaconda.modules.common.base import KickstartService
from pyanaconda.modules.common.containers import TaskContainer

from org_qubes_os_initial_setup.constants import QUBES_INITIAL_SETUP
from org_qubes_os_initial_setup.service.kickstart import (
    QubesKickstartSpecification,
    QubesData,
)
from org_qubes_os_initial_setup.service.qubes_interface import (
    QubesInitialSetupInterface,
)
from org_qubes_os_initial_setup.service.tasks import (
    DefaultKernelTask,
    DefaultPoolTask,
    InstallTemplateTask,
    CleanTemplatePkgsTask,
    ConfigureDom0Task,
    SetDefaultTemplateTask,
    ConfigureDefaultQubesTask,
    CreateDefaultDVMTask,
    ConfigureNetworkTask,
)
from org_qubes_os_initial_setup.utils import (
    is_template_rpm_available,
    get_template_version,
    started_from_usb,
    usb_keyboard_present,
    get_default_tpool,
)

log = logging.getLogger(__name__)


class QubesInitialSetup(KickstartService):
    properties = (
        "system_vms",
        "disp_firewallvm_and_usbvm",
        "disp_netvm",
        "default_vms",
        "whonix_vms",
        "whonix_default",
        "usbvm",
        "usbvm_with_netvm",
        "skip",
        "allow_usb_mouse",
        "allow_usb_keyboard",
        "vg_tpool",
        "templates_to_install",
        "default_template",
        "lvm_setup",
        "create_default_tpool",
    )

    def __init__(self):
        super().__init__()
        self.fedora_available = is_template_rpm_available("fedora")
        self.debian_available = is_template_rpm_available("debian")
        self.whonix_available = is_template_rpm_available(
            "whonix-gw"
        ) and is_template_rpm_available("whonix-ws")

        self.templates_aliases = {}
        self.templates_versions = {}
        if self.fedora_available:
            self.templates_versions["fedora"] = get_template_version("fedora")
            self.templates_aliases["fedora"] = (
                "Fedora %s" % self.templates_versions["fedora"]
            )

        if self.debian_available:
            self.templates_versions["debian"] = get_template_version("debian")
            self.templates_aliases["debian"] = (
                "Debian %s" % self.templates_versions["debian"]
            )

        if self.whonix_available:
            self.templates_versions["whonix"] = get_template_version("whonix-ws")
            self.templates_aliases["whonix"] = (
                "Whonix %s" % self.templates_versions["whonix"]
            )

        self.usbvm_available = not started_from_usb()
        self.usb_keyboards_detected = usb_keyboard_present()

        self._system_vms = True

        self._disp_firewallvm_and_usbvm = True
        self._disp_netvm = False

        self._default_vms = True

        self._whonix_vms = self.whonix_available
        self._whonix_default = False

        self.usb_keyboards_detected = usb_keyboard_present()
        self._usbvm = self.usbvm_available
        self._usbvm_with_netvm = False
        self._allow_usb_mouse = False
        self._allow_usb_keyboard = bool(self.usb_keyboards_detected)

        self._lvm_setup = True
        self._create_default_tpool = True

        default_tpool = get_default_tpool()
        if default_tpool:
            vg, tpool, create = default_tpool
            self._vg_tpool = vg, tpool
            self._create_default_tpool = create
        else:
            self._vg_tpool = ("", "")
            self._lvm_setup = False

        self._skip = False

        self._default_template = None
        self._templates_to_install = ["fedora", "debian", "whonix-gw", "whonix-ws"]

        self.qubes_user = None

        for attr in self.properties:
            setattr(self, attr + "_changed", Signal())

    def __getattr__(self, item):
        if item in self.properties:
            return getattr(self, "_" + item)
        return super().__getattr__(item)

    def __setattr__(self, key, value):
        if key in self.properties:
            setattr(self, "_" + key, value)
            getattr(self, key + "_changed").emit()
            return
        super().__setattr__(key, value)

    def prop_setter(self, attr, value):
        setattr(self, "_" + attr, value)
        getattr(self, attr + "_changed").emit()

    def publish(self):
        """Publish the module."""
        TaskContainer.set_namespace(QUBES_INITIAL_SETUP.namespace)
        DBus.publish_object(
            QUBES_INITIAL_SETUP.object_path, QubesInitialSetupInterface(self)
        )
        DBus.register_service(QUBES_INITIAL_SETUP.service_name)

    @property
    def kickstart_specification(self):
        return QubesKickstartSpecification

    def process_kickstart(self, data):
        """Process the kickstart data."""
        log.debug("Processing kickstart data...")
        ks_data = data.addons.org_qubes_os_initial_setup
        assert isinstance(ks_data, QubesData)
        # the need to copy this is stupid...
        for attr in ks_data.bool_options:
            if getattr(ks_data, attr) is not None:
                setattr(self, attr, getattr(ks_data, attr))
        if ks_data.vg_tpool is not None:
            self.vg_tpool = ks_data.vg_tpool
            self.custom_pool = True
        if ks_data.templates_to_install is not None:
            self.templates_to_install = ks_data.templates_to_install
        if ks_data.default_template is not None:
            self.default_template = ks_data.default_template

    def setup_kickstart(self, data):
        """Set the given kickstart data."""
        log.debug("Generating kickstart data...")
        ks_data = data.addons.org_qubes_os_initial_setup
        assert isinstance(ks_data, QubesData)
        # the need to copy this is stupid...
        for attr in ks_data.bool_options + ("templates_to_install", "default_template"):
            setattr(ks_data, attr, getattr(self, attr))
        if self.custom_pool:
            ks_data.vg_tpool = self.vg_tpool

    def install_with_tasks(self):
        if self.whonix_vms and not self.whonix_available:
            log.warning("Whonix selected but not available")
            self.whonix_vms = False

        if self.skip:
            return []

        start_usb = self.usbvm and not self.usbvm_with_netvm
        # resolve template version, if kickstart doesn't include it already
        if self.default_template and not any(
            x.isdigit() for x in self.default_template
        ):
            template_version = get_template_version(self.default_template)
            if template_version is not None:
                default_template = "%s-%s" % (
                    self.default_template,
                    get_template_version(self.default_template),
                )
            else:
                log.warning("Template '%s' not found", self.default_template)
                default_template = None
        else:
            default_template = self.default_template

        tasks = []
        tasks.append(DefaultKernelTask())
        if self.lvm_setup:
            tasks.append(
                DefaultPoolTask(
                    create_default_tpool=self.create_default_tpool,
                    vg_tpool=self.vg_tpool
                )
            )
        for template in self.templates_to_install:
            tasks.append(InstallTemplateTask(template=template))
        tasks.append(CleanTemplatePkgsTask())
        tasks.append(ConfigureDom0Task())
        if default_template:
            tasks.append(SetDefaultTemplateTask(default_template=default_template))
        tasks.append(
            ConfigureDefaultQubesTask(
                system_vms=self.system_vms,
                usbvm=self.usbvm,
                usbvm_with_netvm=self.usbvm_with_netvm,
                disp_firewallvm_and_usbvm=self.disp_firewallvm_and_usbvm,
                allow_usb_keyboard=self.allow_usb_keyboard,
                allow_usb_mouse=self.allow_usb_mouse,
                whonix_default=self.whonix_default,
                whonix_vms=self.whonix_vms,
                default_vms=self.default_vms,
                disp_netvm=self.disp_netvm,
            )
        )
        if default_template:
            tasks.append(CreateDefaultDVMTask(default_template=default_template))
        tasks.append(
            ConfigureNetworkTask(
                whonix_default=self.whonix_default, start_usb=start_usb
            )
        )
        return tasks

    def configure_with_tasks(self):
        return super().configure_with_tasks()
