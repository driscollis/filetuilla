from pathlib import Path

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Header, Label, Input


class RenameScreen(ModalScreen):
    CSS_PATH = "rename_screen.tcss"

    def __init__(
        self, file_path: Path | str, remote: bool = True, *args, **kwargs
    ) -> None:
        super().__init__(*args, **kwargs)
        self.file_path = file_path
        self.title = "Rename File"
        self.remote = remote

    def compose(self) -> ComposeResult:
        yield Vertical(
            Header(),
            Label(f"Original file name: {self.file_path}", id="original_file_label"),
            Input(placeholder="Enter new file name", id="new_file_input"),
            Horizontal(
                Button("Save", id="save_button", variant="primary"),
                Button("Cancel", id="cancel_button", variant="warning"),
                id="rename_button_row",
            ),
            id="rename_screen_vlayout",
        )

    @on(Button.Pressed, "#save_button")
    def on_save(self, event: Button.Pressed) -> None:
        """
        Event handler for when the save button is pressed
        """
        new_file_name = self.query_one("#new_file_input", Input).value
        if self.remote and new_file_name:
            # Remote file paths need to be strings
            self.dismiss(str(new_file_name))
        elif new_file_name:
            self.dismiss(Path(new_file_name))
            return
        self.dismiss(False)

    @on(Button.Pressed, "#cancel_button")
    def on_cancel(self, event: Button.Pressed) -> None:
        """
        Event handler for when the cancel button is pressed
        """
        self.dismiss(False)
