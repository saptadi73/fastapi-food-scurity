"""store payload selectors for multiplexed MQTT topics"""

import sqlalchemy as sa

from alembic import op

revision = "20260920_0034"
down_revision = "20260920_0033"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("device", sa.Column("mqtt_event", sa.String(length=200), nullable=True))
    op.add_column("device", sa.Column("mqtt_sensor", sa.Integer(), nullable=True))
    op.create_check_constraint("ck_device_mqtt_sensor", "device", "mqtt_sensor IS NULL OR mqtt_sensor >= 0")


def downgrade() -> None:
    op.drop_constraint("ck_device_mqtt_sensor", "device", type_="check")
    op.drop_column("device", "mqtt_sensor")
    op.drop_column("device", "mqtt_event")
