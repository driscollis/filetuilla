import paramiko
import platform
import stat

from datetime import datetime
from pathlib import Path

from textual import on, work
from textual.app import App, ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Button, DataTable, DirectoryTree, Header
from textual.widgets import Input, Label, RichLog
from textual.worker import get_current_worker

from file_utilities import _delete_local_file, _rename_local_file, create_local_folder
from file_utilities import log
from screens.new_folder_screen import NewFolderScreen
from screens.rename_screen import RenameScreen
from screens.warning_screen import WarningScreen
from sftp_directory import SFTPDirectoryTree


class FileTuilla(App):
    CSS_PATH = "filetuilla.tcss"

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.ftp_client: paramiko.sftp_client.SFTPClient | None = None
        self.local_file_selected = Path("BAD_PATH")
        self.remote_file_selected: str | None = None

    def compose(self) -> ComposeResult:
        columns = ("Filename", "Filesize", "Filetype", "Last modified")
        host = Input(id="host")
        host.border_title = "Host"
        username = Input(id="username")
        username.border_title = "Username"
        password = Input(id="password", password=True)
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

        local_files_table = DataTable(id="local_files_table", cursor_type="row")
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
                local_tree, SFTPDirectoryTree("/", id="remote_file_tree"), id="tree_row"
            ),
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
                    Button("Download", id="download", variant="success"),
                    Button("Delete", id="remote_delete", variant="error"),
                    Button("Rename", id="remote_rename", variant="primary"),
                    Button("New Folder", id="remote_new_folder", variant="primary"),
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

    @on(Button.Pressed, "#connect")
    async def on_connect(self, event: Button.Pressed) -> None:
        """
        Event handler for when the connect button is pressed.

        Connects to the FTP/SFTP server using the provided credentials.
        """
        host = self.query_one("#host", Input).value
        port_number = self.query_one("#port", Input).value
        port = int(port_number) if port_number else 22
        username = self.query_one("#username", Input).value
        password = self.query_one("#password", Input).value

        if not host:
            await self.push_screen(WarningScreen("Host is required", cancel=False))
            return
        if not username:
            await self.push_screen(WarningScreen("Username is required", cancel=False))
            return

        await self._connect_ftp(host, port, username, password)

    @work(thread=True, group="sftp_connect")
    def _do_sftp_connect(
        self, host: str, port: int, username: str, password: str
    ) -> paramiko.sftp_client.SFTPClient:
        """Run blocking paramiko connection in a background thread."""
        ssh_client = paramiko.SSHClient()
        ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh_client.connect(host, port, username, password)
        return ssh_client.open_sftp()

    async def _connect_ftp(
        self, host: str, port: int, username: str, password: str
    ) -> None:
        """
        Make connection to FTP/SFTP server.
        """
        try:
            # Run blocking connection in a background thread
            self.ftp_client = await self._do_sftp_connect(
                host, port, username, password
            ).wait()
        except Exception as e:
            await self.push_screen(
                WarningScreen(f"Connection failed: {e}", cancel=False)
            )
            return

        # Set the SFTP client on the remote file tree and reload
        remote_tree = self.query_one("#remote_file_tree", SFTPDirectoryTree)
        remote_tree.set_sftp_client(self.ftp_client)
        await remote_tree.reload()

        self.update_remote_file_info_table()

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

    @on(SFTPDirectoryTree.DirectorySelected, "#remote_file_tree")
    def on_remote_file_tree_selected(
        self, event: SFTPDirectoryTree.DirectorySelected
    ) -> None:
        """
        Update the remote file info table with the contents of the remote directory when a directory is selected.
        """
        selected_path = event.path
        self.remote_site.value = selected_path
        self._load_remote_file_info()

    def update_remote_directory_tree(self, dirs: list[str]) -> None:
        """
        Update the remote directory tree with the contents of the currently selected directory.
        """
        if self.remote_site.value:
            remote_tree = self.query_one("#remote_file_tree", SFTPDirectoryTree)
            remote_tree.set_root_path(self.remote_site.value)

    @work(thread=True, exclusive=True, group="load_remote_file_info")
    def _load_remote_file_info(self) -> None:
        """Load remote file info in a background thread."""
        worker = get_current_worker()
        if not self.ftp_client or self.remote_site.value == "":
            return

        remote_path = self.remote_site.value
        remote_tree = self.query_one("#remote_file_tree", SFTPDirectoryTree)
        sftp_lock = remote_tree.get_sftp_lock()

        try:
            with sftp_lock:
                paths = self.ftp_client.listdir(remote_path)
                files = []
                dirs = []
                total_size = 0
                for path in paths:
                    full_remote_path = f"{remote_path}/{path}"
                    attrs = self.ftp_client.stat(full_remote_path)
                    mode = attrs.st_mode
                    if stat.S_ISREG(mode):
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

            # Schedule UI updates on the main thread
            if not worker.is_cancelled:
                self.call_from_thread(
                    self._update_remote_file_table_ui, files, dirs, total_size
                )
        except Exception as e:
            if not worker.is_cancelled:
                self.call_from_thread(
                    self.notify, f"Error loading remote files: {e}", severity="error"
                )

    def _update_remote_file_table_ui(
        self, files: list, dirs: list, total_size: int
    ) -> None:
        """Update the remote file table UI (must be called from main thread)."""
        remote_files_table = self.query_one("#remote_files_table", DataTable)
        remote_files_table.clear()
        for file_info in files:
            remote_files_table.add_row(*map(str, file_info))

        # Update remote file info label
        self.update_remote_file_info_label(files, dirs, total_size)

    def update_remote_file_info_table(self) -> None:
        """
        Update the remote file info table with the contents of the currently selected directory.
        """
        self._load_remote_file_info()

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

    @on(DataTable.RowHighlighted, "#local_files_table")
    @on(DataTable.RowSelected, "#local_files_table")
    def on_local_row_selected(self, event: DataTable.RowSelected) -> None:
        """
        Set the locally selected file when a row is selected (Enter pressed).
        """
        parent_path = Path(self.local_site.value)
        table: DataTable = event.data_table
        selected_row = table.get_row(event.row_key)
        self.local_file_selected = parent_path / selected_row[0]

    @on(SFTPDirectoryTree.DirectorySelected)
    def on_remote_files_table_selected(
        self, event: SFTPDirectoryTree.DirectorySelected
    ) -> None:
        """
        Set the remote selected file when a row is selected (Enter pressed).
        """
        parent_path = event.path

        if self.local_file_selected.exists():
            self.remote_file_selected = f"{parent_path}/{self.local_file_selected.name}"

    # ----------- Local button event handlers -----------
    @on(Button.Pressed, "#local_delete")
    def on_local_delete(self, event: Button.Pressed) -> None:
        """
        Event handler for local delete button

        Deletes the selected file - Warns user before deleting
        """
        if self.local_file_selected:
            self.push_screen(  # type: ignore
                WarningScreen(
                    f"Do you really want to delete {self.local_file_selected}?"
                ),
                self._delete_local_file,
            )
        else:
            self.push_screen(WarningScreen("No file selected", cancel=False))

    def _delete_local_file(self, should_delete: bool) -> None:
        """
        Delete the local file
        """
        _delete_local_file(self, should_delete)

    @on(Button.Pressed, "#local_rename")
    def on_local_rename(self, event: Button.Pressed) -> None:
        """
        Event handler for local rename button
        """
        if self.local_file_selected:
            self.push_screen(  # type: ignore
                RenameScreen(self.local_file_selected), self._rename_local_file
            )
        else:
            self.push_screen(WarningScreen("No file selected", cancel=False))

    def _rename_local_file(self, new_name: Path | bool = False) -> None:
        """
        Rename the currently selected local file (if any)
        """
        _rename_local_file(self, new_name)

    @on(Button.Pressed, "#local_new_folder")
    def on_local_new_folder(self, event: Button.Pressed) -> None:
        """
        Event handler for the local new folder button

        Creates a new folder on the local machine
        """
        local_path = Path(self.local_site.value)
        self.push_screen(  # type: ignore
            NewFolderScreen(local_path), self.create_local_folder
        )

    def create_local_folder(self, folder_name: str | bool = False) -> None:
        """
        Create a new folder on the local machine with the given name
        """
        create_local_folder(self, folder_name)

    @on(Button.Pressed, "#upload")
    def on_upload(self, event: Button.Pressed) -> None:
        """
        Event handler for upload button

        Uploads a file to the server
        """
        # TODO - Verify with user if they want to upload
        self.upload()

    @work(exclusive=True, thread=True, group="upload")
    def upload(self) -> None:
        worker = get_current_worker()
        remote_tree = self.query_one("#remote_file_tree", SFTPDirectoryTree)

        # TODO - Need do differentiate between FTP and SFTP here or make the interface the same
        sftp_lock = remote_tree.get_sftp_lock()
        try:
            with sftp_lock:
                if self.ftp_client is not None:
                    self.ftp_client.put(
                        self.local_file_selected, self.remote_file_selected
                    )
                    if not worker.is_cancelled:
                        self.call_from_thread(
                            log,
                            self,
                            "success",
                            f"Successfully uploaded {self.local_file_selected} to {self.remote_file_selected} "
                            "on remote server",
                        )
                        self.call_from_thread(self.update_remote_ui)
        except Exception as e:
            if not worker.is_cancelled:
                self.call_from_thread(
                    log,
                    self,
                    "error",
                    f"Error uploading remote file {self.remote_file_selected}: {e}",
                )

    def update_remote_ui(self):
        """
        Update the remote tree and remote table UI after a file operation that changes
        the remote directory contents (upload, delete, rename, new folder)
        """
        remote_tree = self.query_one("#remote_file_tree", SFTPDirectoryTree)
        remote_tree.reload()
        self.update_remote_file_info_table()


if __name__ == "__main__":
    app = FileTuilla()
    app.run()
