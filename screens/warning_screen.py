from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label


class WarningScreen(ModalScreen):
    def __init__(self, message: str, cancel: bool = True, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.message = message
        self.cancel = cancel

    def compose(self) -> ComposeResult:
        if self.cancel:
            yield Vertical(
                Label(self.message, id="warning_message"),
                Horizontal(
                    Button("OK", id="ok_button", variant="primary"),
                    Button("Cancel", id="cancel_button", variant="error"),
                    id="warning_buttons",
                ),
                id="warning_screen",
            )
        else:
            yield Vertical(
                Label(self.message, id="warning_message"),
                Button("OK", id="ok_button", variant="primary"),
            )

    @on(Button.Pressed, "#ok_button")
    def on_okay(self, event: Button.Pressed) -> None:
        """
        Event handler for when the OK button - returns True via callback
        """
        self.dismiss(True)

    @on(Button.Pressed, "#cancel_button")
    def on_cancel(self, event: Button.Pressed) -> None:
        """
        Returns False to the calling application and dismisses the dialog
        """
        self.dismiss(False)
