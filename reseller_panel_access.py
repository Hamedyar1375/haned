from sqlalchemy import Column, Integer, TIMESTAMP, func, ForeignKey, UniqueConstraint
from app.db.base import Base

class ResellerPanelAccess(Base):
    __tablename__ = "reseller_panel_accesses"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    reseller_id = Column(Integer, ForeignKey("resellers.id", ondelete="CASCADE"), nullable=False)
    marzban_panel_id = Column(Integer, ForeignKey("marzban_panels.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("reseller_id", "marzban_panel_id", name="uq_reseller_panel_access"),
    )

    # No direct relationships needed here in the association table itself,
    # the relationships are defined in Reseller and MarzbanPanel models.
