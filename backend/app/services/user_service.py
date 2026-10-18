from typing import Optional, Dict, Any, Tuple, List
from sqlalchemy.orm import Session
from app.repositories.user_repository import UserRepository


class UserService:
    def __init__(self, db: Session):
        self.repo = UserRepository(db)

    def get_users_page(
        self,
        page: int = 1,
        page_size: int = 20,
        search: Optional[str] = None,
        department: Optional[str] = None,
        sort_by: str = "user_id",
        sort_dir: str = "asc"
    ) -> Dict[str, Any]:
        items, total = self.repo.get_paginated(
            page=page,
            page_size=page_size,
            search=search,
            department=department,
            sort_by=sort_by,
            sort_dir=sort_dir
        )
        total_pages = (total + page_size - 1) // page_size if total > 0 else 1
        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages
        }

    def get_user_detail(self, user_id: str) -> Optional[dict]:
        return self.repo.get_user_detail(user_id)
