"""allow one-way MQTT processed transition while preserving evidence"""

from alembic import op

revision = "20260921_0035"
down_revision = "20260920_0034"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP TRIGGER telemetry_immutable ON public.mqtt_message_log")
    op.execute("""
        CREATE FUNCTION public.fsos_guard_mqtt_message_update() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
          IF OLD.processed IS FALSE
             AND NEW.processed IS TRUE
             AND (to_jsonb(NEW) - ARRAY['processed','updated_at','updated_by']::text[])
                 = (to_jsonb(OLD) - ARRAY['processed','updated_at','updated_by']::text[]) THEN
            RETURN NEW;
          END IF;
          RAISE EXCEPTION 'MQTT evidence is immutable except processed false-to-true transition'
            USING ERRCODE='55000';
        END $$
    """)
    op.execute("""
        CREATE TRIGGER mqtt_message_guarded_update BEFORE UPDATE ON public.mqtt_message_log
        FOR EACH ROW EXECUTE FUNCTION public.fsos_guard_mqtt_message_update()
    """)
    op.execute("""
        CREATE TRIGGER mqtt_message_no_delete BEFORE DELETE ON public.mqtt_message_log
        FOR EACH ROW EXECUTE FUNCTION public.fsos_reject_telemetry_mutation()
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER mqtt_message_no_delete ON public.mqtt_message_log")
    op.execute("DROP TRIGGER mqtt_message_guarded_update ON public.mqtt_message_log")
    op.execute("DROP FUNCTION public.fsos_guard_mqtt_message_update()")
    op.execute("""
        CREATE TRIGGER telemetry_immutable BEFORE UPDATE OR DELETE ON public.mqtt_message_log
        FOR EACH ROW EXECUTE FUNCTION public.fsos_reject_telemetry_mutation()
    """)
