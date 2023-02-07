#
# Copyright (C) 2020  Frédéric Pierret <frederic.pierret@qubes-os.org>
# Copyright (C) 2016  M. Vefa Bicakci <m.v.b@runbox.com>
# Copyright (C) 2016  Qubes OS Developers
# Copyright (C) 2013  Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions of
# the GNU General Public License v.2, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY expressed or implied, including the implied warranties of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.  You should have received a copy of the
# GNU General Public License along with this program; if not, write to the
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
# Red Hat Author(s): Vratislav Podzimek <vpodzime@redhat.com>
#

"""Module with the QubesOsSpoke class."""
from org_qubes_os_initial_setup.utils import CamelCaseWrap

# will never be translated
_ = lambda x: x
N_ = lambda x: x

import os
import subprocess
import logging
import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("GLib", "2.0")

from gi.repository import Gtk
from pyanaconda.ui.categories.system import SystemCategory
from pyanaconda.ui.gui.spokes import NormalSpoke
from pyanaconda.ui.common import FirstbootOnlySpokeMixIn
from org_qubes_os_initial_setup.constants import QUBES_INITIAL_SETUP

# export only the spoke, no helper functions, classes or constants
__all__ = ["QubesOsSpoke"]
choices_instances = []


class QubesChoiceBase:
    def __init__(self, widget, location, indent=False, dependencies=None):
        self.widget = widget
        self.location = location
        self.indent = indent
        self.selected = None
        self._can_be_sensitive = True
        self.dependencies = dependencies or []

        if self.indent:
            self.outer_widget = Gtk.Alignment()
            self.outer_widget.add(self.widget)
            self.outer_widget.set_padding(0, 0, 20, 0)
        else:
            self.outer_widget = self.widget

    def connect(self, *args):
        raise NotImplementedError

    def set_selected(self, value):
        self.widget.set_active(value)
        if self.selected is not None:
            self.selected = value

    def set_sensitive(self, sensitive):
        if self._can_be_sensitive:
            self.widget.set_sensitive(sensitive)

    def get_selected(self):
        return (
            self.selected
            if self.selected is not None
            else self.widget.get_sensitive() and self.widget.get_active()
        )

    def are_dependencies_selected(self):
        dependencies_status = [
            dependency.get_selected() for dependency in self.dependencies
        ]
        return all(dependencies_status)

    def friend_on_toggled(self, *args):
        self.set_sensitive(self.are_dependencies_selected())


#
# Gtk.CheckButton
#
class QubesButtonChoice(QubesChoiceBase):
    def __init__(self, location, label, dependencies=None, indent=False):
        super().__init__(
            widget=Gtk.CheckButton(label=label),
            location=location,
            indent=indent,
            dependencies=dependencies,
        )
        self.label = label
        self.selected = None

        for dependency in self.dependencies:
            dependency.connect(self.friend_on_toggled)
            # trigger it now
            self.friend_on_toggled(dependency)

        choices_instances.append(self)

    def connect(self, *args):
        self.widget.connect("toggled", *args)
        self.widget.connect("notify::sensitive", *args)


#
# Gtk.Box -> Gtk.Label
#
class QubesChoiceMessage(QubesChoiceBase):
    def __init__(self, location=None, indent=False, icon_name=None):
        self.widget = Gtk.Box()
        if icon_name:
            icon = Gtk.IconTheme.get_default().load_icon(icon_name, 30, 0)
            icon_img = Gtk.Image.new_from_pixbuf(icon)
            self.widget.pack_start(icon_img, False, False, 0)
        self.label_widget = Gtk.Label()
        self.label_widget.set_xalign(0)
        self.label_widget.set_padding(0, 10)
        self.label_widget.set_line_wrap(True)
        self.widget.pack_start(self.label_widget, False, True, 10)
        self.widget.show_all()
        self.widget.set_no_show_all(True)
        super().__init__(widget=self.widget, location=location, indent=indent)
        choices_instances.append(self)


#
# Gtk.CheckButton
#
class QubesDisabledButtonChoice(QubesButtonChoice):
    def __init__(self, location, label, indent=False):
        super().__init__(location=location, label=label, indent=indent)
        self.widget.set_sensitive(False)
        self._can_be_sensitive = False


#
# Gtk.CheckButton
#
class QubesAdvancedChoice(QubesChoiceBase):
    def __init__(self, location, label, indent=False):
        super().__init__(
            widget=Gtk.CheckButton(label=label), location=location, indent=indent
        )
        self.widget.connect("toggled", self.disable_configuration)

    @staticmethod
    def disable_configuration(widget):
        activated = widget.get_active()

        for choice in choices_instances:
            choice.set_sensitive(
                not activated
                and (choice.dependencies is None or choice.are_dependencies_selected())
            )


#
# Gtk.Grid -> Gtk.Label | Gtk.ComboBoxText
#
class QubesListChoice(QubesChoiceBase):
    def __init__(self, location, label, entries=None, dependencies=None):
        super().__init__(widget=Gtk.Box(), location=location, dependencies=dependencies)
        self.entries = entries or []
        self.widget.set_homogeneous(True)
        self.label_widget = Gtk.Label(label=label, halign=1)
        self.combobox_widget = Gtk.ComboBoxText()

        for dependency in self.dependencies:
            dependency.connect(self.friend_on_toggled)
            # trigger it now
            self.friend_on_toggled(dependency)

        # column row width(number of columns) height(number of rows)
        self.widget.pack_start(self.label_widget, True, True, 0)
        self.widget.pack_start(self.combobox_widget, True, True, 0)

        for entry in entries:
            self.combobox_widget.append_text(entry)

        # choices_instances.append(self)

    def connect(self, *args):
        self.combobox_widget.connect("changed", *args)

    def get_selected(self):
        return self.entries

    def get_entry(self):
        return self.combobox_widget.get_active_text()

    def set_entry(self, entry):
        entry_index = self.entries.index(entry)
        self.combobox_widget.set_active(entry_index)


#
# Gtk.Label | Gtk.ComboBox
#
class QubesTemplateChoice(QubesListChoice):
    def __init__(self, location, entries, dependencies=None):
        super().__init__(
            location=location,
            label="Default:",
            entries=entries,
            dependencies=dependencies,
        )

        choices_instances.append(self)

    def friend_on_toggled(self, *args):
        self.combobox_widget.remove_all()
        self.entries = []
        for dependency in self.dependencies:
            if dependency.get_selected():
                self.entries.append(dependency.label)
                self.combobox_widget.append_text(dependency.label)
        self.combobox_widget.set_active(0)
        self.combobox_widget.set_sensitive(self.are_dependencies_selected())

    def are_dependencies_selected(self):
        dependencies_status = [
            dependency.get_selected() for dependency in self.dependencies
        ]
        # It is 'any' because it's a choice among a list
        return any(dependencies_status)


#
# Gtk.RadioButton
#
class QubesRadioChoice(QubesChoiceBase):
    def __init__(self, location, label, group=None, dependencies=None, indent=False):
        super().__init__(
            widget=Gtk.RadioButton(label=label, group=group),
            location=location,
            indent=indent,
            dependencies=dependencies,
        )

        choices_instances.append(self)

    def connect(self, *args):
        self.widget.connect("toggled", *args)
        self.widget.connect("notify::sensitive", *args)


#
# Gtk.Radiobutton
# Gtk.Radiobutton
#
class QubesInitThinPoolChoice(QubesChoiceBase):
    def __init__(self, location, thin_pools, indent=False):
        super().__init__(
            widget=Gtk.Box(orientation=1), location=location, indent=indent
        )
        self.thin_pools = thin_pools
        self.create_pool_choice = QubesRadioChoice(
            label=_("Create 'vm-pool' LVM thin pool"), location=None
        )
        self.widget.pack_start(self.create_pool_choice.widget, True, True, 0)

        self.custom_pool_choice = QubesRadioChoice(
            label=_("Use existing LVM thin pool"),
            group=self.create_pool_choice.widget,
            location=None,
        )
        self.widget.pack_start(self.custom_pool_choice.widget, True, True, 0)

        choices_instances.append(self)


#
# Gtk.Label | Gtk.ComboBox
# Gtk.Label | Gtk.ComboBox
#
class QubesPoolChoice(QubesChoiceBase):
    def __init__(self, location, pools, dependencies=None):
        super().__init__(
            widget=Gtk.Box(orientation=1), location=location, dependencies=dependencies
        )
        self.pools = {}
        for dependency in self.dependencies:
            dependency.connect(self.friend_on_toggled)
            # trigger it now
            self.friend_on_toggled(dependency)

        # Merge pools info
        if pools:
            for key, val in pools:
                self.pools[key] = self.pools.get(key, ()) + (val,)
        self.vgroups = list(self.pools.keys())

        self.vg_choice = QubesListChoice(
            label=_("LVM Volume Group:"),
            entries=self.vgroups,
            location=None,
        )
        self.tp_choice = QubesListChoice(
            label=_("LVM Thin Pool:"), entries=[], location=None
        )

        self.widget.pack_start(self.vg_choice.widget, True, True, 0)
        self.widget.pack_start(self.tp_choice.widget, True, True, 0)

        choices_instances.append(self)

        self.connect(self.on_vgroups_combo_changed)

    def connect(self, *args):
        self.vg_choice.combobox_widget.connect("changed", *args)

    def on_vgroups_combo_changed(self, *args):
        vgroup = self.get_vgroup()
        self.set_tpools_combo_entries(vgroup)

    def set_tpools_combo_entries(self, vgroup):
        self.tp_choice.combobox_widget.remove_all()
        if vgroup in self.pools.keys():
            for tpool in self.pools[vgroup]:
                self.tp_choice.combobox_widget.append_text(tpool)

        self.tp_choice.combobox_widget.set_active(0)

    def get_vgroup(self):
        return self.vg_choice.combobox_widget.get_active_text()

    def get_tpool(self):
        return self.tp_choice.combobox_widget.get_active_text()

    def set_vgroup(self, vgroup):
        try:
            vgroup_index = self.vgroups.index(vgroup)
        except ValueError:
            # In case of custom install and default value not available
            vgroup_index = 0
        self.vg_choice.combobox_widget.set_active(vgroup_index)

    def set_tpool(self, tpool):
        vgroup = self.get_vgroup()
        try:
            tpool_index = self.pools[vgroup].index(tpool)
        except (KeyError, ValueError):
            tpool_index = 0
        self.tp_choice.combobox_widget.set_active(tpool_index)


class QubesOsSpoke(FirstbootOnlySpokeMixIn, NormalSpoke):
    """
    Since this class inherits from the FirstbootOnlySpokeMixIn, it will
    only appear in the Initial Setup (successor of the Firstboot tool).

    :see: pyanaconda.ui.common.UIObject
    :see: pyanaconda.ui.common.Spoke
    :see: pyanaconda.ui.gui.GUIObject
    :see: pyanaconda.ui.common.FirstbootSpokeMixIn
    :see: pyanaconda.ui.gui.spokes.NormalSpoke

    """

    ### class attributes defined by API ###

    # list all top-level objects from the .glade file that should be exposed
    # to the spoke or leave empty to extract everything
    builderObjects = ["qubesOsSpokeWindow"]

    # the name of the main window widget
    mainWidgetName = "qubesOsSpokeWindow"

    # name of the .glade file in the same directory as this source
    uiFile = "qubes_os.glade"

    # category this spoke belongs to
    category = SystemCategory

    # spoke icon (will be displayed on the hub)
    # preferred are the -symbolic icons as these are used in Anaconda's spokes
    icon = "qubes-logo-icon"

    # title of the spoke (will be displayed on the hub)
    title = N_("_QUBES OS")

    ### methods defined by API ###
    def __init__(self, data, storage, payload):
        """
        :see: pyanaconda.ui.common.Spoke.__init__
        :param data: data object passed to every spoke to load/store data
                     from/to it
        :type data: pykickstart.base.BaseHandler
        :param storage: object storing storage-related information
                        (disks, partitioning, bootloader, etc.)
        :type storage: blivet.Blivet
        :param payload: object storing packaging-related information
        :type payload: pyanaconda.packaging.Payload

        """

        NormalSpoke.__init__(self, data, storage, payload)

        self.qubes_data = CamelCaseWrap(QUBES_INITIAL_SETUP.get_proxy())
        self.logger = logging.getLogger("anaconda")

        # TODO: consider moving to initialize()
        self.templatesBox = self.builder.get_object("templatesBox")
        self.mainBox = self.builder.get_object("mainBox")
        self.advancedBox = self.builder.get_object("advancedBox")

        self.lvm_cache = self.init_cache()
        self.thin_pools = None
        self.seen = False

        self.init_qubes_choices()

    def init_qubes_choices(self):
        default_templates = []
        if self.qubes_data.fedora_available:
            default_templates.append(self.qubes_data.templates_aliases["fedora"])
            self.choice_install_fedora = QubesButtonChoice(
                location=self.templatesBox,
                label=_(self.qubes_data.templates_aliases["fedora"]),
            )
        else:
            self.choice_install_fedora = QubesDisabledButtonChoice(
                location=self.templatesBox,
                label=_("Fedora not available"),
            )

        if self.qubes_data.debian_available:
            default_templates.append(self.qubes_data.templates_aliases["debian"])
            self.choice_install_debian = QubesButtonChoice(
                location=self.templatesBox,
                label=_(self.qubes_data.templates_aliases["debian"]),
            )
        else:
            self.choice_install_debian = QubesDisabledButtonChoice(
                location=self.templatesBox,
                label=_("Debian not available"),
            )

        if self.qubes_data.whonix_available:
            self.choice_install_whonix = QubesButtonChoice(
                location=self.templatesBox,
                label=_(self.qubes_data.templates_aliases["whonix"]),
            )
        else:
            self.choice_install_whonix = QubesDisabledButtonChoice(
                location=self.templatesBox, label=_("Whonix not available")
            )
            self.choice_whonix = self.choice_install_whonix
            self.choice_whonix_updates = self.choice_install_whonix

        self.choice_default_template = QubesTemplateChoice(
            location=self.templatesBox,
            entries=default_templates,
            dependencies=[
                self.choice_install_fedora,
                self.choice_install_debian,
            ],
        )

        self.choice_system = QubesButtonChoice(
            location=self.mainBox,
            label=_(
                "Create default system qubes (sys-net, sys-firewall, default DispVM)"
            ),
            dependencies=[self.choice_default_template],
        )

        self.choice_disp_firewallvm_and_usbvm = QubesButtonChoice(
            location=self.mainBox,
            label=_("Make sys-firewall and sys-usb disposable"),
            dependencies=[self.choice_system],
            indent=True,
        )

        self.choice_disp_netvm = QubesButtonChoice(
            location=self.mainBox,
            label=_("Make sys-net disposable"),
            dependencies=[self.choice_system],
            indent=True,
        )

        self.choice_default = QubesButtonChoice(
            location=self.mainBox,
            label=_(
                "Create default application qubes (personal, work, untrusted, vault)"
            ),
            dependencies=[self.choice_system],
        )

        if self.qubes_data.usbvm_available:
            self.choice_usb = QubesButtonChoice(
                location=self.mainBox,
                label=_(
                    "Use a qube to hold all USB controllers (create a new qube called sys-usb by default)"
                ),
                dependencies=[self.choice_default_template],
            )
        else:
            self.choice_usb = QubesDisabledButtonChoice(
                location=self.mainBox,
                label=_(
                    "USB qube configuration disabled - you are using USB keyboard or USB disk"
                ),
            )

        self.choice_usb_with_netvm = QubesButtonChoice(
            location=self.mainBox,
            label=_("Use sys-net qube for both networking and USB devices"),
            dependencies=[self.choice_usb],
            indent=True,
        )
        self.choice_allow_usb_mouse = QubesButtonChoice(
            location=self.mainBox,
            label=_("Automatically accept USB mice (discouraged)"),
            dependencies=[self.choice_usb],
            indent=True,
        )
        self.choice_allow_usb_keyboard = QubesButtonChoice(
            location=self.mainBox,
            label=_(
                "Automatically accept USB keyboard (discouraged if non-USB keyboard is available)"
            ),
            dependencies=[self.choice_usb],
            indent=True,
        )
        self.usb_keyboards_list = QubesChoiceMessage(
            location=self.mainBox,
            indent=True,
            icon_name="help-about",
        )

        if self.qubes_data.whonix_available:
            self.choice_whonix = QubesButtonChoice(
                location=self.mainBox,
                label=_(
                    "Create Whonix Gateway and Workstation qubes (sys-whonix, anon-whonix)"
                ),
                dependencies=[
                    self.choice_install_whonix,
                    self.choice_system,
                ],
            )

            self.choice_whonix_updates = QubesButtonChoice(
                location=self.mainBox,
                label=_(
                    "Enable system and template updates over the Tor anonymity network using Whonix"
                ),
                dependencies=[
                    self.choice_install_whonix,
                    self.choice_system,
                    self.choice_whonix,
                ],
                indent=True,
            )

        if self.qubes_data.lvm_setup:
            self.thin_pools = self.get_thin_pools()

            self.choice_select_pool = QubesInitThinPoolChoice(
                location=self.advancedBox,
                thin_pools=self.thin_pools,
            )

            choice_pool_list_kwargs = {
                "location": self.advancedBox,
                "pools": self.thin_pools,
                "dependencies": [],
            }
            if self.thin_pools:
                choice_pool_list_kwargs["dependencies"].append(
                    self.choice_select_pool.custom_pool_choice
                )
            self.choice_pool_list = QubesPoolChoice(**choice_pool_list_kwargs)

        self.check_advanced = QubesAdvancedChoice(
            location=self.advancedBox,
            label=_("Do not configure anything (for advanced users)"),
        )

        for choice in choices_instances:
            if not choice.location:
                continue
            choice.location.pack_start(choice.outer_widget, False, True, 0)

        # self.templatesBox.reorder_child(
        #     self.builder.get_object("templateDefaultBox"), -1
        # )

        self.advancedBox.pack_start(self.check_advanced.widget, False, True, 0)

        # Default choices
        if self.choice_install_fedora.widget.get_sensitive():
            self.choice_install_fedora.widget.set_active(True)
        if self.choice_install_debian.widget.get_sensitive():
            self.choice_install_debian.widget.set_active(True)
        if self.choice_install_whonix.widget.get_sensitive():
            self.choice_install_whonix.widget.set_active(True)

        self.choice_system.widget.set_active(True)

        self.choice_disp_firewallvm_and_usbvm.widget.set_active(True)

        self.choice_default.widget.set_active(True)

        if self.choice_whonix.widget.get_sensitive():
            self.choice_whonix.widget.set_active(True)

        if self.choice_usb.widget.get_sensitive():
            self.choice_usb.widget.set_active(True)

        if self.qubes_data.lvm_setup and self.thin_pools:
            # If available, we set Qubes default value
            # for VG and THIN POOL
            if ("qubes_dom0", "vm-pool") in self.thin_pools:
                self.choice_pool_list.set_vgroup("qubes_dom0")
                self.choice_pool_list.set_tpool("vm-pool")
            self.choice_pool_list.widget.set_sensitive(False)

    def initialize(self):
        """
        The initialize method that is called after the instance is created.
        The difference between __init__ and this method is that this may take
        a long time and thus could be called in a separated thread.

        :see: pyanaconda.ui.common.UIObject.initialize

        """

        NormalSpoke.initialize(self)

    def refresh(self):
        """
        The refresh method that is called every time the spoke is displayed.
        It should update the UI elements according to the contents of
        self.data.

        :see: pyanaconda.ui.common.UIObject.refresh

        """

        self.choice_install_fedora.set_selected(
            self.qubes_data.fedora_available
            and "fedora" in self.qubes_data.templates_to_install
        )

        self.choice_install_debian.set_selected(
            self.qubes_data.debian_available
            and "debian" in self.qubes_data.templates_to_install
        )

        self.choice_install_whonix.set_selected(
            self.qubes_data.whonix_available
            and "whonix-gw" in self.qubes_data.templates_to_install
            and "whonix-ws" in self.qubes_data.templates_to_install
        )

        self.choice_system.set_selected(self.qubes_data.system_vms)

        self.choice_disp_firewallvm_and_usbvm.set_selected(
            self.qubes_data.disp_firewallvm_and_usbvm
        )
        self.choice_disp_netvm.set_selected(self.qubes_data.disp_netvm)

        self.choice_default.set_selected(self.qubes_data.default_vms)

        self.choice_whonix.set_selected(self.qubes_data.whonix_vms)
        self.choice_whonix_updates.set_selected(self.qubes_data.whonix_default)

        self.choice_usb.set_selected(self.qubes_data.usbvm)
        self.choice_usb_with_netvm.set_selected(self.qubes_data.usbvm_with_netvm)
        self.choice_allow_usb_mouse.set_selected(self.qubes_data.allow_usb_mouse)
        self.choice_allow_usb_keyboard.set_selected(self.qubes_data.allow_usb_keyboard)
        if self.qubes_data.usb_keyboards_detected:
            self.usb_keyboards_list.label_widget.set_markup(
                _(
                    "<b>INFO:</b> the following USB keyboards will be connected to sys-usb:\n{}\n"
                    "<b>If you disable the option above, they will not function in Qubes.</b>"
                ).format(
                    "\n".join(
                        "- {}".format(k) for k in self.qubes_data.usb_keyboards_detected
                    )
                )
            )
        self.usb_keyboards_list.widget.set_visible(
            bool(self.qubes_data.usb_keyboards_detected)
        )

        if self.qubes_data.lvm_setup:
            self.choice_select_pool.create_pool_choice.set_selected(
                self.qubes_data.create_default_tpool
            )
            if self.qubes_data.vg_tpool and self.qubes_data.vg_tpool in self.thin_pools:
                vg, tpool = self.qubes_data.vg_tpool
                self.choice_pool_list.set_vgroup(vg)
                self.choice_pool_list.set_tpool(tpool)

        self.check_advanced.set_selected(self.qubes_data.skip)

    def apply(self):
        """
        The apply method that is called when the spoke is left. It should
        update the contents of self.data with values set in the GUI elements.

        """

        self.qubes_data.skip = self.check_advanced.get_selected()

        templates_to_install = []
        if self.choice_install_fedora.get_selected():
            templates_to_install.append("fedora")
        if self.choice_install_debian.get_selected():
            templates_to_install.append("debian")
        if self.choice_install_whonix.get_selected():
            templates_to_install += ["whonix-gw", "whonix-ws"]

        self.qubes_data.templates_to_install = templates_to_install
        for key, val in self.qubes_data.templates_aliases.items():
            if self.choice_default_template.get_entry() == val:
                self.qubes_data.default_template = key
                break

        self.qubes_data.system_vms = self.choice_system.get_selected()

        self.qubes_data.disp_firewallvm_and_usbvm = (
            self.choice_disp_firewallvm_and_usbvm.get_selected()
        )
        self.qubes_data.disp_netvm = self.choice_disp_netvm.get_selected()

        self.qubes_data.default_vms = self.choice_default.get_selected()

        self.qubes_data.usbvm = self.choice_usb.get_selected()
        self.qubes_data.usbvm_with_netvm = self.choice_usb_with_netvm.get_selected()
        self.qubes_data.allow_usb_mouse = self.choice_allow_usb_mouse.get_selected()

        self.qubes_data.whonix_vms = self.choice_whonix.get_selected()
        self.qubes_data.whonix_default = self.choice_whonix_updates.get_selected()

        if self.qubes_data.lvm_setup:
            if self.choice_select_pool.create_pool_choice.get_selected():
                self.qubes_data.create_default_tpool = True
            elif (
                self.choice_pool_list
                and self.choice_pool_list.get_vgroup()
                and self.choice_pool_list.get_tpool()
            ):
                self.qubes_data.vg_tpool = (
                    self.choice_pool_list.get_vgroup(),
                    self.choice_pool_list.get_tpool(),
                )
                self.qubes_data.create_default_tpool = False

        self.seen = True

    @property
    def ready(self):
        """
        The ready property that tells whether the spoke is ready (can be visited)
        or not. The spoke is made (in)sensitive based on the returned value.

        :rtype: bool

        """

        return True

    @property
    def completed(self):
        """
        The completed property that tells whether all mandatory items on the
        spoke are set, or not. The spoke will be marked on the hub as completed
        or uncompleted acording to the returned value.

        :rtype: bool

        """

        return self.seen

    @property
    def mandatory(self):
        """
        The mandatory property that tells whether the spoke is mandatory to be
        completed to continue in the installation process.

        :rtype: bool

        """
        return True

    @property
    def status(self):
        """
        The status property that is a brief string describing the state of the
        spoke. It should describe whether all values are set and if possible
        also the values themselves. The returned value will appear on the hub
        below the spoke's title.

        :rtype: str

        """

        return ""

    def execute(self):
        """
        The execute method that is called when the spoke is left. It is
        supposed to do all changes to the runtime environment according to
        the values set in the GUI elements.

        """

        pass

    @staticmethod
    def _parse_lvm_cache(lvm_output):
        result = {}

        for line in lvm_output.splitlines():
            line = line.decode().strip()
            vg_name, name, attr = line.split(";", 3)
            if "" in [vg_name, name]:
                continue
            name = vg_name + "/" + name
            result[name] = {"attr": attr}

        return result

    def init_cache(self):
        cmd = ["lvs", "--noheadings", "-o", "vg_name,name,lv_attr", "--separator", ";"]
        if os.getuid() != 0:
            cmd = ["sudo"] + cmd
        environ = os.environ.copy()
        environ["LC_ALL"] = "C.utf8"
        p = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            close_fds=True,
            env=environ,
        )
        out, err = p.communicate()
        return_code = p.returncode
        if return_code == 0 and err:
            self.logger.warning(err)
        elif return_code != 0:
            raise ValueError(err)

        return self._parse_lvm_cache(out)

    def get_thin_pools(self):
        """Return list of thin pools"""
        thpools = []
        if self.lvm_cache:
            for key, vol in self.lvm_cache.items():
                if vol["attr"] and vol["attr"][0] == "t":
                    # e.g. 'qubes_dom0/pool00'
                    parsed_key = key.split("/")
                    if len(parsed_key) == 2:
                        volume_group = parsed_key[0]
                        thin_pool = parsed_key[1]
                        thpools.append((volume_group, thin_pool))
        return thpools
