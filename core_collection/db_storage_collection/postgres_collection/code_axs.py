"""PostgreSQL-backed collection support similar to :mod:`mongodb_collection`.

Usage examples ::

    axs byname postgres_collection , help

        # see this cookbook

    axs work_collection , attached_entry ---own_data='{"_parent_entries": [["^",
    "byname", "postgres_collection"]], "tags": ["collection"]}' , save
    foo_pg_collection
        # make a new PostgreSQL-backed collection

    axs byname foo_pg_collection , attached_entry ---own_data='{"_parent_entries":
    [["^", "byname", "postgres_entry"]], "name": "John", "age": 98}' , save
        # store an entry in it

    axs byname foo_pg_collection , all_byquery ''
        # list all entries in it (includes the collection)

    axs byname foo_pg_collection , all_byquery 'age<100'
        # list meaningful entries (excludes the collection)

Provides helper functions for connecting using a connection URL which can be
specified via the ``uri`` parameter or the entry field, mirroring the MongoDB
collection helpers.
"""

import json

def db_connect(uri=None, table_name=None, __entry__=None):
    from psycopg2 import connect

    uri = uri or __entry__.get("uri")
    table_name = table_name or __entry__.get("table_name")
    conn = connect(uri)
    cur = conn.cursor()
    cur.execute(
        f"CREATE TABLE IF NOT EXISTS {table_name} (id SERIAL PRIMARY KEY, data JSONB)"
    )
    conn.commit()
    return conn


def db_disconnect(pg_connection_obj):
    pg_connection_obj.close()


def generate_contained_entries(pg_connection_obj=None, postgres_parent_entry=None, table_name=None, __entry__=None):
    conn = pg_connection_obj or __entry__.get("pg_connection_obj")
    table_name = table_name or __entry__.get("table_name")
    postgres_parent_entry = postgres_parent_entry or __entry__.get("postgres_parent_entry")
    contained_entries = {}
    cur = conn.cursor()
    cur.execute(f"SELECT id, data FROM {table_name}")
    for row_id, json_data in cur.fetchall():
        document_data = json.loads(json_data)
        print("Postgres loading row:", row_id, document_data)
        entry_parents = document_data.pop("_parent_entries", [])
        entry_parents.append(__entry__.pickle_struct(postgres_parent_entry))
        document_data["_parent_entries"] = entry_parents
        found_entry = __entry__.call(
            "attached_entry",
            [],
            {"entry_path": f"postgres_{row_id}", "own_data": document_data},
        )
        found_entry.call("db_id", [row_id])
        contained_entries[row_id] = found_entry
    return contained_entries
