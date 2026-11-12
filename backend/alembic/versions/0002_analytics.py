"""Install analytical PostgreSQL views."""

from pathlib import Path

from alembic import op

revision = "0002_analytics"
down_revision = "def8f53327d8"
branch_labels = None
depends_on = None


def upgrade():
    sql = (Path(__file__).resolve().parents[3] / "sql" / "analytical_views.sql").read_text()
    op.get_bind().exec_driver_sql(sql)


def downgrade():
    for name in [
        "vw_delay_risk",
        "vw_demand_analysis",
        "vw_inventory_health",
        "vw_monthly_trends",
        "vw_centre_performance",
        "vw_zone_performance",
        "vw_partner_performance",
        "vw_daily_delivery_kpis",
        "vw_delivery_base",
    ]:
        op.execute(f"DROP VIEW IF EXISTS {name}")
