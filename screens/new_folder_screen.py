from pathlib import Path

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Header, Label, Input


class NewFolderScreen(ModalScreen):
    CSS_PATH = "new_folder_screen.tcss"

    def __init__(self, parent_path: Path, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.parent_path = parent_path
        self.title = "New Local Folder"

    def compose(self) -> ComposeResult:
        yield Vertical(
            Header(),
            Label("Create New Local Folder:"),
            Input(placeholder="Enter new local folder path", id="new_local_folder"),
            Horizontal(
                Button("Save", id="save_local_folder_button", variant="primary"),
                Button("Cancel", id="cancel_local_folder_button", variant="warning"),
                id="save_new_folder_button_row",
            ),
            id="new_local_folder_screen_vlayout",
        )

    @on(Button.Pressed, "#save_local_folder_button")
    def on_save_new_folder(self, event: Button.Pressed) -> None:
        """
        Event handler for when the save button is pressed
        """
        new_folder_name = self.query_one("#new_local_folder", Input).value
        if new_folder_name:
            new_folder_path = self.parent_path / new_folder_name
            self.dismiss(new_folder_path)
            return
        self.dismiss(False)

    @on(Button.Pressed, "#cancel_local_folder_button")
    def on_cancel_new_folder(self, event: Button.Pressed) -> None:
        """
        Event handler for when the cancel button is pressed
        """
        self.dismiss(False)
