"""SFTP Directory Tree widget for Textual applications.

This module provides an SFTPDirectoryTree widget that displays remote
directories via SFTP using paramiko, similar to how DirectoryTree
displays local filesystem directories.
"""

from __future__ import annotations

import stat
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import TYPE_CHECKING, Any, Iterable, Iterator

from rich.style import Style
from rich.text import Text, TextType

from textual import work
from textual.await_complete import AwaitComplete
from textual.message import Message
from textual.reactive import var
from textual.widgets._tree import TOGGLE_STYLE, Tree, TreeNode
from textual.worker import Worker, WorkerCancelled, WorkerFailed, get_current_worker

if TYPE_CHECKING:
    from typing_extensions import Self


@dataclass
class SFTPDirEntry:
    """Attaches directory information to an SFTPDirectoryTree node."""

    path: str
    """The remote path of the directory entry."""
    is_dir: bool
    """Whether this entry is a directory."""
    loaded: bool = False
    """Has this directory been loaded?"""


@dataclass(frozen=True)
class SFTPPathInfo:
    """Represents an item returned from an SFTP directory listing."""

    path: str
    """Full remote path."""
    name: str
    """Entry name (filename or directory name)."""
    is_dir: bool
    """Whether this is a directory."""


class SFTPDirectoryTree(Tree[SFTPDirEntry]):
    """A Tree widget that displays directories from an SFTP connection.

    This widget is similar to DirectoryTree but works with remote SFTP
    servers via paramiko instead of the local filesystem.
    """

    ICON_NODE_EXPANDED = "📂 "
    ICON_NODE = "📁 "
    ICON_FILE = "📄 "

    COMPONENT_CLASSES = {
        "directory-tree--extension",
        "directory-tree--file",
        "directory-tree--folder",
        "directory-tree--hidden",
    }

    DEFAULT_CSS = """
    SFTPDirectoryTree {
        overflow: auto;
        scrollbar-gutter: stable;

        & > .directory-tree--folder {
            text-style: bold;
        }
        & > .directory-tree--extension {
            text-style: italic;
        }
        & > .directory-tree--hidden {
            text-style: dim;
        }
    }
    """

    path: var[str] = var[str]("/", init=False, always_update=True)
    """The root path of the SFTP directory tree."""

    class FileSelected(Message):
        """Posted when a remote file is selected."""

        def __init__(self, node: TreeNode[SFTPDirEntry], path: str) -> None:
            super().__init__()
            self.node: TreeNode[SFTPDirEntry] = node
            """The tree node of the file that was selected."""
            self.path: str = path
            """The remote path of the file that was selected."""

        @property
        def control(self) -> Tree[SFTPDirEntry]:
            """The Tree that had a file selected."""
            return self.node.tree

    class DirectorySelected(Message):
        """Posted when a remote directory is selected."""

        def __init__(self, node: TreeNode[SFTPDirEntry], path: str) -> None:
            super().__init__()
            self.node: TreeNode[SFTPDirEntry] = node
            """The tree node of the directory that was selected."""
            self.path: str = path
            """The remote path of the directory that was selected."""

        @property
        def control(self) -> Tree[SFTPDirEntry]:
            """The Tree that had a directory selected."""
            return self.node.tree

    def __init__(
        self,
        path: str = "/",
        sftp_client: Any = None,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
    ) -> None:
        """Initialize the SFTP directory tree.

        Args:
            path: The root path to display.
            sftp_client: A paramiko SFTP client, or None for an empty tree.
            name: The name of the widget.
            id: The ID of the widget in the DOM.
            classes: Space-separated list of classes.
            disabled: Whether the widget is disabled.
        """
        self.sftp_client = sftp_client
        remote_path = self._normalize_path(path)
        super().__init__(
            self._label_for_path(remote_path),
            data=SFTPDirEntry(path=remote_path, is_dir=True),
            name=name,
            id=id,
            classes=classes,
            disabled=disabled,
        )
        self.root.allow_expand = True
        self.path = remote_path

    # -------------------------------------------------------------------------
    # Path utilities
    # -------------------------------------------------------------------------

    @staticmethod
    def _normalize_path(path: str) -> str:
        """Normalize a remote path to POSIX format.

        Args:
            path: The path to normalize.

        Returns:
            The normalized path string.
        """
        remote_path = str(path).replace("\\", "/")
        if not remote_path:
            return "/"
        normalized = str(PurePosixPath(remote_path))
        return normalized if normalized else "/"

    @staticmethod
    def _label_for_path(path: str) -> str:
        """Get a display label for a path.

        Args:
            path: The remote path.

        Returns:
            The label to display (typically the last component).
        """
        if path == "/":
            return "/"
        return PurePosixPath(path).name or path

    @staticmethod
    def _join_path(parent: str, child: str) -> str:
        """Join two path components.

        Args:
            parent: The parent path.
            child: The child path component.

        Returns:
            The joined path.
        """
        child = child.strip("/")
        if parent == "/":
            return f"/{child}"
        return f"{parent.rstrip('/')}/{child}"

    @staticmethod
    def _get_parents(path: str) -> set[str]:
        """Get all parent paths for a given path.

        Args:
            path: The path to get parents for.

        Returns:
            Set of parent path strings.
        """
        parent_paths: set[str] = set()
        for parent in PurePosixPath(path).parents:
            as_text = str(parent)
            parent_paths.add(as_text if as_text else "/")
        return parent_paths

    # -------------------------------------------------------------------------
    # SFTP client management
    # -------------------------------------------------------------------------

    def set_sftp_client(self, sftp_client: Any) -> None:
        """Set or update the SFTP client.

        Args:
            sftp_client: The paramiko SFTP client to use.
        """
        self.sftp_client = sftp_client

    def set_root_path(self, path: str) -> None:
        """Set a new root path for the directory tree.

        This will trigger a reload of the tree contents.

        Args:
            path: The new remote path to use as the root.
        """
        self.path = self._normalize_path(path)

    # -------------------------------------------------------------------------
    # Validation and path checking
    # -------------------------------------------------------------------------

    def validate_path(self, path: str) -> str:
        """Validate and normalize a path.

        Args:
            path: The path to validate.

        Returns:
            The normalized path string.
        """
        return self._normalize_path(path)

    def _safe_is_dir(self, path: str) -> bool:
        """Check if a path is a directory without blocking the UI.

        This method avoids making network calls. It checks cached data
        from tree nodes, or defaults to True to allow expansion.

        Args:
            path: The remote path to check.

        Returns:
            True if the path is a directory, False otherwise.
        """
        remote_path = self._normalize_path(path)

        # Root is always a directory
        if remote_path == "/" or remote_path == self.path:
            return True

        # Try to find cached info from tree nodes
        def find_in_tree(node: TreeNode[SFTPDirEntry], target: str) -> bool | None:
            if node.data is not None and node.data.path == target:
                return node.data.is_dir
            for child in node.children:
                result = find_in_tree(child, target)
                if result is not None:
                    return result
            return None

        cached = find_in_tree(self.root, remote_path)
        if cached is not None:
            return cached

        # Default to True - actual check happens during directory load
        return True

    # -------------------------------------------------------------------------
    # Tree reload and watch
    # -------------------------------------------------------------------------

    def reload(self) -> AwaitComplete:
        """Reload the directory tree contents.

        Returns:
            An awaitable that completes when the tree has finished reloading.
        """
        return AwaitComplete(self._reload(self.root))

    def reload_node(self, node: TreeNode[SFTPDirEntry]) -> AwaitComplete:
        """Reload a specific node's contents.

        Args:
            node: The node to reload.

        Returns:
            An awaitable that completes when the node has finished reloading.
        """
        return AwaitComplete(self._reload(node))

    def clear_node(self, node: TreeNode[SFTPDirEntry]) -> Self:
        """Clear all children of a node.

        Args:
            node: The node to clear.

        Returns:
            This tree instance.
        """
        self._clear_line_cache()
        node.remove_children()
        self._updates += 1
        self.refresh()
        return self

    def reset_node(
        self,
        node: TreeNode[SFTPDirEntry],
        label: TextType,
        data: SFTPDirEntry | None = None,
    ) -> Self:
        """Clear and reset a node.

        Args:
            node: The node to reset.
            label: The new label for the node.
            data: Optional new data for the node.

        Returns:
            This tree instance.
        """
        self.clear_node(node)
        node.label = label
        node.data = data
        return self

    async def watch_path(self) -> None:
        """React to changes in the path reactive variable."""
        has_cursor = self.cursor_node is not None
        self.reset_node(
            self.root,
            self._label_for_path(self.path),
            SFTPDirEntry(self.path, is_dir=True),
        )
        await self.reload()
        if has_cursor:
            self.cursor_line = 0
        self.scroll_to(0, 0, animate=False)

    async def _reload(self, node: TreeNode[SFTPDirEntry]) -> None:
        """Reload a subtree while preserving expansion state.

        Args:
            node: The root of the subtree to reload.
        """
        async with self.lock:
            # Track currently expanded nodes
            currently_open: set[str] = set()
            to_check: list[TreeNode[SFTPDirEntry]] = [node]
            while to_check:
                checking = to_check.pop()
                if checking.allow_expand and checking.is_expanded:
                    if checking.data:
                        currently_open.add(checking.data.path)
                    to_check.extend(checking.children)

            # Track highlighted node
            highlighted_path: str | None = None
            if self.cursor_line > -1:
                highlighted_node = self.get_node_at_line(self.cursor_line)
                if highlighted_node is not None and highlighted_node.data is not None:
                    highlighted_path = highlighted_node.data.path

            # Reset the node
            if node.data is not None:
                self.reset_node(
                    node,
                    self._label_for_path(node.data.path),
                    SFTPDirEntry(node.data.path, is_dir=True),
                )

            # Reopen previously expanded nodes
            to_reopen = [node]
            while to_reopen:
                reopening = to_reopen.pop()
                if not reopening.data:
                    continue
                if reopening.allow_expand and (
                    reopening.data.path in currently_open or reopening == node
                ):
                    try:
                        content = await self._load_directory(reopening).wait()
                    except (WorkerCancelled, WorkerFailed):
                        continue
                    reopening.data.loaded = True
                    self._populate_node(reopening, content)
                    to_reopen.extend(reopening.children)
                    reopening.expand()

            # Restore highlighted node
            if highlighted_path is None:
                return

            looking = [node]
            highlight_candidates = self._get_parents(highlighted_path)
            highlight_candidates.add(highlighted_path)
            best_found: TreeNode[SFTPDirEntry] | None = None
            while looking:
                checking = looking.pop()
                checking_path = (
                    checking.data.path if checking.data is not None else None
                )
                if checking_path in highlight_candidates:
                    best_found = checking
                    if checking_path == highlighted_path:
                        break
                if (
                    checking.allow_expand
                    and checking.is_expanded
                    and checking_path in self._get_parents(highlighted_path)
                ):
                    looking.extend(checking.children)
            if best_found is not None:
                _ = self._tree_lines
                self.cursor_line = best_found.line

    # -------------------------------------------------------------------------
    # Rendering
    # -------------------------------------------------------------------------

    def process_label(self, label: TextType) -> Text:
        """Process a label for display.

        Args:
            label: The label to process.

        Returns:
            A Rich Text object.
        """
        if isinstance(label, str):
            text_label = Text(label)
        else:
            text_label = label
        first_line = text_label.split()[0]
        return first_line

    def render_label(
        self, node: TreeNode[SFTPDirEntry], base_style: Style, style: Style
    ) -> Text:
        """Render a node's label.

        Args:
            node: The tree node.
            base_style: The base style of the widget.
            style: Additional style for the label.

        Returns:
            A Rich Text object containing the rendered label.
        """
        node_label = node._label.copy()
        node_label.stylize(style)

        if not self.is_mounted:
            return node_label

        if node._allow_expand:
            prefix = (
                self.ICON_NODE_EXPANDED if node.is_expanded else self.ICON_NODE,
                base_style + TOGGLE_STYLE,
            )
            node_label.stylize_before(
                self.get_component_rich_style("directory-tree--folder", partial=True)
            )
        else:
            prefix = (
                self.ICON_FILE,
                base_style,
            )
            node_label.stylize_before(
                self.get_component_rich_style("directory-tree--file", partial=True),
            )
            node_label.highlight_regex(
                r"\..+$",
                self.get_component_rich_style(
                    "directory-tree--extension", partial=True
                ),
            )

        if node_label.plain.startswith("."):
            node_label.stylize_before(
                self.get_component_rich_style("directory-tree--hidden", partial=True)
            )

        text = Text.assemble(prefix, node_label)
        return text

    # -------------------------------------------------------------------------
    # Directory loading via SFTP
    # -------------------------------------------------------------------------

    def filter_paths(self, entries: Iterable[SFTPPathInfo]) -> Iterable[SFTPPathInfo]:
        """Filter entries before adding them to the tree.

        Override this method to implement custom filtering.

        Args:
            entries: The entries to filter.

        Returns:
            The filtered entries.
        """
        return entries

    def _populate_node(
        self, node: TreeNode[SFTPDirEntry], content: Iterable[SFTPPathInfo]
    ) -> None:
        """Populate a tree node with directory content.

        Args:
            node: The node to populate.
            content: The entries to add as children.
        """
        node.remove_children()
        for entry in content:
            node.add(
                entry.name,
                data=SFTPDirEntry(path=entry.path, is_dir=entry.is_dir),
                allow_expand=entry.is_dir,
            )
        node.expand()

    def _directory_content(
        self, location: str, worker: Worker
    ) -> Iterator[SFTPPathInfo]:
        """Load directory content from SFTP.

        Args:
            location: The remote path to list.
            worker: The worker performing the load.

        Yields:
            SFTPPathInfo objects for each entry.
        """
        if self.sftp_client is None:
            return
        try:
            for entry in self.sftp_client.listdir_attr(location):
                if worker.is_cancelled:
                    break
                entry_name = entry.filename
                full_path = self._join_path(location, entry_name)
                is_dir = stat.S_ISDIR(entry.st_mode)
                yield SFTPPathInfo(full_path, entry_name, is_dir)
        except OSError:
            return

    @work(thread=True, exit_on_error=False)
    def _load_directory(self, node: TreeNode[SFTPDirEntry]) -> list[SFTPPathInfo]:
        """Load directory contents in a background thread.

        Args:
            node: The node whose directory to load.

        Returns:
            Sorted list of SFTPPathInfo entries.
        """
        assert node.data is not None
        remote_path = self._normalize_path(node.data.path)
        entries = self.filter_paths(
            self._directory_content(remote_path, get_current_worker())
        )
        return sorted(
            entries,
            key=lambda entry: (not entry.is_dir, entry.name.lower()),
        )

    # -------------------------------------------------------------------------
    # Event handlers
    # -------------------------------------------------------------------------

    async def _on_tree_node_expanded(
        self, event: Tree.NodeExpanded[SFTPDirEntry]
    ) -> None:
        """Handle node expansion."""
        event.stop()
        dir_entry = event.node.data
        if dir_entry is None:
            return

        if dir_entry.is_dir:
            if not dir_entry.loaded:
                dir_entry.loaded = True
                try:
                    content = await self._load_directory(event.node).wait()
                    self._populate_node(event.node, content)
                except (WorkerCancelled, WorkerFailed):
                    dir_entry.loaded = False
        else:
            self.post_message(self.FileSelected(event.node, dir_entry.path))

    async def _on_tree_node_selected(
        self, event: Tree.NodeSelected[SFTPDirEntry]
    ) -> None:
        """Handle node selection."""
        event.stop()
        dir_entry = event.node.data
        if dir_entry is None:
            return

        if dir_entry.is_dir:
            self.post_message(self.DirectorySelected(event.node, dir_entry.path))
        else:
            self.post_message(self.FileSelected(event.node, dir_entry.path))
