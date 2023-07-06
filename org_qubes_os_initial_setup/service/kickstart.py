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
#

from pyanaconda.core.kickstart import KickstartSpecification
from pyanaconda.core.kickstart.addon import AddonData
from pykickstart.errors import KickstartValueError
from pyanaconda.anaconda_loggers import get_module_logger

log = get_module_logger(__name__)

__all__ = ["QubesData"]


class QubesData(AddonData):
    """
    Class providing and storing data for the Qubes initial setup addon
    """

    bool_options = (
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
        "create_default_tpool",
    )

    def __init__(self):
        super(QubesData, self).__init__()

        self.system_vms = True

        self.disp_firewallvm_and_usbvm = True
        self.disp_netvm = False

        self.default_vms = True

        self.whonix_vms = None
        self.whonix_default = False

        self.usbvm = None
        self.usbvm_with_netvm = False
        self.allow_usb_mouse = False
        self.allow_usb_keyboard = None

        self.vg_tpool = None

        self.skip = False

        self.default_template = None
        self.templates_to_install = ["fedora", "debian", "whonix-gateway", "whonix-workstation"]

        self.qubes_user = None

    def handle_header(self, args, line_number=None):
        pass

    def handle_line(self, line, line_number=None):
        """

        :param line:
        :param line_number:
        :return:
        """

        line = line.strip()
        try:
            (param, value) = line.split(maxsplit=1)
        except ValueError:
            if " " not in line:
                param, value = line, ""
            else:
                raise KickstartValueError("invalid line: %s" % line)
        if param in self.bool_options:
            if value.lower() not in ("true", "false"):
                raise KickstartValueError("invalid value for bool property: %s" % line)
            bool_value = value.lower() == "true"
            setattr(self, param, bool_value)
        elif param == "default_template":
            self.default_template = value
        elif param == "templates_to_install":
            self.templates_to_install = [t for t in value.split(" ") if t]
        elif param == "lvm_pool":
            parsed = value.split("/")
            if len(parsed) != 2:
                raise KickstartValueError("invalid value for lvm_pool: %s" % line)
            self.vg_tpool = (parsed[0], parsed[1])
        else:
            raise KickstartValueError("invalid parameter: %s" % param)

    def __str__(self):
        section = "%addon org_qubes_os_initial_setup\n"

        for param in self.bool_options:
            section += "{} {!s}\n".format(param, getattr(self, param))

        if self.default_template:
            section += "default_template {}\n".format(self.default_template)
        section += "templates_to_install {}\n".format(
            " ".join(self.templates_to_install)
        )

        if self.vg_tpool:
            vg, tpool = self.vg_tpool
            section += "lvm_pool {}/{}\n".format(vg, tpool)

        section += "%end\n"
        return section


class QubesKickstartSpecification(KickstartSpecification):
    """Kickstart specification of the Hello World add-on."""

    addons = {"org_qubes_os_initial_setup": QubesData}
