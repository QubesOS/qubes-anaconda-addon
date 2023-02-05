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
import functools
from typing import Dict, List, Tuple

import dasbus.typing
from dasbus.server.interface import dbus_interface
from dasbus.typing import Bool
from pyanaconda.modules.common.base import KickstartModuleInterface

from org_qubes_os_initial_setup.constants import QUBES_INITIAL_SETUP
from org_qubes_os_initial_setup.utils import to_camel_case


@dbus_interface(QUBES_INITIAL_SETUP.interface_name)
class QubesInitialSetupInterface(KickstartModuleInterface):
    def connect_signals(self):
        super().connect_signals()
        for attr in self.implementation.properties:
            self.watch_property(
                to_camel_case(attr), getattr(self.implementation, attr + "_changed")
            )

    def _prop_getter(self, attr):
        return getattr(self.implementation, attr)

    def _prop_setter(self, attr, value):
        setattr(self.implementation, attr, value)

    # all attempts at dynamically create properties failed, as dasbus is rather
    # picky when constructing interface (it needs properties inheriting from
    # builtins.property, it needs proper type hints, etc)
    # the below section is generated with the following code:

    # for attr, ty in (
    #             ("system_vms", "Bool"),
    #             ("disp_firewallvm_and_usbvm", "Bool"),
    #             ("disp_netvm", "Bool"),
    #             ("default_vms", "Bool"),
    #             ("whonix_vms", "Bool"),
    #             ("whonix_default", "Bool"),
    #             ("usbvm", "Bool"),
    #             ("usbvm_with_netvm", "Bool"),
    #             ("skip", "Bool"),
    #             ("allow_usb_mouse", "Bool"),
    #             ("allow_usb_keyboard", "Bool"),
    #             ("vg_tpool", "Tuple[str, str]"),
    #             ("templates_to_install", "List[str]"),
    #             ("default_template", "str"),
    #     ):
    #         print(f"""
    #     @property
    #     def {to_camel_case(attr)}(self) -> {ty}:
    #         return self.implementation.{attr}
    #
    #     @{to_camel_case(attr)}.setter
    #     def {to_camel_case(attr)}(self, value: {ty}):
    #         self.implementation.{attr} = value""")

    @property
    def SystemVms(self) -> Bool:
        return self.implementation.system_vms

    @SystemVms.setter
    def SystemVms(self, value: Bool):
        self.implementation.system_vms = value

    @property
    def DispFirewallvmAndUsbvm(self) -> Bool:
        return self.implementation.disp_firewallvm_and_usbvm

    @DispFirewallvmAndUsbvm.setter
    def DispFirewallvmAndUsbvm(self, value: Bool):
        self.implementation.disp_firewallvm_and_usbvm = value

    @property
    def DispNetvm(self) -> Bool:
        return self.implementation.disp_netvm

    @DispNetvm.setter
    def DispNetvm(self, value: Bool):
        self.implementation.disp_netvm = value

    @property
    def DefaultVms(self) -> Bool:
        return self.implementation.default_vms

    @DefaultVms.setter
    def DefaultVms(self, value: Bool):
        self.implementation.default_vms = value

    @property
    def WhonixVms(self) -> Bool:
        return self.implementation.whonix_vms

    @WhonixVms.setter
    def WhonixVms(self, value: Bool):
        self.implementation.whonix_vms = value

    @property
    def WhonixDefault(self) -> Bool:
        return self.implementation.whonix_default

    @WhonixDefault.setter
    def WhonixDefault(self, value: Bool):
        self.implementation.whonix_default = value

    @property
    def Usbvm(self) -> Bool:
        return self.implementation.usbvm

    @Usbvm.setter
    def Usbvm(self, value: Bool):
        self.implementation.usbvm = value

    @property
    def UsbvmWithNetvm(self) -> Bool:
        return self.implementation.usbvm_with_netvm

    @UsbvmWithNetvm.setter
    def UsbvmWithNetvm(self, value: Bool):
        self.implementation.usbvm_with_netvm = value

    @property
    def Skip(self) -> Bool:
        return self.implementation.skip

    @Skip.setter
    def Skip(self, value: Bool):
        self.implementation.skip = value

    @property
    def AllowUsbMouse(self) -> Bool:
        return self.implementation.allow_usb_mouse

    @AllowUsbMouse.setter
    def AllowUsbMouse(self, value: Bool):
        self.implementation.allow_usb_mouse = value

    @property
    def AllowUsbKeyboard(self) -> Bool:
        return self.implementation.allow_usb_keyboard

    @AllowUsbKeyboard.setter
    def AllowUsbKeyboard(self, value: Bool):
        self.implementation.allow_usb_keyboard = value

    @property
    def CreateDefaultTpool(self) -> Bool:
        return self.implementation.create_default_tpool

    @CreateDefaultTpool.setter
    def CreateDefaultTpool(self, value: Bool):
        self.implementation.create_default_tpool = value

    @property
    def VgTpool(self) -> Tuple[str, str]:
        return self.implementation.vg_tpool

    @VgTpool.setter
    def VgTpool(self, value: Tuple[str, str]):
        self.implementation.vg_tpool = value

    @property
    def TemplatesToInstall(self) -> List[str]:
        return self.implementation.templates_to_install

    @TemplatesToInstall.setter
    def TemplatesToInstall(self, value: List[str]):
        self.implementation.templates_to_install = value

    @property
    def DefaultTemplate(self) -> str:
        return self.implementation.default_template

    @DefaultTemplate.setter
    def DefaultTemplate(self, value: str):
        self.implementation.default_template = value

    # read-only properties
    @property
    def LvmSetup(self) -> bool:
        return self.implementation.lvm_setup

    @property
    def FedoraAvailable(self) -> bool:
        return self.implementation.fedora_available

    @property
    def DebianAvailable(self) -> bool:
        return self.implementation.debian_available

    @property
    def WhonixAvailable(self) -> bool:
        return self.implementation.whonix_available

    @property
    def UsbvmAvailable(self) -> bool:
        return self.implementation.usbvm_available

    @property
    def TemplatesAliases(self) -> Dict[str, str]:
        return self.implementation.templates_aliases

    @property
    def UsbKeyboardsDetected(self) -> List[str]:
        return self.implementation.usb_keyboards_detected

    @property
    def CustomPool(self) -> bool:
        return self.implementation.custom_pool
