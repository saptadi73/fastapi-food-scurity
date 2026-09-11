-- Jalankan dengan psql sebagai administrator PostgreSQL pada database postgres.
-- Khusus development: role/database bernama fsos.
\set ON_ERROR_STOP on

SELECT NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'fsos') AS create_fsos_role \gset
\if :create_fsos_role
CREATE ROLE fsos LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE;
\password fsos
\else
\echo 'Role fsos sudah ada; password dan atribut role tidak diubah.'
\endif

SELECT 'CREATE DATABASE fsos OWNER fsos'
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'fsos') \gexec

\connect fsos
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pgcrypto;
SELECT current_database(), extname, extversion
FROM pg_extension WHERE extname IN ('postgis', 'pgcrypto');
