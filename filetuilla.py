from textual import on
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Header, Input, Label, Tree

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
        yield Header()
        yield Vertical(
            Horizontal(
                host,
                username,
                password,
                port,
                Button("Connect", id="connect", variant="primary"),
                id="connection_form",
            ),
            id="main_container"
        )

    def on_mount(self) -> None:
        self.title = "FileTuilla"

if __name__ == "__main__":
    app = FileTuilla()
    app.run()
