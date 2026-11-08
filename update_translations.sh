#!/bin/bash
# Regenerate the translation template and merge it into existing .po files.
# Translations use the "qubes-anaconda-addon" gettext domain
# (see org_qubes_os_initial_setup/i18n.py).
set -e

cd "$(dirname "$0")"

DOMAIN=qubes-anaconda-addon
FILES=$(find org_qubes_os_initial_setup \( -name '*.py' -o -name '*.glade' \) | sort)

xgettext -d "$DOMAIN" -o "locale/$DOMAIN.pot" \
    --from-code=UTF-8 --add-comments=TRANSLATORS --keyword=N_ \
    --package-name="$DOMAIN" --package-version="$(cat version)" \
    $FILES

find locale/* -maxdepth 2 -mindepth 2 -type f -iname '*.po' \
    -exec msgmerge --update --backup=none {} "locale/$DOMAIN.pot" \;
