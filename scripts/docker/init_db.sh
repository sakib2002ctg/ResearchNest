#!/usr/bin/env bash
set -euo pipefail
: "${APP_DATABASE_PASSWORD:?APP_DATABASE_PASSWORD is required}"
: "${MIGRATION_DATABASE_PASSWORD:?MIGRATION_DATABASE_PASSWORD is required}"
# Only runs when PostgreSQL initializes an empty data volume. psql reads secrets
# from its environment, rather than process arguments or echoed SQL text.
psql -X --no-password --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" --set=ON_ERROR_STOP=1 <<'SQL'
\getenv app_password APP_DATABASE_PASSWORD
\getenv migration_password MIGRATION_DATABASE_PASSWORD
\getenv database_name POSTGRES_DB
CREATE ROLE researchnest_app LOGIN PASSWORD :'app_password';
CREATE ROLE researchnest_migrator LOGIN PASSWORD :'migration_password';
CREATE EXTENSION IF NOT EXISTS vector;
REVOKE ALL ON DATABASE :"database_name" FROM PUBLIC;
GRANT CONNECT ON DATABASE :"database_name" TO researchnest_app, researchnest_migrator;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
ALTER SCHEMA public OWNER TO researchnest_migrator;
GRANT USAGE ON SCHEMA public TO researchnest_app;
ALTER DEFAULT PRIVILEGES FOR ROLE researchnest_migrator IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO researchnest_app;
ALTER DEFAULT PRIVILEGES FOR ROLE researchnest_migrator IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO researchnest_app;
SQL
