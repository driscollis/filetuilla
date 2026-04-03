import platform
import stat

from datetime import datetime
from pathlib import Path

from textual import on
from textual.app import App, ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Button, DataTable, DirectoryTree, Header
from textual.widgets import Input, Label, RichLog, Tree


class FileTuilla(App):
    CSS_PATH = "filetuilla.tcss"

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.ftp_client = None

    def compose(self) -> ComposeResult:
        columns = ("Filename", "Filesize", "Filetype", "Last modified")
        host = Input(id="host")
        host.border_title = "Host"
        username = Input(id="username")
        username.border_title = "Username"
        password = Input(id="password")
        password.border_title = "Password"
        port = Input(id="port")
        port.border_title = "Port"

        if "Windows" in platform.platform():
            self.local_site = Input("C:\\", id="local_site")
        else:
            self.local_site = Input("/", id="local_site")
        self.local_site.border_title = "Local site"
        self.remote_site = Input(id="remote_site")
        self.remote_site.border_title = "Remote site"

        local_tree = DirectoryTree("/", id="local_file_tree")

        local_files_table = DataTable(id="local_files_table")
        local_files_table.add_columns(*columns)
        remote_files_table = DataTable(id="remote_files_table")
        remote_files_table.add_columns(*columns)

        yield Header()
        yield VerticalScroll(
            Horizontal(
                host,
                username,
                password,
                port,
                Button("Connect", id="connect", variant="primary"),
                id="connection_form",
            ),
            RichLog(id="ftp_log"),
            Horizontal(self.local_site, self.remote_site, id="site_inputs"),
            Horizontal(local_tree, Tree("", id="remote_file_tree"), id="tree_row"),
            # File info data tables
            Horizontal(local_files_table, remote_files_table, id="file_tables"),
            # File info row (number of files/directories, total size)
            Horizontal(
                Label("local", id="local_file_info"),
                Label("remote", id="remote_file_info"),
                id="file_info_row",
            ),
            # Buttons to control file actions locally and remotely
            Horizontal(
                Horizontal(
                    Button("Upload", id="upload", variant="success"),
                    Button("Delete", id="local_delete", variant="error"),
                    Button("Rename", id="local_rename", variant="primary"),
                    Button("New Folder", id="local_new_folder", variant="primary"),
                    id="local_file_actions",
                ),
                Horizontal(
                    Button("Download", id="download", variant="primary"),
                    Button("Delete", id="remote_delete", variant="error"),
                    Button("Rename", id="remote_rename", variant="primary"),
                    Button("New Folder", id="remote_new_folder", variant="primary"),
                    Button("Up Dir", id="up_dir", variant="success"),
                    id="remote_file_actions",
                ),
                id="file_action_controls_row",
            ),
            # Transfer info
            id="main_container",
        )

    def on_mount(self) -> None:
        self.title = "FileTuilla"
        self.update_local_file_info_table()
        self.query_one("#local_file_actions").border_title = "Local"
        self.query_one("#remote_file_actions").border_title = "Remote"

    @on(DirectoryTree.DirectorySelected, "#local_file_tree")
    def on_local_file_tree_selected(
        self, event: DirectoryTree.DirectorySelected
    ) -> None:
        """
        Update the local file info table with the contents of the local directory when a directory is selected.
        """
        selected_path = event.path
        if str(selected_path) != "":
            self.local_site.value = str(selected_path)
            self.update_local_file_info_table()

    def update_local_file_info_table(self) -> None:
        """
        Update the local file info table with the contents of the currently selected directory.
        """
        local_path = Path(self.local_site.value)
        files = []
        dirs = []
        total_size = 0
        if local_path.exists():
            for path in local_path.iterdir():
                if path.is_file():
                    modified_time = datetime.fromtimestamp(path.stat().st_mtime)
                    files.append(
                        (
                            path.name,
                            path.stat().st_size,
                            path.suffix,
                            f"{modified_time:%Y-%m-%d %H:%M:%S}",
                        )
                    )
                    total_size += path.stat().st_size
                elif path.is_dir():
                    dirs.append(path.name)
        local_files_table = self.query_one("#local_files_table", DataTable)
        local_files_table.clear()
        for file_info in files:
            local_files_table.add_row(*map(str, file_info))

        # Update local file info label
        self.update_local_file_info_label(files, dirs, total_size)

    def update_local_file_info_label(
        self, files: list, dirs: list, total_size: int
    ) -> None:
        """
        Update the local file info label with the number of files/directories
        and total size of the currently selected directory.
        """
        num_files = len(files)
        num_dirs = len(dirs)
        local_file_info_label = self.query_one("#local_file_info", Label)
        local_file_info_label.update(
            f"{num_files} files and {num_dirs} directories, Total size: {total_size} B"
        )

    @on(DirectoryTree.DirectorySelected, "#remote_file_tree")
    def on_remote_file_tree_selected(
        self, event: DirectoryTree.DirectorySelected
    ) -> None:
        """
        Update the remote file info table with the contents of the remote directory when a directory is selected.
        """
        selected_path = event.path
        self.remote_site.value = str(selected_path)
        self.update_remote_file_info_table()

    def update_remote_file_info_table(self) -> None:
        """
        Update the remote file info table with the contents of the currently selected directory.
        """
        if self.ftp_client:
            # TODO - need to test to see if this works for FTP too
            # SFTP Implementation
            paths = self.ftp_client.listdir(self.remote_site.value)
            files = []
            dirs = []
            total_size = 0
            for path in paths:
                full_remote_path = f"{self.remote_site.value}/{path}"
                attrs = self.ftp_client.stat(full_remote_path)
                mode = attrs.st_mode
                if stat.S_ISREG(mode):
                    # path is a file
                    modified_time = datetime.fromtimestamp(attrs.st_mtime)
                    files.append(
                        (
                            path,
                            attrs.st_size,
                            Path(path).suffix,
                            f"{modified_time:%Y-%m-%d %H:%M:%S}",
                        )
                    )
                    total_size += attrs.st_size
                elif stat.S_ISDIR(mode):
                    dirs.append(path)
            remote_files_table = self.query_one("#remote_files_table", DataTable)
            remote_files_table.clear()
            for file_info in files:
                remote_files_table.add_row(*map(str, file_info))

            # Update local file info label
            self.update_remote_file_info_label(files, dirs, total_size)

    def update_remote_file_info_label(
        self, files: list, dirs: list, total_size: int
    ) -> None:
        """
        Update the remote file info label with the number of files/directories
        """
        num_files = len(files)
        num_dirs = len(dirs)
        remote_file_info_label = self.query_one("#remote_file_info", Label)
        remote_file_info_label.update(
            f"{num_files} files and {num_dirs} directories, Total size: {total_size} B"
        )


if __name__ == "__main__":
    app = FileTuilla()
    app.run()
