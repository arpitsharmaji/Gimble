from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..config import SUPPORT_CATEGORIES, settings
from ..db import get_db
from ..mailer import send_email
from ..models import User, SupportTicket
from ..schemas import SupportIn, AdminTicketIn
from ..security import optional_user, current_user, admin_user, rate_limit
from ..services import notify, audit

router = APIRouter(prefix="/api", tags=["support"])


def _t(t: SupportTicket) -> dict:
    return {"id": t.id, "category": t.category, "message": t.message, "status": t.status, "admin_reply": t.admin_reply,
            "name": t.name, "email": t.email, "user_id": t.user_id, "created_at": t.created_at.isoformat() + "Z"}


@router.post("/support", dependencies=[Depends(rate_limit("support", 5, 3600))])
def create_ticket(x: SupportIn, viewer: User | None = Depends(optional_user), db: Session = Depends(get_db)):
    if x.category not in SUPPORT_CATEGORIES:
        raise HTTPException(400, "Choose a valid category")
    t = SupportTicket(user_id=viewer.id if viewer else None, name=x.name.strip(), email=x.email, category=x.category, message=x.message.strip())
    db.add(t)
    db.flush()
    for a in db.query(User).filter_by(role="admin", active=True).all():
        notify(db, a.id, "report", f"New support ticket #{t.id} ({x.category.replace('_', ' ')})", "#/admin")
    db.commit()
    return {"message": f"Thanks - ticket #{t.id} is open. We reply by email within 1-2 working days.", "id": t.id}


@router.get("/support/mine")
def my_tickets(u: User = Depends(current_user), db: Session = Depends(get_db)):
    return [_t(t) for t in db.query(SupportTicket).filter_by(user_id=u.id).order_by(SupportTicket.id.desc()).limit(30).all()]


@router.get("/admin/support")
def admin_tickets(status: str = "open", a: User = Depends(admin_user), db: Session = Depends(get_db)):
    qs = db.query(SupportTicket)
    if status != "all":
        qs = qs.filter_by(status=status)
    return [_t(t) for t in qs.order_by(SupportTicket.id.desc()).limit(100).all()]


@router.patch("/admin/support/{ticket_id}")
def admin_reply(ticket_id: int, x: AdminTicketIn, a: User = Depends(admin_user), db: Session = Depends(get_db)):
    t = db.get(SupportTicket, ticket_id)
    if not t:
        raise HTTPException(404, "Ticket not found")
    if x.reply.strip():
        t.admin_reply = x.reply.strip()
        send_email(t.email, f"Re: your PairUp support request #{t.id}", x.reply.strip())
        if t.user_id:
            notify(db, t.user_id, "support", f"We replied to your support ticket #{t.id}", "#/support")
    if x.close:
        t.status = "closed"
    audit(db, a.id, "ticket_updated", f"ticket:{t.id}")
    db.commit()
    return {"status": t.status}
