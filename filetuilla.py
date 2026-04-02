from pathlib import Path

from textual import on
from textual.app import App, ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Button, DirectoryTree, Header, Input
from textual.widgets import Label, RichLog, Tree


class FileTuilla(App):
    CSS_PATH = "filetuilla.tcss"

    def compose(self) -> ComposeResult:
        host = Input(id="host")
        host.border_title = "Host"
        username = Input(id="username")
        username.border_title = "Username"
        password = Input(id="password")
        password.border_title = "Password"
        port = Input(id="port")
        port.border_title = "Port"
        local_site = Input(id="local_site")
        local_site.border_title = "Local site"
        remote_site = Input(id="remote_site")
        remote_site.border_title = "Remote site"
        local_tree = DirectoryTree("/", id="local_file_tree")

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
            Horizontal(
                local_site,
                remote_site,
                id="site_inputs"
            ),
            Horizontal(
                local_tree,
                Tree("Remote", id="remote_file_tree"),
                id="tree_row"
            ),
            # File info data tables

            # File info row (number of files/directories, total size)
            Horizontal(
                Label("local", id="local_file_info"),
                Label("remote", id="remote_file_info"),
                id="file_info_row",
            ),
            # Transfer info

            id="main_container"
        )

    def on_mount(self) -> None:
        self.title = "FileTuilla"

if __name__ == "__main__":
    app = FileTuilla()
    app.run()
