"""SQLite-backed collection support similar to :mod:`mongodb_collection`.

Usage examples ::

    axs byname sqlite_collection , help

        # see this cookbook

    axs work_collection , attached_entry ---own_data='{"_parent_entries": [["^",
    "byname", "sqlite_collection"]], "tags": ["collection"]}' , save foo_sqlite
        # make a new SQLite-backed collection

    axs byname foo_sqlite , attached_entry ---own_data='{"_parent_entries": [["^",
    "byname", "sqlite_entry"]], "name": "John", "age": 98}' , save
        # store an entry in it

    axs byname foo_sqlite , all_byquery ''
        # list all entries in it (includes the collection)

    axs byname foo_sqlite , all_byquery 'age<100'
        # list meaningful entries (excludes the collection)
"""

import json
import sqlite3


def db_connect(db_path=None, table_name=None, __entry__=None):
    db_path = db_path or __entry__.get("db_path")
    table_name = table_name or __entry__.get("table_name")
    conn = sqlite3.connect(db_path)
    conn.execute(
        f"CREATE TABLE IF NOT EXISTS {table_name} (id INTEGER PRIMARY KEY AUTOINCREMENT, data TEXT)"
    )
    return conn


def db_disconnect(sqlite_connection_obj):
    sqlite_connection_obj.close()


def generate_contained_entries(sqlite_connection_obj=None, sqlite_parent_entry=None, table_name=None, __entry__=None):
    conn = sqlite_connection_obj or __entry__.get("sqlite_connection_obj")
    table_name = table_name or __entry__.get("table_name")
    sqlite_parent_entry = sqlite_parent_entry or __entry__.get("sqlite_parent_entry")
    contained_entries = {}
    cur = conn.cursor()
    for row_id, json_data in cur.execute(f"SELECT id, data FROM {table_name}"):
        document_data = json.loads(json_data)
        print("SQLite loading row:", row_id, document_data)
        entry_parents = document_data.pop("_parent_entries", [])
        entry_parents.append(__entry__.pickle_struct(sqlite_parent_entry))
        document_data["_parent_entries"] = entry_parents
        found_entry = __entry__.call(
            "attached_entry",
            [],
            {"entry_path": f"sqlite_{row_id}", "own_data": document_data},
        )
        found_entry.call("db_id", [row_id])
        contained_entries[row_id] = found_entry
    return contained_entries
