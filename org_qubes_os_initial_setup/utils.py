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
import glob
import os
import subprocess

import pyudev

from org_qubes_os_initial_setup.constants import TEMPLATES_RPM_PATH

# dict[str, tuple(version, filename, alias, full-name)]
templates_cache = {}


def _template_alias_parts(template):
    # yield parts that are to be included in the final alias (to be joined
    # with a space)
    version_found = False
    for part in template.capitalize().split("-"):
        if part[0].isdigit():
            if version_found:
                # only first numer is considered a template version
                continue
            version_found = True
        # adjust cases for flavors
        if part == "xfce":
            part = "Xfce"
        elif part == "kde":
            part = "KDE"
        elif part == "gnome":
            part = "GNOME"
        yield part


def update_template_list():
    global templates_cache
    templates = {}
    try:
        for fname in os.listdir(TEMPLATES_RPM_PATH):
            if not fname.startswith("qubes-template-"):
                continue
            if not fname.endswith(".rpm"):
                continue
            tname = fname[len("qubes-template-") :]
            # then remove .noarch.rpm (also when different arch is set)
            tname = tname.rsplit(".", 2)[0]
            # then remove package version (-4.2.0-202301020304
            tname = tname.rsplit("-", 2)[0]
            parts = tname.split("-")
            # now drop numeric parts
            name_flavor = "-".join(p for p in parts if p[0].isalpha())
            version = [p for p in parts if p[0].isdigit()][0]
            alias = " ".join(_template_alias_parts(tname))
            templates[name_flavor] = (version, fname, alias, tname)
    except FileNotFoundError:
        # don't crash if no templates are available at all
        pass
    templates_cache = templates


def get_template_alias(template):
    if not templates_cache:
        update_template_list()
    if template in templates_cache:
        return templates_cache[template][2]
    return None


def get_template_rpm(template):
    if not templates_cache:
        update_template_list()
    if template in templates_cache:
        return TEMPLATES_RPM_PATH + templates_cache[template][1]
    return None


def is_template_rpm_available(template):
    return bool(get_template_rpm(template))


def get_template_version(template):
    if not templates_cache:
        update_template_list()
    if template in templates_cache:
        return templates_cache[template][0]
    return None


def get_template_name(template):
    if not templates_cache:
        update_template_list()
    if template in templates_cache:
        return templates_cache[template][3]
    return None


def get_templates_list():
    """Returns list of (name, alias) about available templates"""
    return [(name, info[2]) for name, info in templates_cache.items()]


def is_package_installed(pkgname):
    pkglist = subprocess.check_output(["rpm", "-qa", pkgname])
    return bool(pkglist)


def is_usb_device(device: pyudev.Device):
    if device.get("ID_USB_INTERFACES", False):
        return True
    for parent in device.ancestors:
        if parent.get("ID_USB_INTERFACES", False):
            return True
    return False


def usb_keyboard_present():
    context = pyudev.Context()
    keyboards = context.list_devices(subsystem="input", ID_INPUT_KEYBOARD="1")
    # allow sys-usb even if USB keyboard is present, as long as it's connected
    # to a controller that remains in dom0
    dom0_controllers = []
    with open("/proc/cmdline") as cmdline:
        for opt in cmdline.read().split():
            if opt.startswith("rd.qubes.dom0_usb="):
                dom0_controllers.extend(opt.split("=", 1)[1].split(","))
    usb_keyboards = []
    for kbd in keyboards:
        if not is_usb_device(kbd):
            continue
        for dom0_usb in dom0_controllers:
            if kbd.get("ID_PATH", "").startswith("pci-0000:" + dom0_usb + "-"):
                break
        else:
            usb_keyboards.append(
                "{} {}".format(kbd.get("ID_VENDOR"), kbd.get("ID_MODEL"))
            )
    return usb_keyboards


def started_from_usb():
    def get_all_used_devices(dev):
        stat = os.stat(dev)
        if stat.st_rdev:
            # XXX any better idea how to handle device-mapper?
            sysfs_slaves = "/sys/dev/block/{}:{}/slaves".format(
                os.major(stat.st_rdev), os.minor(stat.st_rdev)
            )
            if os.path.exists(sysfs_slaves):
                for slave_dev in os.listdir(sysfs_slaves):
                    for d in get_all_used_devices("/dev/{}".format(slave_dev)):
                        yield d
            else:
                yield dev

    context = pyudev.Context()
    mounts = open("/proc/mounts").readlines()
    for mount in mounts:
        device = mount.split(" ")[0]
        if not os.path.exists(device):
            continue
        for dev in get_all_used_devices(device):
            udev_info = pyudev.Devices.from_device_file(context, dev)
            if is_usb_device(udev_info):
                return True

    return False


def is_disp_preload_available() -> bool:
    try:
        total_memory = subprocess.check_output(["xl", "info", "total_memory"])
        total_memory_megabytes = int(total_memory.decode("ascii"))
    except subprocess.CalledProcessError:
        return False
    total_memory_gigabytes = int(total_memory_megabytes / 1000)
    # Some systems allocate kernel resources needed for some components such as
    # integrated graphics, thus deducting from total memory. Be lenient.
    return bool(total_memory_gigabytes >= 15)


def get_default_tpool():
    # get VG / pool where root filesystem lives
    fs_stat = os.stat("/")
    fs_major = (fs_stat.st_dev & 0xFF00) >> 8
    fs_minor = fs_stat.st_dev & 0xFF

    try:
        root_table = subprocess.check_output(
            ["dmsetup", "-j", str(fs_major), "-m", str(fs_minor), "table"],
            stderr=subprocess.DEVNULL,
        )
    except subprocess.CalledProcessError:
        return None

    _start, _sectors, target_type, target_args = root_table.decode().split(" ", 3)
    if target_type not in ("thin", "linear"):
        return None

    create = False
    lower_devnum, _args = target_args.split(" ")
    with open("/sys/dev/block/{}/dm/name".format(lower_devnum), "r") as lower_devname_f:
        lower_devname = lower_devname_f.read().rstrip("\n")
    if lower_devname.endswith("-tpool"):
        # LVM replaces '-' by '--' if name contains
        # a hyphen
        lower_devname = lower_devname.replace("--", "=")
        volume_group, thin_pool, _tpool = lower_devname.rsplit("-", 2)
        volume_group = volume_group.replace("=", "-")
        thin_pool = thin_pool.replace("=", "-")
    else:
        lower_devname = lower_devname.replace("--", "=")
        volume_group, _lv_name = lower_devname.rsplit("-", 1)
        volume_group = volume_group.replace("=", "-")
        thin_pool = None

    if thin_pool in (None, "root-pool"):
        thin_pool = "vm-pool"
        # search for "vm-pool" in the same VG
        try:
            cmd = ["lvs", "--noheadings", "{}/vm-pool".format(volume_group)]
            subprocess.check_call(
                cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
        except subprocess.CalledProcessError:
            create = True

    if volume_group and thin_pool:
        return volume_group, thin_pool, create

    return None


def to_camel_case(name: str):
    return name.title().replace("_", "")


class CamelCaseWrap:
    def __init__(self, model):
        self._model = model

    def __getattr__(self, item):
        return getattr(self._model, to_camel_case(item))

    def __setattr__(self, key, value):
        if key.startswith("_"):
            return super().__setattr__(key, value)
        return setattr(self._model, to_camel_case(key), value)
