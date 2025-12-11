"""Seed random monthly JSON data into monthly categories tables.

Usage:
    python random_data.py [--start-year Y] [--end-year Y] [--seed S] [--dry-run]

Behavior:
- Finds all monthly categories via core.dynamic_mapping.get_monthly_map
- For each category, reads active FieldData entries and picks monthly fields (columns of JSON type)
- For each category inserts rows for every factory and every year in the requested range (default 2020-2025)
- If factory+year already exists in the table, the script will skip that row (no update)
- Values are 12-element lists (monthly) using unit/step heuristic to choose magnitude and precision
"""

import argparse
import random
import logging
from typing import List

from core.dependencies import SessionLocal
from core.dynamic_mapping import get_monthly_map
from core.models import FieldData, Factory, Category
from sqlalchemy import JSON
from sqlalchemy.exc import IntegrityError

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# heuristics for base magnitudes by unit token
UNIT_BASE_MAP = [
    (('%',), 50),
    (('t', 'T', '吨', 'T/'), 100),
    (('kg',), 1000),
    (('kwh', 'kWh', 'kW'), 10000),
    (('m3', 'm³'), 1000),
]


def detect_base_by_unit(unit: str) -> float:
    if not unit:
        return 100.0
    u = unit.lower()
    for tokens, base in UNIT_BASE_MAP:
        for t in tokens:
            if t.lower() in u:
                return float(base)
    # fallback
    return 100.0


def decimals_from_step(step) -> int:
    try:
        if not step:
            return 2
        s = float(step)
        if s <= 0:
            return 2
        # count decimals from step like 0.01 -> 2
        as_int = round(s, 8)
        d = 0
        while abs(as_int - round(as_int)) > 1e-9 and d < 8:
            as_int *= 10
            d += 1
        return d
    except Exception:
        return 2


def sample_monthly_list(unit: str, step, months: int = 12) -> List[float]:
    base = detect_base_by_unit(unit)
    dec = decimals_from_step(step)
    # choose a per-field mean within a reasonable multiplier to avoid extremes
    mean = random.uniform(max(0.1, base * 0.2), base * 2)
    values = []
    for _ in range(months):
        v = random.uniform(mean * 0.5, mean * 1.5)
        if '%' in (unit or ''):
            # clamp 0-100
            v = max(0.0, min(100.0, v))
        if dec == 0:
            v = int(round(v))
        else:
            v = round(v, dec)
        values.append(v)
    return values


def main(start_year: int = 2020, end_year: int = 2025, seed: int = None, dry_run: bool = False, update_existing: bool = False):
    """Insert monthly data for every factory and every year in [start_year, end_year].
    If a factory+year row already exists in the target table, skip it (no update) unless update_existing=True.
    """
    if seed is not None:
        random.seed(seed)
    db = SessionLocal()
    try:
        # factories list
        factories = [row[0] for row in db.query(Factory.name).all()]
        if not factories:
            logger.error("No factories found in database (Factory table empty). Aborting.")
            return
        logger.info(f"Found {len(factories)} factories; sample factories: {factories[:3]}")

        monthly_map = get_monthly_map(db)
        if not monthly_map:
            logger.error("No monthly categories found. Aborting.")
            return
        logger.info(f"Found {len(monthly_map)} monthly categories")

        years = list(range(start_year, end_year + 1))
        logger.info(f"Will ensure data for years: {years}")

        # iterate categories
        for cat_id, model in monthly_map.items():
            cat_row = db.query(Category).filter_by(id=cat_id).first()
            logger.info(f"Processing category {cat_id} - {cat_row.name_en if cat_row else 'unknown'}")
            # get fields metadata
            flds = db.query(FieldData).filter_by(category=cat_id, is_active=True).all()
            # determine which field name_en exist as JSON columns on model
            # build a normalized column lookup to allow tolerant matching
            cols = {c.name for c in model.__table__.columns}
            monthly_cols = {c.name for c in model.__table__.columns if isinstance(c.type, JSON) or 'json' in str(c.type).lower()}

            def _norm(x: str) -> str:
                if not x:
                    return ''
                return ''.join(ch.lower() for ch in x if ch.isalnum())

            col_norm_map = { _norm(name): name for name in monthly_cols }

            monthly_fields = []  # list of tuples (FieldData, model_column_name)
            for f in flds:
                # try exact matches first
                model_col = None
                if f.name_en and f.name_en in monthly_cols:
                    model_col = f.name_en
                else:
                    # try normalized name_en
                    n = _norm(f.name_en)
                    if n and n in col_norm_map:
                        model_col = col_norm_map[n]
                    else:
                        # try zh name normalized
                        n2 = _norm(f.name_zh)
                        if n2 and n2 in col_norm_map:
                            model_col = col_norm_map[n2]
                        else:
                            # try case-insensitive match
                            for col in monthly_cols:
                                if col.lower() == (f.name_en or '').lower():
                                    model_col = col
                                    break
                if model_col:
                    monthly_fields.append((f, model_col))
                else:
                    logger.debug(f"    field metadata '{f.name_en}' not mapped to model columns for category {cat_id}")
            if not monthly_fields:
                logger.info("  no monthly fields for this category, skipping")
                continue
            logger.info(f"  found {len(monthly_fields)} monthly fields (after matching to model columns)")

            inserted = 0
            skipped = 0
            errors = 0
            updated = 0

            # Determine primary key columns to build proper existence keys
            try:
                pk_cols = [c.name for c in model.__table__.primary_key.columns]
            except Exception:
                pk_cols = []
            cols_all = {c.name for c in model.__table__.columns}
            has_factory_col = 'factory' in cols_all
            has_year_col = 'year' in cols_all

            existing_keys = set()
            # preload existing keys according to primary key shape
            if pk_cols:
                # If primary key includes both factory and year -> keys are (factory, year)
                if 'factory' in pk_cols and 'year' in pk_cols:
                    rows = db.query(model).with_entities(getattr(model, 'factory'), getattr(model, 'year')).all()
                    for r in rows:
                        existing_keys.add((r[0], r[1]))
                # If primary key only includes factory -> keys are (factory,)
                elif 'factory' in pk_cols:
                    rows = db.query(model).with_entities(getattr(model, 'factory')).all()
                    for r in rows:
                        existing_keys.add((r[0],))
                # If primary key only includes year -> keys are (year,)
                elif 'year' in pk_cols:
                    rows = db.query(model).with_entities(getattr(model, 'year')).all()
                    for r in rows:
                        existing_keys.add((r[0],))
                else:
                    # fallback to factory/year combo if present
                    if has_factory_col and has_year_col:
                        rows = db.query(model).with_entities(getattr(model, 'factory'), getattr(model, 'year')).all()
                        for r in rows:
                            existing_keys.add((r[0], r[1]))
                    elif has_factory_col:
                        rows = db.query(model).with_entities(getattr(model, 'factory')).all()
                        for r in rows:
                            existing_keys.add((r[0],))
            else:
                # no primary key info; fallback
                if has_factory_col and has_year_col:
                    rows = db.query(model).with_entities(getattr(model, 'factory'), getattr(model, 'year')).all()
                    for r in rows:
                        existing_keys.add((r[0], r[1]))
                elif has_factory_col:
                    rows = db.query(model).with_entities(getattr(model, 'factory')).all()
                    for r in rows:
                        existing_keys.add((r[0],))

            for factory in factories:
                for year in years:
                    # determine key to check based on primary key columns
                    if pk_cols:
                        if 'factory' in pk_cols and 'year' in pk_cols:
                            key = (factory, year)
                        elif 'factory' in pk_cols:
                            key = (factory,)
                        elif 'year' in pk_cols:
                            key = (year,)
                        else:
                            # default fallback
                            key = (factory, year) if has_factory_col and has_year_col else ((factory,) if has_factory_col else (year,))
                    else:
                        # fallback behavior
                        if has_factory_col and has_year_col:
                            key = (factory, year)
                        elif has_factory_col:
                            key = (factory,)
                        else:
                            key = (year,)

                    if key in existing_keys:
                        if update_existing:
                            # perform update on the existing row (find it by primary key / filters)
                            try:
                                filters_check = {}
                                if pk_cols:
                                    for col in pk_cols:
                                        if col == 'factory':
                                            filters_check['factory'] = factory
                                        elif col == 'year':
                                            filters_check['year'] = year
                                else:
                                    if has_factory_col:
                                        filters_check['factory'] = factory
                                    if has_year_col:
                                        filters_check['year'] = year
                                if not filters_check:
                                    # cannot determine existing row to update; skip
                                    skipped += 1
                                    continue
                                existing_obj = db.query(model).filter_by(**filters_check).first()
                                if not existing_obj:
                                    # maybe key shape is (factory,) while filters_check used (factory,year)
                                    # fallback to factory-only filter
                                    if has_factory_col:
                                        existing_obj = db.query(model).filter_by(factory=factory).first()
                                if not existing_obj:
                                    skipped += 1
                                    continue
                                # update year column if present
                                if has_year_col:
                                    try:
                                        setattr(existing_obj, 'year', year)
                                    except Exception:
                                        pass
                                # update monthly fields
                                for ff, model_col in monthly_fields:
                                    vals = sample_monthly_list(ff.unit, ff.step, months=12)
                                    try:
                                        setattr(existing_obj, model_col, vals)
                                    except Exception as e:
                                        logger.warning(f"    failed to set model column {model_col} on existing row: {e}")
                                if not dry_run:
                                    try:
                                        db.commit()
                                        updated += 1
                                        logger.info(f"  updated existing row for {factory} {year} (category {cat_id})")
                                    except Exception as e:
                                        db.rollback()
                                        errors += 1
                                        logger.warning(f"  Error updating {factory} {year} in category {cat_id}: {e}")
                                else:
                                    logger.info(f"  [dry-run] would update existing row for {factory} {year} (category {cat_id})")
                                existing_keys.add(key)
                                continue
                            except Exception as e:
                                logger.warning(f"  update-existing failed for {factory} {year} in category {cat_id}: {e}")
                                skipped += 1
                                continue
                        else:
                            skipped += 1
                            continue

                    # create new row and set factory/year if columns exist
                    obj = model()
                    if has_factory_col:
                        setattr(obj, 'factory', factory)
                    if has_year_col:
                        setattr(obj, 'year', year)
                    # fill monthly fields with sampled data
                    for ff, model_col in monthly_fields:
                        vals = sample_monthly_list(ff.unit, ff.step, months=12)
                        try:
                            setattr(obj, model_col, vals)
                        except Exception as e:
                            logger.warning(f"    failed to set model column {model_col} for field {ff.name_en} on model {model}: {e}")
                    if dry_run:
                        logger.info(f"  [dry-run] would insert row for {factory} {year} with {len(monthly_fields)} fields")
                        # simulate insertion to avoid duplicates in dry-run
                        existing_keys.add(key)
                    else:
                        # final existence re-check to avoid race / unexpected PKs
                        try:
                            filters_check = {}
                            # use primary key based filters if possible to avoid mismatch
                            if pk_cols:
                                for col in pk_cols:
                                    if col == 'factory':
                                        filters_check['factory'] = factory
                                    elif col == 'year':
                                        filters_check['year'] = year
                            else:
                                if has_factory_col:
                                    filters_check['factory'] = factory
                                if has_year_col:
                                    filters_check['year'] = year

                            if filters_check:
                                now_exists = db.query(model).filter_by(**filters_check).first()
                                if now_exists:
                                    skipped += 1
                                    existing_keys.add(key)
                                    logger.info(f"  skipped (became existing) {factory} {year} (category {cat_id})")
                                    continue
                        except Exception:
                            # on any issue, fall back to attempting the insert and rely on IntegrityError handling
                            pass

                        try:
                            db.add(obj)
                            db.commit()
                            inserted += 1
                            existing_keys.add(key)
                            logger.info(f"  inserted row for {factory} {year} (category {cat_id})")
                        except IntegrityError as ie:
                            # likely unique constraint violation or similar - rollback and skip
                            db.rollback()
                            errors += 1
                            logger.warning(f"  IntegrityError inserting {factory} {year} in category {cat_id}: {ie.orig}")
                        except Exception as e:
                            db.rollback()
                            errors += 1
                            logger.warning(f"  Error inserting {factory} {year} in category {cat_id}: {e}")
            logger.info(f"Category {cat_id}: inserted={inserted}, updated={updated}, skipped_existing={skipped}, errors={errors}")
    finally:
        db.close()


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--start-year', type=int, default=2020, help='Start year (inclusive)')
    ap.add_argument('--end-year', type=int, default=2025, help='End year (inclusive)')
    ap.add_argument('--seed', type=int, default=None, help='Random seed')
    ap.add_argument('--dry-run', action='store_true', help='Do not commit changes')
    ap.add_argument('--update-existing', action='store_true', help='Update existing rows instead of skipping')
    args = ap.parse_args()
    main(start_year=args.start_year, end_year=args.end_year, seed=args.seed, dry_run=args.dry_run, update_existing=args.update_existing)
