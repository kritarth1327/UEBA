import json
from typing import Optional, List, Tuple
from sqlalchemy import select, func, or_, desc, asc
from sqlalchemy.orm import Session
from app.models.user import User
from app.models.prediction import ModelPrediction
from app.models.alert import Alert
from app.models.behavior import DailyBehaviorProfile


class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, user_id: str) -> Optional[User]:
        stmt = select(User).where(User.user_id == user_id)
        return self.db.scalars(stmt).first()

    def get_paginated(
        self,
        page: int = 1,
        page_size: int = 20,
        search: Optional[str] = None,
        department: Optional[str] = None,
        sort_by: str = "user_id",
        sort_dir: str = "asc"
    ) -> Tuple[List[dict], int]:
        """Fetch users with aggregated latest risk and alert count."""
        # Base query for counting
        base_query = select(User)
        if search:
            search_filter = f"%{search}%"
            base_query = base_query.where(
                or_(
                    User.user_id.ilike(search_filter),
                    User.employee_name.ilike(search_filter),
                    User.email.ilike(search_filter),
                    User.role.ilike(search_filter),
                )
            )
        if department:
            base_query = base_query.where(User.department == department)

        total = self.db.scalar(select(func.count()).select_from(base_query.subquery())) or 0

        # Subquery for latest prediction per user
        subq_latest_pred = (
            select(
                ModelPrediction.user_id,
                ModelPrediction.hybrid_risk_score,
                ModelPrediction.risk_level,
                ModelPrediction.date.label("latest_assessment_date"),
                func.row_number().over(
                    partition_by=ModelPrediction.user_id,
                    order_by=desc(ModelPrediction.date)
                ).label("rn")
            )
            .subquery()
        )
        latest_pred = select(
            subq_latest_pred.c.user_id,
            subq_latest_pred.c.hybrid_risk_score,
            subq_latest_pred.c.risk_level,
            subq_latest_pred.c.latest_assessment_date
        ).where(subq_latest_pred.c.rn == 1).subquery()

        # Subquery for alert count
        alert_cnt = (
            select(
                Alert.user_id,
                func.count(Alert.id).label("alert_count")
            )
            .group_by(Alert.user_id)
            .subquery()
        )

        query = (
            select(
                User,
                latest_pred.c.hybrid_risk_score,
                latest_pred.c.risk_level,
                latest_pred.c.latest_assessment_date,
                func.coalesce(alert_cnt.c.alert_count, 0).label("alert_count")
            )
            .outerjoin(latest_pred, User.user_id == latest_pred.c.user_id)
            .outerjoin(alert_cnt, User.user_id == alert_cnt.c.user_id)
        )

        if search:
            search_filter = f"%{search}%"
            query = query.where(
                or_(
                    User.user_id.ilike(search_filter),
                    User.employee_name.ilike(search_filter),
                    User.email.ilike(search_filter),
                    User.role.ilike(search_filter),
                )
            )
        if department:
            query = query.where(User.department == department)

        # Sorting
        order_col = User.user_id
        if sort_by == "risk":
            order_col = latest_pred.c.hybrid_risk_score
        elif sort_by == "alerts":
            order_col = alert_cnt.c.alert_count
        elif sort_by == "department":
            order_col = User.department

        if sort_dir.lower() == "desc":
            query = query.order_by(desc(order_col).nulls_last())
        else:
            query = query.order_by(asc(order_col).nulls_first())

        offset = (page - 1) * page_size
        results = self.db.execute(query.offset(offset).limit(page_size)).all()

        items = []
        for row in results:
            user_obj = row[0]
            items.append({
                "user_id": user_obj.user_id,
                "employee_name": user_obj.employee_name,
                "email": user_obj.email,
                "department": user_obj.department,
                "role": user_obj.role,
                "supervisor": user_obj.supervisor,
                "is_active": user_obj.is_active,
                "created_at": user_obj.created_at,
                "latest_risk_score": row[1],
                "latest_risk_level": row[2],
                "latest_assessment_date": row[3],
                "alert_count": int(row[4]),
            })

        return items, total

    def get_user_detail(self, user_id: str) -> Optional[dict]:
        user = self.get_by_id(user_id)
        if not user:
            return None

        # Latest prediction
        latest_pred = (
            self.db.scalars(
                select(ModelPrediction)
                .where(ModelPrediction.user_id == user_id)
                .order_by(desc(ModelPrediction.date))
            )
            .first()
        )

        total_profiles = (
            self.db.scalar(
                select(func.count(DailyBehaviorProfile.id))
                .where(DailyBehaviorProfile.user_id == user_id)
            )
            or 0
        )

        total_alerts = (
            self.db.scalar(
                select(func.count(Alert.id))
                .where(Alert.user_id == user_id)
            )
            or 0
        )

        return {
            "user_id": user.user_id,
            "employee_name": user.employee_name,
            "email": user.email,
            "department": user.department,
            "role": user.role,
            "supervisor": user.supervisor,
            "is_active": user.is_active,
            "created_at": user.created_at,
            "updated_at": user.updated_at,
            "latest_risk_score": latest_pred.hybrid_risk_score if latest_pred else None,
            "latest_risk_level": latest_pred.risk_level if latest_pred else None,
            "latest_assessment_date": latest_pred.date if latest_pred else None,
            "total_profiles_count": total_profiles,
            "total_alerts_count": total_alerts,
        }

    def create(self, user: User) -> User:
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user
