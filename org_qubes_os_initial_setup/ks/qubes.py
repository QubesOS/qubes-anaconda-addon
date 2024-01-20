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
import grp
import os
import glob
import distutils.version
import pyudev
import subprocess
import shutil

from pyanaconda.core import util
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.addons import AddonData
from pykickstart.errors import KickstartValueError
from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.progress import progress_message
log = get_module_logger(__name__)

__all__ = ['QubesData']

TEMPLATES_RPM_PATH = '/var/lib/qubes/template-packages/'


def get_template_rpm(template):
    try:
        rpm = glob.glob(TEMPLATES_RPM_PATH + 'qubes-template-%s-*.rpm' % template)[0]
    except IndexError:
        rpm = None
    return rpm


def is_template_rpm_available(template):
    return bool(get_template_rpm(template))


def get_template_version(template):
    rpm = get_template_rpm(template)
    if rpm:
        rpm = os.path.basename(rpm)
        version = rpm.replace('qubes-template-%s-' % template, '').split('-')[0]
        return version


def is_package_installed(pkgname):
    pkglist = subprocess.check_output(['rpm', '-qa', pkgname])
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
    keyboards = context.list_devices(subsystem='input', ID_INPUT_KEYBOARD='1')
    # allow sys-usb even if USB keyboard is present, as long as it's connected
    # to a controller that remains in dom0
    dom0_controllers = []
    with open('/proc/cmdline') as cmdline:
        for opt in cmdline.read().split():
            if opt.startswith('rd.qubes.dom0_usb='):
                dom0_controllers.extend(opt.split('=', 1)[1].split(','))
    usb_keyboards = []
    for kbd in keyboards:
        if not is_usb_device(kbd):
            continue
        for dom0_usb in dom0_controllers:
            if kbd.get('ID_PATH', '').startswith('pci-0000:' + dom0_usb + '-'):
                break
        else:
            usb_keyboards.append("{} {}".format(kbd.get('ID_VENDOR'), kbd.get('ID_MODEL')))
    return usb_keyboards


def started_from_usb():
    def get_all_used_devices(dev):
        stat = os.stat(dev)
        if stat.st_rdev:
            # XXX any better idea how to handle device-mapper?
            sysfs_slaves = '/sys/dev/block/{}:{}/slaves'.format(
                os.major(stat.st_rdev), os.minor(stat.st_rdev))
            if os.path.exists(sysfs_slaves):
                for slave_dev in os.listdir(sysfs_slaves):
                    for d in get_all_used_devices('/dev/{}'.format(slave_dev)):
                        yield d
            else:
                yield dev

    context = pyudev.Context()
    mounts = open('/proc/mounts').readlines()
    for mount in mounts:
        device = mount.split(' ')[0]
        if not os.path.exists(device):
            continue
        for dev in get_all_used_devices(device):
            udev_info = pyudev.Devices.from_device_file(context, dev)
            if is_usb_device(udev_info):
                return True

    return False


class QubesData(AddonData):
    """
    Class providing and storing data for the Qubes initial setup addon
    """

    bool_options = (
        'system_vms', 'disp_firewallvm_and_usbvm', 'disp_netvm','default_vms',
        'whonix_vms', 'whonix_default', 'usbvm', 'usbvm_with_netvm', 'skip',
        'allow_usb_mouse', 'allow_usb_keyboard',
    )

    def __init__(self, name):
        """

        :param name: name of the addon
        :type name: str
        """

        super(QubesData, self).__init__(name)
        self.fedora_available = is_template_rpm_available('fedora')
        self.debian_available = is_template_rpm_available('debian')

        self.whonix_available = (
                is_template_rpm_available('whonix-gw') and
                is_template_rpm_available('whonix-ws')) or (
                is_template_rpm_available('whonix-gateway') and
                is_template_rpm_available('whonix-workstation'))

        self.templates_aliases = {}
        self.templates_versions = {}
        if self.fedora_available:
            self.templates_versions['fedora'] = get_template_version('fedora')
            self.templates_aliases['fedora'] = 'Fedora %s' % self.templates_versions['fedora']

        if self.debian_available:
            self.templates_versions['debian'] = get_template_version('debian')
            self.templates_aliases['debian'] = 'Debian %s' % self.templates_versions['debian']

        if self.whonix_available:
            self.templates_versions['whonix'] = get_template_version('whonix-ws') or get_template_version('whonix-workstation')
            self.templates_aliases['whonix'] = 'Whonix %s' % self.templates_versions['whonix']

        self.usbvm_available = not started_from_usb()
        self.system_vms = True

        self.disp_firewallvm_and_usbvm = True
        self.disp_netvm = False

        self.default_vms = True

        self.whonix_vms = self.whonix_available
        self.whonix_default = False

        self.usb_keyboards_detected = usb_keyboard_present()
        self.usbvm = self.usbvm_available
        self.usbvm_with_netvm = False
        self.allow_usb_mouse = False
        self.allow_usb_keyboard = bool(self.usb_keyboards_detected)

        self.custom_pool = False
        self.vg_tpool = self.get_default_tpool()

        self.skip = False

        self.default_template = None
        self.whonix_templates = ['whonix-gateway', 'whonix-workstation']
        if is_template_rpm_available('whonix-gw'):
            self.whonix_templates = ['whonix-gw', 'whonix-ws']
        self.templates_to_install = \
            ['fedora', 'debian'] + self.whonix_templates

        # this is a hack, but initial-setup do not have progress hub or similar
        # provision for handling lengthy self.execute() call, so we must do it
        # ourselves
        self.gui_mode = False
        self.thread_dialog = None

        self.qubes_user = None

        self.seen = False

    def get_default_tpool(self):
        # get VG / pool where root filesystem lives
        fs_stat = os.stat("/")
        fs_major = (fs_stat.st_dev & 0xff00) >> 8
        fs_minor = fs_stat.st_dev & 0xff

        try:
            root_table = subprocess.check_output(["dmsetup",
                "-j", str(fs_major), "-m", str(fs_minor),
                "table"], stderr=subprocess.DEVNULL)
        except subprocess.CalledProcessError:
            return None

        _start, _sectors, target_type, target_args = \
            root_table.decode().split(" ", 3)
        if target_type not in ("thin", "linear"):
            return None

        lower_devnum, _args = target_args.split(" ")
        with open("/sys/dev/block/{}/dm/name"
            .format(lower_devnum), "r") as lower_devname_f:
            lower_devname = lower_devname_f.read().rstrip('\n')
        if lower_devname.endswith("-tpool"):
            # LVM replaces '-' by '--' if name contains
            # a hyphen
            lower_devname = lower_devname.replace('--', '=')
            volume_group, thin_pool, _tpool = \
                lower_devname.rsplit("-", 2)
            volume_group = volume_group.replace('=', '-')
            thin_pool = thin_pool.replace('=', '-')
        else:
            lower_devname = lower_devname.replace('--', '=')
            volume_group, _lv_name = \
                lower_devname.rsplit("-", 1)
            volume_group = volume_group.replace('=', '-')
            thin_pool = None

        if thin_pool in (None, "root-pool"):
            # search for "vm-pool" in the same VG
            try:
                cmd = ['lvs', '--noheadings',
                       '{}/vm-pool'.format(volume_group)]
                subprocess.check_call(cmd, stdout=subprocess.DEVNULL,
                                      stderr=subprocess.DEVNULL)
            except subprocess.CalledProcessError:
                return None
            else:
                thin_pool = 'vm-pool'

        if volume_group and thin_pool:
            return volume_group, thin_pool
        
        return None

    def handle_header(self, lineno, args):
        pass

    def handle_line(self, line):
        """

        :param line:
        :return:
        """

        line = line.strip()
        try:
            (param, value) = line.split(maxsplit=1)
        except ValueError:
            if ' ' not in line:
                param, value = line, ""
            else:
                raise KickstartValueError('invalid line: %s' % line)
        if param in self.bool_options:
            if value.lower() not in ('true', 'false'):
                raise KickstartValueError(
                    'invalid value for bool property: %s' % line)
            bool_value = value.lower() == 'true'
            setattr(self, param, bool_value)
        elif param == 'default_template':
            self.default_template = value
        elif param == 'templates_to_install':
            self.templates_to_install = [t for t in value.split(' ') if t]
        elif param == 'lvm_pool':
            parsed = value.split('/')
            if len(parsed) != 2:
                raise KickstartValueError(
                    'invalid value for lvm_pool: %s' % line)
            self.vg_tpool = (parsed[0], parsed[1])
        else:
            raise KickstartValueError('invalid parameter: %s' % param)
        self.seen = True

    def __str__(self):
        section = "%addon {}\n".format(self.name)

        for param in self.bool_options:
            section += "{} {!s}\n".format(param, getattr(self, param))

        if self.default_template:
            section += 'default_template {}\n'.format(self.default_template)
        section += 'templates_to_install {}\n'.format(' '.join(self.templates_to_install))

        if self.vg_tpool:
            vg, tpool = self.vg_tpool
            section += 'lvm_pool {}/{}\n'.format(vg, tpool)

        section += '%end\n'
        return section

    def execute(self, storage, ksdata, users, payload):
        if self.gui_mode:
            from ..gui import ThreadDialog
            self.thread_dialog = ThreadDialog(
                "Qubes OS Setup", self.do_setup, ())
            self.thread_dialog.run()
            self.thread_dialog.destroy()
        else:
            self.do_setup()

    def set_stage(self, stage):
        if self.thread_dialog is not None:
            self.thread_dialog.set_text(stage)
        else:
            print(stage)

    def do_setup(self):
        qubes_gid = grp.getgrnam('qubes').gr_gid

        qubes_users = grp.getgrnam('qubes').gr_mem

        if len(qubes_users) < 1:
            raise Exception(
                  "You must create a user account to create default VMs.")
        else:
            self.qubes_user = qubes_users[0]

        if self.skip:
            return

        errors = []

        os.setgid(qubes_gid)
        os.umask(0o0007)

        self.configure_default_kernel()
        self.configure_default_pool()
        self.install_templates()
        self.configure_dom0()
        self.configure_default_template()
        self.configure_qubes()
        if self.system_vms:
            self.configure_network()
        if self.usbvm and not self.usbvm_with_netvm:
            # Workaround for #1464 (so qvm.start from salt can't be used)
            self.run_command(['systemctl', 'start', 'qubes-vm@sys-usb.service'])
        if self.whonix_vms:
            # Workaround for #1464 (so qvm.start from salt can't be used)
            self.run_command(["systemctl", "start", "qubes-vm@sys-whonix.service"])

        try:
            self.configure_default_dvm()
        except Exception as e:
            errors.append(('Default DVM', str(e)))

        if errors:
            msg = ""
            for (stage, error) in errors:
                msg += "{} failed:\n{}\n\n".format(stage, error)

            raise Exception(msg)

    def run_command(self, command, stdin=None, ignore_failure=False):
        process_error = None

        try:
            sys_root = conf.target.system_root

            cmd = util.startProgram(command,
                stderr=subprocess.PIPE,
                stdin=stdin,
                root=sys_root)

            (stdout, stderr) = cmd.communicate()

            stdout = stdout.decode("utf-8")
            stderr = stderr.decode("utf-8")

            if not ignore_failure and cmd.returncode != 0:
                process_error = "{} failed:\nstdout: \"{}\"\nstderr: \"{}\"".format(command, stdout, stderr)

        except Exception as e:
            process_error = str(e)

        if process_error:
            log.error(process_error)
            raise Exception(process_error)

        return (stdout, stderr)

    def configure_default_kernel(self):
        self.set_stage("Setting up default kernel")
        installed_kernels = os.listdir('/var/lib/qubes/vm-kernels')
        installed_kernels = [distutils.version.LooseVersion(x) for x in installed_kernels
                             if x[0].isdigit()]
        default_kernel = str(sorted(installed_kernels)[-1])
        self.run_command([
            '/usr/bin/qubes-prefs', 'default-kernel', default_kernel])

    def configure_default_pool(self):
        self.set_stage("Setting up default pool")
        # At this stage:
        # 1) on default LVM install, '(qubes_dom0, vm-pool)' is available
        # 2) on non-default LVM install, we assume that user *should* have
        #    use custom thin pool to use
        if self.vg_tpool:
            volume_group, thin_pool = self.vg_tpool

            sys_root = conf.target.system_root

            cmd = util.startProgram(["qvm-pool", "info", thin_pool],
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                root=sys_root)
            cmd.wait()
            if cmd.returncode != 0:
                # create only if doesn't exist already
                self.run_command(['/usr/bin/qvm-pool', '--add', thin_pool, 'lvm_thin',
                                  '-o', 'volume_group={volume_group},thin_pool={thin_pool},revisions_to_keep=2'.format(
                        volume_group=volume_group, thin_pool=thin_pool)])
            self.run_command([
                '/usr/bin/qubes-prefs', 'default-pool', thin_pool])

    def install_templates(self):
        for template in self.templates_to_install:
            if template.startswith('whonix'):
                template_version = self.templates_versions['whonix']
            else:
                template_version = self.templates_versions[template]
            template_name = '%s-%s' % (template, template_version)
            self.set_stage("Installing TemplateVM %s" % template_name)
            rpm = get_template_rpm(template)
            self.run_command(['/usr/bin/qvm-template', 'install', '--nogpgcheck', rpm])

        # Clean RPM after install of selected ones
        if os.path.exists(TEMPLATES_RPM_PATH):
            shutil.rmtree(TEMPLATES_RPM_PATH)

    def configure_dom0(self):
        self.set_stage("Setting up administration VM (dom0)")

        for service in ['rdisc', 'kdump', 'libvirt-guests', 'salt-minion']:
            self.run_command(['systemctl', 'disable', '{}.service'.format(service) ], ignore_failure=True)
            self.run_command(['systemctl', 'stop',    '{}.service'.format(service) ], ignore_failure=True)

    def configure_default_template(self):
        self.set_stage('Setting default template')
        if self.default_template:
            self.default_template = '%s-%s' % (self.default_template, self.templates_versions[self.default_template])
            self.run_command(['/usr/bin/qubes-prefs', 'default-template', self.default_template])

    def configure_qubes(self):
        self.set_stage('Executing qubes configuration')

        states = []
        if self.system_vms:
            states.extend(
                ('qvm.sys-net', 'qvm.sys-firewall', 'qvm.default-dispvm'))
        if self.disp_firewallvm_and_usbvm:
            states.extend(
                ('pillar.qvm.disposable-sys-firewall',
                'pillar.qvm.disposable-sys-usb'))
        if self.disp_netvm:
            states.append('pillar.qvm.disposable-sys-net')
        if self.default_vms:
            states.extend(
                ('qvm.personal', 'qvm.work', 'qvm.untrusted', 'qvm.vault'))
        if self.whonix_available and self.whonix_vms:
            states.extend(
                ('qvm.sys-whonix', 'qvm.anon-whonix'))
        if self.whonix_default:
            states.append('qvm.updates-via-whonix')
        if self.usbvm:
            states.append('qvm.sys-usb')
        if self.usbvm_with_netvm:
            states.append('pillar.qvm.sys-net-as-usbvm')
        if self.allow_usb_mouse:
            states.append('pillar.qvm.sys-usb-allow-mouse')
        if self.allow_usb_keyboard:
            states.append('pillar.qvm.usb-keyboard')

        try:
            # get rid of initial entries (from package installation time)
            os.rename('/var/log/salt/minion', '/var/log/salt/minion.install')
        except OSError:
            pass

        # Refresh minion configuration to make sure all installed formulas are included
        self.run_command(['qubesctl', 'saltutil.clear_cache'])
        self.run_command(['qubesctl', 'saltutil.sync_all'])

        for state in states:
            print("Setting up state: {}".format(state))
            if state.startswith('pillar.'):
                self.run_command(['qubesctl', 'top.enable',
                    state[len('pillar.'):], 'pillar=True'])
            else:
                self.run_command(['qubesctl', 'top.enable', state])

        try:
            self.run_command(['qubesctl', '--all', 'state.highstate'])
            # After successful call disable all the states to not leave them
            # enabled, to not interfere with later user changes (like assigning
            # additional PCI devices)
            for state in states:
                if not state.startswith('pillar.'):
                    self.run_command(['qubesctl', 'top.disable', state])
        except Exception:
            raise Exception(
                    ("Qubes initial configuration failed. Login to the system and " +
                     "check /var/log/salt/minion for details. " +
                     "You can retry configuration by calling " +
                     "'sudo qubesctl --all state.highstate' in dom0 (you will get " +
                     "detailed state there)."))

    def configure_default_dvm(self):
        self.set_stage("Creating default DisposableVM")

        if self.default_template:
            dispvm_name = self.default_template + '-dvm'
            self.run_command(['/usr/bin/qubes-prefs', 'default-dispvm',
                dispvm_name])

    def configure_network(self):
        self.set_stage('Setting up networking')

        default_netvm = 'sys-firewall'
        updatevm = default_netvm
        if self.whonix_default:
            updatevm = 'sys-whonix'

        self.run_command(['/usr/bin/qvm-prefs', 'sys-firewall', 'netvm', 'sys-net'])
        self.run_command(['/usr/bin/qubes-prefs', 'default-netvm', default_netvm])
        self.run_command(['/usr/bin/qubes-prefs', 'updatevm', updatevm])
        self.run_command(['/usr/bin/qubes-prefs', 'clockvm', 'sys-net'])
        self.run_command(['/usr/bin/qvm-start', default_netvm])

