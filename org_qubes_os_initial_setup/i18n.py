#
# The Qubes OS Project, https://www.qubes-os.org/
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

"""Translation helpers for the addon.

The addon uses its own gettext domain, as recommended for Anaconda addons.
The lookup is done on every call (not bound once at import time), so the
language selected in Anaconda at runtime is respected.
"""

import gettext

TRANSLATION_DOMAIN = "qubes-anaconda-addon"


def _(string):
    """Translate string using the addon translation domain."""
    if not string:
        return ""
    return gettext.dgettext(TRANSLATION_DOMAIN, string)


def N_(string):
    """Mark string for translation without translating it."""
    return string
