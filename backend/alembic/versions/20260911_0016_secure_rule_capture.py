"""Constrain privileged rule history capture to its two source tables.

Revision ID: 20260911_0016
Revises: 20260911_0015
"""
from alembic import op

revision = '20260911_0016'
down_revision = '20260911_0015'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE OR REPLACE FUNCTION public.fsos_capture_rule_revision() RETURNS trigger
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
        BEGIN
          IF TG_TABLE_SCHEMA <> 'public' OR TG_OP NOT IN ('INSERT','UPDATE') THEN
            RAISE EXCEPTION 'Invalid rule capture context' USING ERRCODE='42501';
          END IF;
          IF TG_TABLE_NAME = 'alarm_rule' THEN
            INSERT INTO public.alarm_rule_revision (revision_id,tenant_id,rule_id,version,snapshot)
              VALUES (gen_random_uuid(),NEW.tenant_id,NEW.alarm_rule_id,NEW.version,to_jsonb(NEW));
          ELSIF TG_TABLE_NAME = 'holding_rule' THEN
            INSERT INTO public.holding_rule_revision (revision_id,tenant_id,rule_id,version,snapshot)
              VALUES (gen_random_uuid(),NEW.tenant_id,NEW.holding_rule_id,NEW.version,to_jsonb(NEW));
          ELSE
            RAISE EXCEPTION 'Invalid rule capture source' USING ERRCODE='42501';
          END IF;
          RETURN NEW;
        END $$
    """)
    op.execute('REVOKE ALL ON FUNCTION public.fsos_capture_rule_revision() FROM PUBLIC')


def downgrade():
    op.execute("""
        CREATE OR REPLACE FUNCTION public.fsos_capture_rule_revision() RETURNS trigger
        LANGUAGE plpgsql SECURITY INVOKER AS $$
        BEGIN
          EXECUTE format('INSERT INTO public.%I (revision_id, tenant_id, rule_id, version, snapshot) '
                         'VALUES (gen_random_uuid(), $1, $2, $3, $4)', TG_ARGV[1])
            USING NEW.tenant_id, (to_jsonb(NEW)->>TG_ARGV[0])::uuid, NEW.version, to_jsonb(NEW);
          RETURN NEW;
        END $$
    """)
    op.execute('ALTER FUNCTION public.fsos_capture_rule_revision() RESET ALL')
    op.execute('GRANT EXECUTE ON FUNCTION public.fsos_capture_rule_revision() TO PUBLIC')
