"""Private desktop stdin actions. HTTP callers cannot authorize arbitrary roots."""

from app.db.database import connect, init_schema
from app.services.folder_scanner import folder_lock
from app.services.folders import parent_handle, register_root, root_record
from app.services.workspace_access import request_access


def dispatch(action, values):
    with request_access(), folder_lock:
        connection = connect()
        try:
            init_schema(connection)
            if action == "register_root":
                identifier = register_root(
                    connection, values["path"], values["kind"], reconnect_id=values.get("root_id")
                )
                from app.config import data_directory
                from app.services.folder_backup import reconnect_assets

                reconnect_assets(connection, identifier, data_directory())
                return identifier
            if action == "reveal_root":
                root = root_record(connection, values["root_id"])
                from app.services.folders import root_handle

                with root_handle(root):
                    return root["path"]
            if action == "reveal_source":
                row = connection.execute(
                    "SELECT * FROM sources WHERE file_id=?", (values["source_id"],)
                ).fetchone()
                if row is None:
                    raise ValueError("This source is not registered.")
                root = root_record(connection, row["root_id"])
                with parent_handle(root, row["relative_path"]) as (fd, name):
                    import os
                    import stat

                    info = os.stat(name, dir_fd=fd, follow_symlinks=False)
                    if not stat.S_ISREG(info.st_mode):
                        raise ValueError("This original cannot be revealed safely.")
                return root["path"] + "/" + row["relative_path"]
            raise ValueError("Unknown native folder action.")
        finally:
            connection.close()
