#!/usr/bin/env bash
# Uses libpq environment/PGPASSFILE; credentials never enter command arguments.
set -euo pipefail
umask 077

fail() { printf '%s\n' "$1" >&2; exit 1; }
[[ $# -eq 1 ]] || fail 'Usage: backup_db.sh ARCHIVE.dump (set PGDATABASE, PGHOST, PGUSER and PGPASSFILE)'
[[ ${PGDATABASE:-} =~ ^[a-zA-Z_][a-zA-Z0-9_]*$ ]] || fail 'PGDATABASE must be an explicit database name, not a connection URI.'
for tool in pg_dump sha256sum mktemp; do command -v "$tool" >/dev/null || fail "Missing tool: $tool"; done
[[ $1 != *$'\n'* && $1 != *$'\r'* ]] || fail 'Archive path must be a single line.'
backup_dir=$(dirname -- "$1")
if [[ ! -d "$backup_dir" ]]; then mkdir -p -- "$backup_dir"; fi
backup_dir=$(cd -- "$backup_dir" && pwd -P)
archive="$backup_dir/$(basename -- "$1")"
[[ ! -e "$archive" && ! -L "$archive" && ! -e "$archive.sha256" && ! -L "$archive.sha256" ]] || fail 'Archive or checksum already exists; choose a new filename.'
printf 'Create a private backup of database %s? Type BACKUP: ' "$PGDATABASE" >&2
read -r confirmation || fail 'Backup canceled.'
[[ $confirmation == BACKUP ]] || fail 'Backup canceled.'
temporary=$(mktemp "$backup_dir/.researchnest-backup.XXXXXXXX")
checksum_file=$(mktemp "$backup_dir/.researchnest-checksum.XXXXXXXX")
error_file=$(mktemp "$backup_dir/.researchnest-error.XXXXXXXX")
cleanup() { rm -f -- "$temporary" "$checksum_file" "$error_file"; }
trap cleanup EXIT
if ! pg_dump --format=custom --no-owner --no-acl --no-password --file="$temporary" 2>"$error_file"; then
    fail 'Backup failed; check database connectivity and credentials. No archive was published.'
fi
[[ -s "$temporary" ]] || fail 'Backup failed: empty archive.'
checksum=$(sha256sum -- "$temporary")
checksum=${checksum%% *}
[[ $checksum =~ ^[0-9a-f]{64}$ ]] || fail 'Checksum generation failed.'
printf '%s\n' "$checksum" > "$checksum_file"
# Same-directory hard links publish complete files atomically and never replace
# an existing file or symlink, including a concurrent backup's output.
ln -- "$checksum_file" "$archive.sha256" || fail 'Checksum publication failed.'
if ! ln -- "$temporary" "$archive"; then
    rm -f -- "$archive.sha256"
    fail 'Archive publication failed; an existing archive was not overwritten.'
fi
printf 'Backup and SHA-256 checksum created: %s\n' "$archive"
