from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from backend.models.data_models import Article

def delete_old_articles(db: Session, days: int = 2):
    """
    Delete articles older than X days (default 2).
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    deleted = (
        db.query(Article)
        .filter(Article.published_at < cutoff)
        .delete(synchronize_session=False)
    )

    db.commit()
    return deleted
