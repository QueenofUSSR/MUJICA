import threading
from typing import Dict, Optional, Tuple

from sqlalchemy import MetaData
from sqlalchemy.ext.automap import automap_base
from sqlalchemy.orm import Session

from core.models import Category

_LOCK = threading.Lock()
_CACHE: Dict[str, Optional[Dict]] = {"mappings": None, "periods": None}
_AUTOMAP_BASE = None


def _get_engine_from_session(db: Session):
    return getattr(db, "bind", None) or (db.get_bind() if hasattr(db, "get_bind") else None)


def _init_automap(engine):
    global _AUTOMAP_BASE
    if _AUTOMAP_BASE is not None:
        return _AUTOMAP_BASE
    Base = automap_base()
    metadata = MetaData()
    metadata.reflect(bind=engine)
    Base.prepare(engine, reflect=True)
    _AUTOMAP_BASE = Base
    return _AUTOMAP_BASE


def _find_class_in_core_models(name: str):
    try:
        import core.models as models_module
    except Exception:
        return None
    # 1) 按类名
    cls = getattr(models_module, name, None)
    if cls:
        return cls
    # 2) 按 __tablename__ 匹配
    for attr in dir(models_module):
        try:
            obj = getattr(models_module, attr)
            if getattr(obj, "__tablename__", None) == name:
                return obj
        except Exception:
            continue
    return None


def _automap_lookup(engine, hint: str, table_hint: str):
    Base = _init_automap(engine)
    # 1) 直接属性名
    cls = getattr(Base.classes, hint, None)
    if cls:
        return cls
    # 2) 按表名
    cls = getattr(Base.classes, table_hint, None)
    if cls:
        return cls
    # 3) 兜底模糊匹配
    for attr in dir(Base.classes):
        if hint.lower() in attr.lower() or table_hint.lower() in attr.lower():
            try:
                c = getattr(Base.classes, attr)
                if c is not None:
                    return c
            except Exception:
                continue
    return None


def load_category_mappings(db: Session, force: bool = False) -> Tuple[Dict[int, type], Dict[int, str]]:
    """
    返回 (category_id -> ORM class, category_id -> period_type)。
    会缓存结果，若需强制刷新传入 force=True。
    """
    global _CACHE
    with _LOCK:
        if _CACHE["mappings"] is not None and not force:
            return _CACHE["mappings"], _CACHE["periods"]

        rows = db.query(Category).filter_by(is_active=True).all()
        mappings = {}
        periods = {}
        engine = _get_engine_from_session(db)

        for row in rows:
            en = (row.name_en or "").strip()
            try:
                row_id = getattr(row, "id")
                if row_id is None:
                    continue
                row_id = int(row_id)
            except Exception:
                continue
            hint = (getattr(row, "model_class", "") or "").strip()
            cls = None
            # 1) 优先尝试 core.models 静态类/tablename 匹配
            if hint:
                cls = _find_class_in_core_models(hint)
            if not cls:
                cls = _find_class_in_core_models(en)
            # 2) 回退 automap（若提供 engine）
            if not cls and engine:
                cls = _automap_lookup(engine, hint or en, (hint or en))
            # 3) 如果最终有 cls，放入映射（以 category id 为键）
            if cls:
                mappings[row_id] = cls
                periods[row_id] = (row.period_type or "").lower()

        _CACHE["mappings"] = mappings
        _CACHE["periods"] = periods
        return mappings, periods


def get_monthly_map(db: Session, force: bool = False) -> Dict[int, type]:
    mappings, periods = load_category_mappings(db, force=force)
    monthly_map = {k: v for k, v in mappings.items() if periods.get(k) == "month"}
    return dict(sorted(monthly_map.items(), key=lambda kv: kv[0]))


def get_yearly_map(db: Session, force: bool = False) -> Dict[int, type]:
    mappings, periods = load_category_mappings(db, force=force)
    yearly_map = {k: v for k, v in mappings.items() if periods.get(k) == "year"}
    return dict(sorted(yearly_map.items(), key=lambda kv: kv[0]))


def get_model_for_category(db: Session, category_id: int, force: bool = False) -> Optional[type]:
    if not category_id:
        return None
    mappings, _ = load_category_mappings(db, force=force)
    return mappings.get(category_id)


# Optional helper to clear cache (管理员触发)
def clear_mapping_cache():
    global _CACHE
    with _LOCK:
        _CACHE = {"mappings": None, "periods": None}
