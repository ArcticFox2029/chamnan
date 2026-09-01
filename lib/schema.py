"""Extract a data model from whatever the repo uses to define one — DDL, ORM models, migrations.

Same argument as the code map, applied to tables. An agent asked "where are refunds stored" will
otherwise either guess or ask for a schema dump, and a dump of a real schema is thousands of tokens
of column definitions to answer a question about one table name.

Two tiers, and the second is deliberately NOT a vector store:

  small schema  -> table names and one-line summaries go into the session, all of them
  large schema  -> only the names go in; columns stay in the map's detail section, grepped

Vector search over schema metadata is a real technique and it would work here, but it needs an
embedding model, which means a dependency or a network call in a plugin that currently has neither.
Grep reaches the same place: the agent knows the table exists from the injected name list, then
greps one heading for its columns. The saving comes from not injecting all the columns, and both
approaches deliver that.

Nothing here connects to a database. It reads the files that describe one.
"""
import pathlib
import re
from pathlib import Path

import redact
import tree

# Above this many tables, only names are injected and columns are left to be grepped.
DETAIL_LIMIT = 40
MAX_COLUMNS_SHOWN = 25

# The trailing "(" is what keeps a partition out of the index, and that is worth stating rather
# than leaving to luck: `CREATE TABLE readings_eu_west PARTITION OF readings ...` has no column
# list, so it never matches. That is the outcome we want -- eight regional partitions of one table
# are eight rows of noise and the parent already says everything -- but it was accidental, and an
# innocent-looking relaxation of this pattern would silently undo it. SQL_PARTITION exists to
# count them so the parent can say it is partitioned.
#
# The same "(" rule also skips `CREATE TABLE x LIKE y`, which is how MySQL fakes a materialized
# view: a staging copy is built inside a stored procedure, filled, and renamed over the real table.
# Those __new tables are not schema anybody needs to know about, and the table they shadow is
# indexed under its own name.
SQL_TABLE = re.compile(
    r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[`\"\[]?(?:\w+[`\"\]]?\.[`\"\[]?)?(\w+)[`\"\]]?\s*\(",
    re.I)
SQL_PARTITION = re.compile(
    r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[`\"\[]?(?:\w+[`\"\]]?\.[`\"\[]?)?\w+[`\"\]]?"
    r"\s+PARTITION\s+OF\s+[`\"\[]?(?:\w+[`\"\]]?\.[`\"\[]?)?(\w+)", re.I)
PRISMA_MODEL = re.compile(r"^model\s+(\w+)\s*\{", re.M)
# `models.Model` must be among the bases, not the only one. Requiring it alone indexed
# TimestampedMixin -- which is abstract and is not a table -- and missed Order, which is. An
# invented table is the worse half of that: a reader can go looking for it.
DJANGO_MODEL = re.compile(
    r"^class\s+(\w+)\s*\(([^)]*\b(?:models\.)?Model\b[^)]*)\)\s*:", re.M)
# An abstract base declares no table of its own, and Django says so in its own Meta.
DJANGO_ABSTRACT = re.compile(r"abstract\s*=\s*True")
SQLALCHEMY_TABLE = re.compile(r"__tablename__\s*=\s*[\"'](\w+)[\"']")
# SQLAlchemy 2.0's shared-base idiom computes __tablename__ in a declared_attr instead of writing
# it. There is no literal to read, so the table name genuinely is not in this file -- but the
# class IS a table, and saying nothing said the file had no tables at all.
SQLALCHEMY_DECLARED = re.compile(
    r"@declared_attr[\s\S]{0,200}?def\s+__tablename__")
SQLALCHEMY_CLASS = re.compile(r"^class\s+(\w+)\s*\([^)]*\)\s*:", re.M)
RAILS_TABLE = re.compile(r"create_table\s+[:\"'](\w+)", re.I)
TYPEORM_ENTITY = re.compile(r"@Entity\([^)]*\)\s*(?:export\s+)?class\s+(\w+)", re.S)
# `@Entity({ name: "orders" })` -- the decorator names the real table, and the class name is not
# it. Read first, exactly as ROOM_JPA_TABLE is read before ROOM_JPA_CLASS below, and for the same
# reason: `Order` is not what the table is called.
TYPEORM_NAMED = re.compile(
    r"@Entity\s*\(\s*(?:[\"']([\w.]+)[\"']|\{[^{}]*?name\s*:\s*[\"']([\w.]+)[\"'])", re.S)
# A view is a queryable object, and an analytics materialized view is often the only place a
# derived figure is defined. Neither was matched at all, so "where does lane performance come
# from" had no answer in the index even though the repo declares it.
SQL_VIEW = re.compile(
    r"CREATE\s+(?:OR\s+REPLACE\s+)?(?:MATERIALIZED\s+)?VIEW\s+(?:IF\s+NOT\s+EXISTS\s+)?"
    r"[`\"\[]?(?:\w+[`\"\]]?\.[`\"\[]?)?(\w+)[`\"\]]?", re.I)
# Room (Android) and JPA (Java) both declare the real table name in the annotation, which beats
# the class name -- ShipmentEntity is not what the table is called. The TypeORM pattern above
# missed both: its [^)] stops at the first ")" and Room's annotation contains Index(...), and
# Kotlin writes "data class" rather than "class".
ROOM_JPA_TABLE = re.compile(
    r"@(?:Entity|Table)\s*\([^{]*?(?:tableName|name)\s*=\s*[\"']([\w.]+)[\"']", re.S)
# Bare @Entity with no name: the table is the class, which is what JPA defaults to.
# Only when nothing between @Entity and the class declares a name -- otherwise the table would be
# listed twice, once as `fleet_vehicles` and once as `Vehicle`, and one of those is not a table.
ROOM_JPA_CLASS = re.compile(
    r"@Entity\b(?:(?!tableName|(?<![\w])name\s*=)[^\n])*\n"
    r"(?:[ \t]*@(?:(?!tableName|(?<![\w])name\s*=)[^\n])*\n)*"
    r"[ \t]*(?:public\s+|open\s+|data\s+|final\s+|abstract\s+)*class\s+(\w+)")

COMMENT_ABOVE = re.compile(r"(?:^|\n)((?:[ \t]*(?://|--|#)[^\n]*\n)+)[ \t]*$")
SQL_COLUMN = re.compile(r"^\s*[`\"\[]?(\w+)[`\"\]]?\s+"
                        r"(varchar|char|text|int|integer|bigint|smallint|decimal|numeric|float|"
                        r"double|real|bool|boolean|date|datetime|timestamp|time|json|jsonb|uuid|"
                        r"blob|bytea|serial|bigserial|"
                        # Dialect types, added because a column of one vanished from the list with
                        # nothing saying the list was short -- which reads as "this table has no
                        # status column", not as "this tool does not know ENUM".
                        r"enum|tinyint|mediumint|nvarchar|nchar|ntext|varchar2|number|clob|"
                        r"money|bit|year|set|inet|cidr|macaddr|xml|citext|interval|"
                        r"timestamptz|datetime2|smalldatetime|binary|varbinary|image|geometry)",
                        re.I | re.M)

SCHEMA_HINTS = ("migration", "migrations", "schema", "models", "db", "database", "sql",
                # Where JPA, Room, Hibernate and Doctrine entities actually live. The corpus only
                # found its Room entities because their path happened to contain db/ and entity/;
                # the far more common src/main/java/.../domain/Vehicle.java was invisible.
                "entity", "entities", "domain", "model", "persistence", "repository", "dao",
                "store", "storage")


# 🐛 A path's components are tested RELATIVE to the repository root, never absolute. Testing the
# absolute path means one directory ABOVE the checkout named `vendor`, `node_modules`, `build`,
# `dist` or `.venv` skips every file in the repository -- and each of these renderers returns "" on
# an empty result, so whole sections simply vanish with no hedge. `assets.scan` already tested
# `rel.parts`, which is what made the asymmetry findable. Two harms beyond the missing sections:
# `mapper.scan` is unaffected, so the index and the catalogues then disagree about the same
# repository; and the unignored-`.env` warning goes silent, which is the false-calm direction.
def _rel_parts(path, root):
    """`path`'s components below `root`, or its own components when it is not below root."""
    try:
        return pathlib.Path(path).relative_to(root).parts
    except (ValueError, TypeError):
        return pathlib.Path(path).parts


def _summary_above(text, pos):
    """A comment block immediately above a definition, used as its one-line summary."""
    m = COMMENT_ABOVE.search(text[:pos])
    if not m:
        return ""
    lines = []
    for line in m.group(1).strip().splitlines():
        cleaned = re.sub(r"^[ \t]*(?://|--|#)+\s?", "", line).strip()
        if cleaned:
            lines.append(cleaned)
    return " ".join(lines)[:110]


def _looks_relevant(path):
    """Whether a file is worth opening for schema definitions, judged by where it sits.

    Deliberately a path test and not a content test. Reading every source file in the repo to see
    whether it happens to contain @Entity is the cost this whole plugin exists to avoid, so a
    schema definition in a directory named after none of the conventions below is not found. That
    is a real limitation and the honest trade: the hint list covers where these files actually
    live in Django, Rails, JPA, Room, Hibernate, Prisma and Doctrine projects, and a table defined
    outside all of them stays invisible until someone adds a hint or moves the file.
    """
    parts = [p.lower() for p in path.parts]
    return path.suffix.lower() in (".sql", ".prisma") or any(h in parts for h in SCHEMA_HINTS) \
        or path.name.lower() in ("models.py", "schema.rb", "schema.prisma")


def scan(root, files):
    """files: the list already produced by mapper.scan, reused so nothing is read twice."""
    tables = {}
    partitions = {}

    def add(name, source, summary="", columns=None):
        key = name.lower()
        if key in tables and not summary:
            return
        tables[key] = {"name": name, "source": source,
                       "summary": summary or tables.get(key, {}).get("summary", ""),
                       "columns": columns or tables.get(key, {}).get("columns", [])}

    # Schema files are not in mapper's extension table — it indexes code, and a .sql or .prisma
    # file is a declaration of shape, not code — so they are read directly here. Prisma was missed
    # entirely until a multi-service fixture showed a service whose whole store was invisible: its
    # models are in schema.prisma and nothing else in the repo mentions them.
    for path in tree.by_suffix(root, ".sql", ".prisma"):
        # .venv added 2026-08-28: it was the only skip list here missing it, which is the reason a
        # shared pruned walk could not include virtualenvs. A .sql inside one is a dependency's
        # schema, never this repository's.
        if any(p in (".git", "node_modules", "vendor", "__pycache__", ".venv")
               for p in _rel_parts(path, root)) \
                or redact.is_blocked(path):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        rel = str(path.relative_to(root))
        for m in PRISMA_MODEL.finditer(text):
            add(m.group(1), rel, _summary_above(text, m.start()))
        for m in SQL_TABLE.finditer(text):
            body_end = text.find(";", m.end())
            body = text[m.end(): body_end if body_end > 0 else m.end() + 2000]
            cols = [c.group(1) for c in SQL_COLUMN.finditer(body)]
            add(m.group(1), rel, _summary_above(text, m.start()), cols[:MAX_COLUMNS_SHOWN])
        for m in SQL_VIEW.finditer(text):
            add(m.group(1), rel, _summary_above(text, m.start()))
        for m in SQL_PARTITION.finditer(text):
            partitions[m.group(1).lower()] = partitions.get(m.group(1).lower(), 0) + 1

    for f in files:
        path = root / f["path"]
        if not _looks_relevant(path):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for pattern in (PRISMA_MODEL, SQLALCHEMY_TABLE, RAILS_TABLE,
                        ROOM_JPA_TABLE, ROOM_JPA_CLASS):
            for m in pattern.finditer(text):
                add(m.group(1), f["path"], _summary_above(text, m.start()))

        # Django, separately: a class is a table only if `models.Model` is among its bases AND the
        # class is not abstract. Abstract mixins are a table's worth of fields with no table.
        for m in DJANGO_MODEL.finditer(text):
            body = text[m.end():m.end() + 800]
            nxt = DJANGO_MODEL.search(text, m.end())
            if nxt:
                body = text[m.end():min(nxt.start(), m.end() + 800)]
            if DJANGO_ABSTRACT.search(body):
                continue
            add(m.group(1), f["path"], _summary_above(text, m.start()))

        # TypeORM, separately: the decorator's own name beats the class name where it is given,
        # and the class name is only the fallback for a bare @Entity().
        named = set()
        for m in TYPEORM_NAMED.finditer(text):
            named.add(m.start())
            add(m.group(1) or m.group(2), f["path"], _summary_above(text, m.start()))
        for m in TYPEORM_ENTITY.finditer(text):
            if m.start() not in named:
                add(m.group(1), f["path"], _summary_above(text, m.start()))

        # A computed __tablename__ names no table in this file, but the classes are still tables.
        # Recorded under their class names, which is the only name present, rather than dropped.
        if SQLALCHEMY_DECLARED.search(text) and not SQLALCHEMY_TABLE.search(text):
            for m in SQLALCHEMY_CLASS.finditer(text):
                add(m.group(1), f["path"], _summary_above(text, m.start()))

    for name, count in partitions.items():
        if name in tables:
            note = f"partitioned, {count} partitions"
            existing = tables[name]["summary"]
            tables[name]["summary"] = f"{existing} ({note})" if existing else note
    return sorted(tables.values(), key=lambda t: t["name"].lower())


def render(tables):
    """The section injected with the index. Empty string when the repo has no data model — a repo
    of plain scripts should see no trace of this feature at all."""
    if not tables:
        return ""
    out = [f"## Data model", "",
           f"{len(tables)} table(s)/model(s) found in this repo's schema and migration files."]
    if len(tables) > DETAIL_LIMIT:
        out.append(f"Names only — this schema is large. Grep `### <table>` below for one table's"
                   f" columns rather than reading them all.")
        out.append("")
        out.append(", ".join(f"`{t['name']}`" for t in tables))
    else:
        out.append("")
        for t in tables:
            desc = f" — {t['summary']}" if t["summary"] else ""
            out.append(f"- **`{t['name']}`**{desc}  _({t['source']})_")
    out.append("")
    return "\n".join(out)


def render_detail(tables):
    """Column lists, placed in the map's grep-only half."""
    if not tables:
        return ""
    out = ["## Data model detail", ""]
    for t in tables:
        out.append(f"### {t['name']}")
        if t["summary"]:
            out.append(t["summary"])
        if t["columns"]:
            out.append(f"columns: {', '.join(t['columns'])}")
        out.append(f"defined in `{t['source']}`")
        out.append("")
    return "\n".join(out)
