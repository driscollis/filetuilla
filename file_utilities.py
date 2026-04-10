import os
import typing

from pathlib import Path

from rich.text import Text
from textual.widgets import DirectoryTree, RichLog

if typing.TYPE_CHECKING:
    from filetuilla import FileTuilla


def _delete_local_file(app: "FileTuilla", should_delete: bool) -> None:
    """
    Delete the local file
    """
    log = app.query_one("#ftp_log", RichLog)
    if should_delete and app.local_file_selected.exists():
        try:
            os.remove(app.local_file_selected)
            log.write(
                Text(
                    f"Deleted {app.local_file_selected} successfully!",
                    style="green4",
                )
            )
            local_tree = app.query_one("#local_file_tree", DirectoryTree)
            local_tree.reload()
            app.update_local_file_info_table()
        except FileNotFoundError:
            log.write(
                Text(
                    f"File not found: {app.local_file_selected}",
                    style="bright_red",
                )
            )
        except OSError as e:
            log.write(
                Text(
                    f"Unable to delete file {app.local_file_selected}: {e}",
                    style="bright_red",
                )
            )


def _rename_local_file(app: "FileTuilla", new_name: Path | bool = False) -> None:
    """
    Rename the currently selected local file (if any)
    """
    log = app.query_one("#ftp_log", RichLog)
    if isinstance(new_name, Path) and app.local_file_selected.exists():
        old_path = app.local_file_selected
        new_path = app.local_file_selected.parent / new_name
        try:
            app.local_file_selected.rename(new_path)
            log.write(
                Text(
                    f"Renamed {old_path} to {new_path} successfully!",
                    style="green4",
                )
            )
            local_tree = app.query_one("#local_file_tree", DirectoryTree)
            local_tree.reload()
            app.update_local_file_info_table()
        except FileNotFoundError:
            log.write(
                Text(
                    f"File not found: {app.local_file_selected}",
                    style="bright_red",
                )
            )
        except OSError as e:
            log.write(
                Text(
                    f"Unable to rename file {app.local_file_selected}: {e}",
                    style="bright_red",
                )
            )


def create_local_folder(app: "FileTuilla", folder_name: str | bool = False) -> None:
    """
    Create a new folder on the local machine with the given name
    """
    log = app.query_one("#ftp_log", RichLog)
    if isinstance(folder_name, Path):
        new_folder_path = Path(app.local_site.value) / folder_name
        try:
            new_folder_path.mkdir()
            log.write(
                Text(
                    f"Created new folder {new_folder_path} successfully!",
                    style="green4",
                )
            )
            local_tree = app.query_one("#local_file_tree", DirectoryTree)
            local_tree.reload()
            app.update_local_file_info_table()
        except FileExistsError:
            log.write(
                Text(
                    f"Folder already exists: {new_folder_path}",
                    style="bright_red",
                )
            )
        except OSError as e:
            log.write(
                Text(
                    f"Unable to create folder {new_folder_path}: {e}",
                    style="bright_red",
                )
            )
