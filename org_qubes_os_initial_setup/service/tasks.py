#
# The Qubes OS Project, https://www.qubes-os.org/
#
# Copyright (C) 2023 Marek Marczykowski-Górecki
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
import os
import shutil
import subprocess
from looseversion import LooseVersion

from pyanaconda.core import util
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.modules.common.task import Task

from org_qubes_os_initial_setup.constants import TEMPLATES_RPM_PATH
from org_qubes_os_initial_setup.utils import get_template_name, get_template_rpm

log = logging.getLogger(__name__)


class BaseQubesTask(Task):
    def run_command(self, command, stdin=None, ignore_failure=False):
        process_error = None
        # not really needed, but make static analysis happy
        stdout = None
        stderr = None

        try:
            sys_root = conf.target.system_root

            cmd = util.startProgram(
                command, stderr=subprocess.PIPE, stdin=stdin, root=sys_root
            )

            (stdout, stderr) = cmd.communicate()

            stdout = stdout.decode("utf-8")
            stderr = stderr.decode("utf-8")

            if not ignore_failure and cmd.returncode != 0:
                process_error = '{} failed:\nstdout: "{}"\nstderr: "{}"'.format(
                    command, stdout, stderr
                )

        except Exception as e:
            process_error = str(e)

        if process_error:
            log.error(process_error)
            raise Exception(process_error)

        return (stdout, stderr)


class DefaultKernelTask(BaseQubesTask):
    @property
    def name(self):
        return "Setup up default kernel"

    def run(self):
        installed_kernels = os.listdir("/var/lib/qubes/vm-kernels")
        installed_kernels = [
            LooseVersion(x) for x in installed_kernels if x[0].isdigit()
        ]
        default_kernel = str(sorted(installed_kernels)[-1])
        self.run_command(["/usr/bin/qubes-prefs", "default-kernel", default_kernel])


class DefaultPoolTask(BaseQubesTask):
    def __init__(self, create_default_tpool, vg_tpool):
        super().__init__()
        self.create_default_tpool = create_default_tpool
        self.vg_tpool = vg_tpool

    @property
    def name(self):
        return "Setup up default storage pool"

    def run(self):
        # At this stage:
        # 1) on default LVM install, '(qubes_dom0, vm-pool)' is not available yet
        # 2) on non-default LVM install, we assume that user *should* have
        #    use custom thin pool to use
        # 3) in all the cases, we propose to create 'vm-pool' in appropriate
        #    volume group
        if self.create_default_tpool:
            # should be pre-filled based on rootfs's volume group
            # see utils.get_default_tpool() called from QubesInitialSetup()
            if self.vg_tpool is None:
                raise Exception("Cannot find default LVM volume group")
            self.run_command(
                [
                    "/usr/sbin/lvcreate",
                    "-l",
                    "90%FREE",
                    "--thinpool",
                    self.vg_tpool[1],
                    self.vg_tpool[0],
                ],
            )
        if self.vg_tpool:
            volume_group, thin_pool = self.vg_tpool

            sys_root = conf.target.system_root

            cmd = util.startProgram(
                ["qvm-pool", "info", thin_pool],
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                root=sys_root,
            )
            cmd.wait()
            if cmd.returncode != 0:
                # create only if it doesn't exist already
                self.run_command(
                    [
                        "/usr/bin/qvm-pool",
                        "--add",
                        thin_pool,
                        "lvm_thin",
                        "-o",
                        "volume_group={volume_group},thin_pool={thin_pool},revisions_to_keep=2".format(
                            volume_group=volume_group, thin_pool=thin_pool
                        ),
                    ]
                )
            self.run_command(["/usr/bin/qubes-prefs", "default-pool", thin_pool])


class InstallTemplateTask(BaseQubesTask):
    def __init__(self, template):
        super().__init__()
        self.template = template

    @property
    def name(self):
        return "Install template " + self.template

    def run(self):
        template = self.template
        template_name = get_template_name(template)
        self.report_progress("Installing TemplateVM %s" % template_name)
        rpm = get_template_rpm(template)
        self.run_command(["/usr/bin/qvm-template", "install", "--nogpgcheck", rpm])


class CleanTemplatePkgsTask(BaseQubesTask):
    @property
    def name(self):
        return "Setting up default pool"

    def run(self):
        # Clean RPM after install of selected ones
        if os.path.exists(TEMPLATES_RPM_PATH):
            shutil.rmtree(TEMPLATES_RPM_PATH)


class ConfigureDom0Task(BaseQubesTask):
    @property
    def name(self):
        return "Setup up administration VM (dom0)"

    def run(self):
        for service in ["rdisc", "kdump", "libvirt-guests", "salt-minion"]:
            self.run_command(
                ["systemctl", "disable", "{}.service".format(service)],
                ignore_failure=True,
            )
            self.run_command(
                ["systemctl", "stop", "{}.service".format(service)], ignore_failure=True
            )


class SetDefaultTemplateTask(BaseQubesTask):
    def __init__(self, default_template):
        super().__init__()
        self.default_template = default_template

    @property
    def name(self):
        return "Setup default template"

    def run(self):
        if self.default_template:
            self.run_command(
                ["/usr/bin/qubes-prefs", "default-template", self.default_template]
            )


class ConfigureDefaultQubesTask(BaseQubesTask):
    def __init__(
        self,
        system_vms,
        usbvm,
        usbvm_with_netvm,
        disp_firewallvm_and_usbvm,
        allow_usb_keyboard,
        allow_usb_mouse,
        whonix_default,
        whonix_vms,
        default_vms,
        disp_netvm,
        disp_preload,
    ):
        super().__init__()
        self.system_vms = system_vms
        self.usbvm = usbvm
        self.usbvm_with_netvm = usbvm_with_netvm
        self.disp_firewallvm_and_usbvm = disp_firewallvm_and_usbvm
        self.allow_usb_keyboard = allow_usb_keyboard
        self.allow_usb_mouse = allow_usb_mouse
        self.whonix_default = whonix_default
        self.whonix_vms = whonix_vms
        self.default_vms = default_vms
        self.disp_netvm = disp_netvm
        self.disp_preload = disp_preload

    @property
    def name(self):
        return "Executing qubes configuration"

    def run(self):
        states = []
        if self.system_vms:
            states.extend(("qvm.sys-net", "qvm.sys-firewall", "qvm.default-dispvm"))
        if self.disp_firewallvm_and_usbvm:
            states.extend(
                ("pillar.qvm.disposable-sys-firewall", "pillar.qvm.disposable-sys-usb")
            )
        if self.disp_netvm:
            states.append("pillar.qvm.disposable-sys-net")
        if self.disp_preload:
            states.append("pillar.qvm.disposable-preload")
        if self.default_vms:
            states.extend(("qvm.personal", "qvm.work", "qvm.untrusted", "qvm.vault"))
        if self.whonix_vms:
            states.extend(("qvm.sys-whonix", "qvm.anon-whonix"))
        if self.whonix_default:
            states.append("qvm.updates-via-whonix")
        if self.usbvm:
            states.append("qvm.sys-usb")
        if self.usbvm_with_netvm:
            states.append("pillar.qvm.sys-net-as-usbvm")
        if self.allow_usb_mouse:
            states.append("pillar.qvm.sys-usb-allow-mouse")
        if self.allow_usb_keyboard:
            states.append("pillar.qvm.usb-keyboard")

        try:
            # get rid of initial entries (from package installation time)
            os.rename("/var/log/salt/minion", "/var/log/salt/minion.install")
        except OSError:
            pass

        # Refresh minion configuration to make sure all installed formulas are included
        self.run_command(["qubesctl", "saltutil.clear_cache"])
        self.run_command(["qubesctl", "saltutil.sync_all"])

        for state in states:
            print("Setting up state: {}".format(state))
            if state.startswith("pillar."):
                self.run_command(
                    ["qubesctl", "top.enable", state[len("pillar.") :], "pillar=True"]
                )
            else:
                self.run_command(["qubesctl", "top.enable", state])

        try:
            self.run_command(["qubesctl", "--all", "state.highstate"])
            # After successful call disable all the states to not leave them
            # enabled, to not interfere with later user changes (like assigning
            # additional PCI devices)
            for state in states:
                if not state.startswith("pillar."):
                    self.run_command(["qubesctl", "top.disable", state])
        except Exception:
            raise Exception(
                (
                    "Qubes initial configuration failed. Login to the system and "
                    + "check /var/log/salt/minion for details. "
                    + "You can retry configuration by calling "
                    + "'sudo qubesctl --all state.highstate' in dom0 (you will get "
                    + "detailed state there)."
                )
            )


class CreateDefaultDVMTask(BaseQubesTask):
    def __init__(self, default_template):
        super().__init__()
        self.default_template = default_template

    @property
    def name(self):
        return "Create default DisposableVM"

    def run(self):
        if self.default_template:
            dispvm_name = "default-dvm"
            self.run_command(["/usr/bin/qubes-prefs", "default-dispvm", dispvm_name])


class ConfigureNetworkTask(BaseQubesTask):
    def __init__(self, whonix_default, start_usb, start_whonix):
        super().__init__()
        self.whonix_default = whonix_default
        # should sys-usb be started too?
        self.start_usb = start_usb
        self.start_whonix = start_whonix

    @property
    def name(self):
        return "Setup networking"

    def run(self):
        default_netvm = "sys-firewall"
        updatevm = default_netvm
        if self.whonix_default:
            updatevm = "sys-whonix"

        self.run_command(["/usr/bin/qvm-prefs", "sys-firewall", "netvm", "sys-net"])
        self.run_command(["/usr/bin/qubes-prefs", "default-netvm", default_netvm])
        self.run_command(["/usr/bin/qubes-prefs", "updatevm", updatevm])
        self.run_command(["/usr/bin/qubes-prefs", "clockvm", "sys-net"])
        self.run_command(["/usr/bin/qvm-start", default_netvm])
        if self.start_usb:
            # Workaround for #1464 (so qvm.start from salt can't be used)
            self.run_command(["systemctl", "start", "qubes-vm@sys-usb.service"])
        if self.start_whonix:
            # Workaround for #1464 (so qvm.start from salt can't be used)
            self.run_command(["systemctl", "start", "qubes-vm@sys-whonix.service"])
