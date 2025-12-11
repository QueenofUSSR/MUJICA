import json
import os
import sys
import re
import uuid

from sqlalchemy import create_engine, MetaData, select, literal, text
from sqlalchemy.schema import CreateTable

# 从项目配置读取默认数据库 URL（Postgres 配置）
try:
    from backend.core.dependencies import SQLALCHEMY_DATABASE_URL
except Exception:
    SQLALCHEMY_DATABASE_URL = None

DEFAULT_URL = os.getenv("DATABASE_URL") or SQLALCHEMY_DATABASE_URL
DEFAULT_OUT = "../static/init_db.sql"
DEFAULT_TABLES = None


def quote_name(preparer, name):
    return preparer.quote(name)


def table_qualified_name(preparer, table):
    if table.schema:
        return f"{quote_name(preparer, table.schema)}.{quote_name(preparer, table.name)}"
    return quote_name(preparer, table.name)


def _make_dollar_tag(text):
    # prefer a short human-friendly tag, fall back to numbered variants, then uuid if necessary
    preferred = "dump"
    if f"${preferred}$" not in text:
        return preferred
    # try a few numeric variants which are still readable
    for i in range(1, 101):
        tag = f"{preferred}_{i}"
        if f"${tag}$" not in text:
            return tag
    # fallback to short uuid-based tag (very unlikely to be needed)
    for i in range(5):
        tag = f"{preferred}_{uuid.uuid4().hex[:8]}"
        if f"${tag}$" not in text:
            return tag
    return f"{preferred}_{uuid.uuid4().hex}"


def _dollar_quote(text):
    tag = _make_dollar_tag(text)
    return f"${tag}$" + text + f"${tag}$"


def dump_db(url, out_path, tables=None, collapse_percent=False, normalize_newlines='strip'):
    engine = create_engine(url, pool_pre_ping=True,
        connect_args={"options": "-c client_encoding=utf8"} if "postgres" in url else {}, )
    metadata = MetaData()
    metadata.reflect(bind=engine, only=tables)
    preparer = engine.dialect.identifier_preparer

    with engine.connect() as conn, open(out_path, "w", encoding="utf-8") as f:
        try:
            if engine.dialect.name == "postgresql":
                search_path = conn.execute(text("SHOW search_path")).scalar()
                f.write(f"-- search_path: {search_path}\n\n")
        except Exception:
            pass

        for table in metadata.sorted_tables:
            ddl = str(CreateTable(table).compile(dialect=engine.dialect))
            f.write(ddl.rstrip() + ";\n\n")

            # Build a stable list of columns and detect an 'id' column
            cols = list(table.columns)
            id_col = next((c for c in cols if c.name.lower() == "id"), None)

            # Select rows; if we have an id column, order by it to ensure deterministic export
            if id_col is not None:
                sel = select(table).order_by(id_col)
            else:
                sel = select(table)

            result = conn.execute(sel)
            # use mappings to access by column name
            rows = result.mappings().all()
            if not rows:
                continue

            # Prepare quoted column names and the corresponding Column objects to dump (exclude id)
            cols_to_dump = [c for c in cols if c is not id_col]
            col_names = [quote_name(preparer, c.name) for c in cols_to_dump]
            qualified = table_qualified_name(preparer, table)

            # detect json-like columns
            json_col_names = set()
            for c in cols_to_dump:
                try:
                    tname = c.type.__class__.__name__.lower()
                except Exception:
                    tname = str(c.type).lower()
                if "json" in tname:
                    json_col_names.add(c.name)

            for row in rows:
                vals = []
                for c in cols_to_dump:
                    # Access value by column name from the mapping
                    v = row.get(c.name)

                    if v is None:
                        vals.append("NULL")
                        continue

                    # decode memoryview/bytes
                    if isinstance(v, memoryview):
                        try:
                            v = v.tobytes()
                        except Exception:
                            v = bytes(v)
                    if isinstance(v, (bytes, bytearray)):
                        try:
                            v = v.decode('utf-8')
                        except Exception:
                            v = bytes(v).hex()

                    # booleans
                    if isinstance(v, bool):
                        if engine.dialect.name == 'postgresql':
                            vals.append('true' if v else 'false')
                        else:
                            vals.append('1' if v else '0')
                        continue

                    # numbers
                    try:
                        from decimal import Decimal
                        if isinstance(v, (int, float, Decimal)) and not isinstance(v, bool):
                            vals.append(str(v))
                            continue
                    except Exception:
                        pass

                    # dict/list -> json
                    if isinstance(v, (dict, list)):
                        sval = json.dumps(v, ensure_ascii=False)
                        # normalize percent/newlines inside JSON string representation
                        if isinstance(sval, str):
                            sval = re.sub(r"%{2,}", "%", sval)
                            if collapse_percent:
                                sval = re.sub(r"%+", "%", sval)
                            if normalize_newlines and normalize_newlines != 'none':
                                if normalize_newlines == 'strip':
                                    sval = re.sub(r"[\r\n]+", "", sval)
                                elif normalize_newlines == 'collapse':
                                    sval = re.sub(r"\s+", " ", sval).strip()
                                elif normalize_newlines == 'dot':
                                    sval = re.sub(r"[\r\n]+", "。", sval)
                                    sval = re.sub(r"。+", "。", sval).strip()

                        if engine.dialect.name == 'postgresql' and c.name in json_col_names:
                            dq = _dollar_quote(sval)
                            vals.append(f"{dq}::jsonb")
                        else:
                            escaped = sval.replace("'", "''")
                            vals.append(f"'{escaped}'")
                        continue

                    # strings: normalize percent and newlines before quoting
                    if isinstance(v, str):
                        v = re.sub(r"%{2,}", "%", v)
                        if collapse_percent:
                            v = re.sub(r"%+", "%", v)

                        if normalize_newlines and normalize_newlines != 'none':
                            if normalize_newlines == 'strip':
                                v = re.sub(r"[\r\n]+", "", v)
                            elif normalize_newlines == 'collapse':
                                v = re.sub(r"\s+", " ", v).strip()
                            elif normalize_newlines == 'dot':
                                v = re.sub(r"[\r\n]+", "。", v)
                                v = re.sub(r"。+", "。", v).strip()

                        # For Postgres use dollar-quoting to avoid any backslash or percent escaping
                        if engine.dialect.name == 'postgresql':
                            dq = _dollar_quote(v)
                            vals.append(dq)
                            continue
                        else:
                            escaped = v.replace("'", "''")
                            vals.append(f"'{escaped}'")
                            continue

                    # fallback: try literal for other types
                    try:
                        lit = literal(v)
                        compiled = lit.compile(dialect=engine.dialect, compile_kwargs={"literal_binds": True})
                        vals.append(str(compiled))
                        continue
                    except Exception:
                        pass

                    # final fallback
                    try:
                        sval = json.dumps(v, ensure_ascii=False)
                    except Exception:
                        sval = str(v)
                    escaped = sval.replace("'", "''")
                    vals.append(f"'{escaped}'")

                if col_names:
                    row_sql = f"INSERT INTO {qualified} ({', '.join(col_names)}) " \
                              f"VALUES ({', '.join(vals)});\n"
                    # final safety: collapse repeated % sequences to a single % to avoid doubled escaping
                    # do this idempotently so multiple runs won't keep changing the file
                    row_sql = re.sub(r"%{2,}", "%", row_sql)
                    f.write(row_sql)
            f.write("\n")
    print(f"dumped to {out_path}")
    # Final post-processing: collapse any repeated '%' sequences across the file to a single '%'.
    try:
        with open(out_path, 'r', encoding='utf-8') as rf:
            content = rf.read()
        new_content = re.sub(r"%{2,}", "%", content)
        if new_content != content:
            with open(out_path, 'w', encoding='utf-8') as wf:
                wf.write(new_content)
            print("Post-processed: collapsed repeated '%' sequences in output file.")
    except Exception:
        # don't fail the dump on post-processing errors
        pass


def parse_simple_args(argv):
    url = os.getenv("DATABASE_URL") or DEFAULT_URL
    out = DEFAULT_OUT
    tables = DEFAULT_TABLES
    collapse_percent = False
    normalize_newlines = 'strip'
    for a in argv:
        if a.startswith("--url="):
            url = a.split("=", 1)[1]
        elif a.startswith("--out="):
            out = a.split("=", 1)[1]
        elif a.startswith("--tables="):
            val = a.split("=", 1)[1]
            tables = val.split(",") if val else None
        elif a == "--collapse-percent":
            collapse_percent = True
        elif a.startswith("--normalize-newlines="):
            normalize_newlines = a.split("=", 1)[1]
    return url, out, tables, collapse_percent, normalize_newlines


if __name__ == "__main__":
    url, out, tables, collapse_percent, normalize_newlines = parse_simple_args(sys.argv[1:])
    if not url:
        raise SystemExit("No database URL provided. Set DATABASE_URL env or use --url=...")
    dump_db(url, out, tables, collapse_percent=collapse_percent, normalize_newlines=normalize_newlines)
