import json


def db_id(db_id=None, __entry__=None):
    """Getter/Setter for PostgreSQL row id"""
    if db_id is not None:
        __entry__.stored_db_id = db_id
    return getattr(__entry__, "stored_db_id", None)


def save(__entry__):
    postgres_collection = __entry__.get_container()
    conn = postgres_collection.get("pg_connection_obj")
    table_name = postgres_collection.get("table_name")
    postgres_parent_entry = postgres_collection.get("postgres_parent_entry")

    db_id_val = __entry__.call("db_id")
    sanitized_data = __entry__.pickle_struct(__entry__.own_data())
    allowed_parents = __entry__.pickle_struct([
        p for p in __entry__.parents_loaded() if p != postgres_parent_entry
    ])

    if allowed_parents == []:
        sanitized_data.pop("_parent_entries", None)
    else:
        sanitized_data["_parent_entries"] = allowed_parents

    json_data = json.dumps(sanitized_data)
    cur = conn.cursor()

    if db_id_val:
        cur.execute(
            f"UPDATE {table_name} SET data=%s WHERE id=%s",
            (json_data, db_id_val),
        )
    else:
        cur.execute(
            f"INSERT INTO {table_name} (data) VALUES (%s) RETURNING id",
            (json_data,),
        )
        db_id_val = cur.fetchone()[0]
        __entry__.call("db_id", db_id_val)
    conn.commit()
    return __entry__


def remove(__entry__):
    postgres_collection = __entry__.get_container()
    conn = postgres_collection.get("pg_connection_obj")
    table_name = postgres_collection.get("table_name")
    db_id_val = __entry__.call("db_id")
    cur = conn.cursor()
    cur.execute(f"DELETE FROM {table_name} WHERE id=%s", (db_id_val,))
    conn.commit()
    __entry__.call("db_id", None)
    return __entry__
