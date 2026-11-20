#!/usr/bin/env bash
# Restore only trusted archives into an explicitly selected disposable/new target.
set -euo pipefail
umask 077

fail() { printf '%s\n' "$1" >&2; exit 1; }
[[ $# -eq 1 ]] || fail 'Usage: restore_db.sh ARCHIVE.dump (set target PGDATABASE and libpq credentials)'
[[ ${PGDATABASE:-} =~ ^[a-zA-Z_][a-zA-Z0-9_]*$ ]] || fail 'PGDATABASE must be an explicit target database name, not a connection URI.'
for tool in pg_restore sha256sum mktemp; do command -v "$tool" >/dev/null || fail "Missing tool: $tool"; done
archive=$1
[[ $archive != *$'\n'* && $archive != *$'\r'* ]] || fail 'Archive path must be a single line.'
[[ -f "$archive" && ! -L "$archive" && -f "$archive.sha256" && ! -L "$archive.sha256" ]] || fail 'A regular archive and its .sha256 sidecar are required.'
expected=$(cat -- "$archive.sha256")
[[ $expected =~ ^[0-9a-f]{64}$ ]] || fail 'Invalid SHA-256 sidecar.'
temporary=$(mktemp "${TMPDIR:-/tmp}/researchnest-restore.XXXXXXXX")
error_file=$(mktemp "${TMPDIR:-/tmp}/researchnest-restore-error.XXXXXXXX")
cleanup() { rm -f -- "$temporary" "$error_file"; }
trap cleanup EXIT
# Freeze a private copy before validating, so edits during the safety prompt
# cannot change the archive that will be restored.
cat -- "$archive" > "$temporary"
actual=$(sha256sum -- "$temporary")
actual=${actual%% *}
[[ $actual == "$expected" ]] || fail 'Checksum mismatch. The target database was not changed.'
pg_restore --list "$temporary" >/dev/null 2>"$error_file" || fail 'Invalid PostgreSQL archive. The target database was not changed.'
printf 'This replaces archive objects in database %s. Restore trusted backups only.\n' "$PGDATABASE" >&2
printf 'Type RESTORE %s to continue: ' "$PGDATABASE" >&2
read -r confirmation || fail 'Restore canceled.'
[[ $confirmation == "RESTORE $PGDATABASE" ]] || fail 'Restore canceled.'
if ! pg_restore --single-transaction --exit-on-error --clean --if-exists --no-owner --no-acl --no-password --dbname="$PGDATABASE" "$temporary" 2>"$error_file"; then
    fail 'Restore failed and its transaction was rolled back; check server logs and target permissions.'
fi
printf 'Restore completed for database %s. Run migrations, release verification and application checks before routing traffic.\n' "$PGDATABASE"
