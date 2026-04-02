import platform

from datetime import datetime
from pathlib import Path

from textual import on
from textual.app import App, ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Button, DataTable, DirectoryTree, Header
from textual.widgets import Input, Label, RichLog, Tree


class FileTuilla(App):
    CSS_PATH = "filetuilla.tcss"

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
            Horizontal(
                local_tree, Tree("Remote", id="remote_file_tree"), id="tree_row"
            ),
            # File info data tables
            Horizontal(local_files_table, remote_files_table, id="file_tables"),
            # File info row (number of files/directories, total size)
            Horizontal(
                Label("local", id="local_file_info"),
                Label("remote", id="remote_file_info"),
                id="file_info_row",
            ),
            # Transfer info
            id="main_container",
        )

    def on_mount(self) -> None:
        self.title = "FileTuilla"
        self.update_local_file_info_table()

    @on(DirectoryTree.DirectorySelected, "#local_file_tree")
    def on_local_file_tree_selected(
        self, event: DirectoryTree.DirectorySelected
    ) -> None:
        """
        Update the local file info table with the contents of the local directory when a directory is selected.
        """
        selected_path = event.path
        self.local_site.value = str(selected_path)
        self.update_local_file_info_table()

    def update_local_file_info_table(self) -> None:
        """
        Update the local file info table with the contents of the currently selected directory.
        """
        local_path = Path(self.local_site.value)
        files = []
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
        local_files_table = self.query_one("#local_files_table", DataTable)
        local_files_table.clear()
        for file_info in files:
            local_files_table.add_row(*map(str, file_info))


if __name__ == "__main__":
    app = FileTuilla()
    app.run()
