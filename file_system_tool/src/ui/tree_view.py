"""
tree_view.py — Reusable directory-tree widget for the File System Simulator.

Wraps a ``ttk.Treeview`` and binds it to a
:class:`~src.core.directory.DirectoryTree` model so the user can
browse, create, delete, and inspect files and directories interactively.

Usage::

    from src.ui.tree_view import TreeView

    tree_view = TreeView(parent_frame, directory_tree,
                         fat=fat, fsm=fsm, disk=disk, journal=journal)
    tree_view.refresh()
"""

import logging
import tkinter as tk
from datetime import datetime
from tkinter import ttk, messagebox, simpledialog
from typing import Callable, Dict, List, Optional

from src.core.directory import DirectoryTree, DirectoryNode
from src.core.file_allocation_table import FileAllocationTable
from src.core.free_space import FreeSpaceManager
from src.core.inode import Inode

logger = logging.getLogger(__name__)


# =========================================================================== #
#  Tooltip helper
# =========================================================================== #

class _ToolTip:
    """Minimal tooltip that follows the mouse on a Treeview row."""

    _DELAY_MS = 400

    def __init__(self, widget: tk.Widget):
        self._widget = widget
        self._tip_window: Optional[tk.Toplevel] = None
        self._text = ""
        self._after_id: Optional[str] = None

        widget.bind("<Motion>", self._on_motion, add="+")
        widget.bind("<Leave>", self._hide, add="+")

    # ------------------------------------------------------------------ #

    def _on_motion(self, event: tk.Event):
        """Schedule a tooltip for the row under the cursor."""
        self._hide()
        self._after_id = self._widget.after(self._DELAY_MS,
                                             lambda: self._show(event))

    def _show(self, event: tk.Event):
        """Display the tooltip window."""
        tree: ttk.Treeview = self._widget  # type: ignore[assignment]
        row_id = tree.identify_row(event.y)
        if not row_id:
            return

        values = tree.item(row_id, "values")
        text_parts = [tree.item(row_id, "text")]
        if values:
            text_parts.append(f"Type: {values[0]}")
            if len(values) > 1 and values[1]:
                text_parts.append(f"Size: {values[1]}")
            if len(values) > 2 and values[2]:
                text_parts.append(f"Modified: {values[2]}")
        tip_text = "\n".join(text_parts)

        self._tip_window = tw = tk.Toplevel(self._widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{event.x_root + 18}+{event.y_root + 12}")
        label = tk.Label(tw, text=tip_text, justify=tk.LEFT,
                         background="#313244", foreground="#cdd6f4",
                         relief=tk.SOLID, borderwidth=1,
                         font=("Segoe UI", 9), padx=6, pady=4)
        label.pack()

    def _hide(self, _event=None):
        """Destroy the tooltip window."""
        if self._after_id:
            self._widget.after_cancel(self._after_id)
            self._after_id = None
        if self._tip_window:
            self._tip_window.destroy()
            self._tip_window = None


# =========================================================================== #
#  TreeView
# =========================================================================== #

class TreeView:
    """
    Interactive directory-tree component backed by ``ttk.Treeview``.

    Attributes
    ----------
    parent_frame : ttk.Frame
        The container this widget lives in.
    directory_tree : DirectoryTree
        The authoritative model for the file-system hierarchy.
    tree_widget : ttk.Treeview
        The underlying Tkinter treeview widget.
    selected_path : str
        The absolute path of the currently selected item (or ``""``).
    context_menu : tk.Menu
        Right-click context menu.
    """

    # --------------------------------------------------------------------- #
    #  Construction
    # --------------------------------------------------------------------- #

    def __init__(self, parent_frame: ttk.Frame,
                 directory_tree: DirectoryTree,
                 *,
                 fat: Optional[FileAllocationTable] = None,
                 fsm: Optional[FreeSpaceManager] = None,
                 disk=None,
                 journal=None,
                 on_select_callback: Optional[Callable] = None,
                 on_change_callback: Optional[Callable] = None,
                 inode_counter_ref: Optional[list] = None):
        """
        Build the tree-view widget inside *parent_frame*.

        Parameters
        ----------
        parent_frame : ttk.Frame
            Container widget.
        directory_tree : DirectoryTree
            The directory model to visualise.
        fat : FileAllocationTable, optional
            For block-allocation display and file creation.
        fsm : FreeSpaceManager, optional
            For block allocation during file creation.
        disk : Disk, optional
            For block reads/writes during file creation.
        journal : Journal, optional
            For transaction logging.
        on_select_callback : callable, optional
            Called with ``(path: str)`` whenever the selection changes.
        on_change_callback : callable, optional
            Called (no args) after any mutation so the parent can refresh.
        inode_counter_ref : list[int], optional
            Single-element list used as a mutable shared counter for
            inode numbering (e.g. ``[5]``).
        """
        self.parent_frame = parent_frame
        self.directory_tree = directory_tree
        self.selected_path: str = ""
        self._on_select = on_select_callback
        self._on_change = on_change_callback

        # Optional FS components for file operations
        self._fat = fat
        self._fsm = fsm
        self._disk = disk
        self._journal = journal
        self._inode_counter_ref = inode_counter_ref or [1]

        # ---- Build the treeview ----
        columns = ("type", "size", "modified")
        self.tree_widget = ttk.Treeview(
            parent_frame,
            columns=columns,
            show="tree headings",
            selectmode="browse",
        )
        self.tree_widget.heading("#0", text="Name", anchor=tk.W)
        self.tree_widget.heading("type", text="Type", anchor=tk.W)
        self.tree_widget.heading("size", text="Size", anchor=tk.E)
        self.tree_widget.heading("modified", text="Modified", anchor=tk.W)

        self.tree_widget.column("#0", width=220, minwidth=120, stretch=True)
        self.tree_widget.column("type", width=80, minwidth=50, stretch=False)
        self.tree_widget.column("size", width=80, minwidth=50,
                                stretch=False, anchor=tk.E)
        self.tree_widget.column("modified", width=130, minwidth=80,
                                stretch=False)

        # Scrollbars
        v_scroll = ttk.Scrollbar(parent_frame, orient=tk.VERTICAL,
                                  command=self.tree_widget.yview)
        h_scroll = ttk.Scrollbar(parent_frame, orient=tk.HORIZONTAL,
                                  command=self.tree_widget.xview)
        self.tree_widget.configure(yscrollcommand=v_scroll.set,
                                    xscrollcommand=h_scroll.set)

        # Grid layout
        self.tree_widget.grid(row=0, column=0, sticky="nsew")
        v_scroll.grid(row=0, column=1, sticky="ns")
        h_scroll.grid(row=1, column=0, sticky="ew")
        parent_frame.grid_rowconfigure(0, weight=1)
        parent_frame.grid_columnconfigure(0, weight=1)

        # ---- Context menu ----
        self.context_menu = self._create_context_menu()

        # ---- Tooltip ----
        _ToolTip(self.tree_widget)

        # ---- Bind events ----
        self.tree_widget.bind("<<TreeviewSelect>>", self.on_select)
        self.tree_widget.bind("<Double-1>", self.on_double_click)

        # Right-click (platform-aware)
        self.tree_widget.bind("<Button-3>", self.on_right_click)
        self.tree_widget.bind("<Button-2>", self.on_right_click)  # macOS

        # ---- Populate ----
        self.populate_tree()

    # --------------------------------------------------------------------- #
    #  Population
    # --------------------------------------------------------------------- #

    def populate_tree(self, parent_item: str = "",
                      parent_node: Optional[DirectoryNode] = None):
        """
        Recursively populate the treeview from the directory model.

        Parameters
        ----------
        parent_item : str
            Internal treeview item ID of the parent row (``""`` for root).
        parent_node : DirectoryNode or None
            Starting node; defaults to the tree root.
        """
        if parent_node is None:
            parent_node = self.directory_tree.root

        for child_name in sorted(parent_node.children.keys()):
            child = parent_node.children[child_name]
            icon = "📁" if child.is_directory else "📄"
            kind = "Directory" if child.is_directory else "File"

            # Size
            size_str = ""
            if not child.is_directory and child.inode is not None:
                size_str = self._format_size(child.inode.size_bytes)

            # Modified time
            mod_str = ""
            if child.inode is not None:
                mod_str = self._format_date(child.inode.modified_time)
            else:
                mod_str = self._format_date(child.created_time)

            iid = self.tree_widget.insert(
                parent_item, tk.END,
                text=f"{icon} {child_name}",
                values=(kind, size_str, mod_str),
                open=child.is_directory,
            )

            if child.is_directory:
                self.populate_tree(parent_item=iid, parent_node=child)

    # --------------------------------------------------------------------- #
    #  Refresh
    # --------------------------------------------------------------------- #

    def refresh(self):
        """Clear and re-populate the tree, restoring selection if possible."""
        saved_path = self.selected_path

        self.tree_widget.delete(*self.tree_widget.get_children())
        self.populate_tree()

        if saved_path:
            self.expand_to_path(saved_path)

    # --------------------------------------------------------------------- #
    #  Event handlers
    # --------------------------------------------------------------------- #

    def on_select(self, event):
        """Handle item selection — update ``selected_path`` and fire callback."""
        sel = self.tree_widget.selection()
        if not sel:
            self.selected_path = ""
            return
        item_id = sel[0]
        self.selected_path = self._get_item_path(item_id)
        if self._on_select:
            self._on_select(self.selected_path)

    def on_double_click(self, event):
        """
        Handle double-click.

        * Directory → toggle expand / collapse
        * File     → show properties dialog
        """
        item_id = self.tree_widget.identify_row(event.y)
        if not item_id:
            return

        values = self.tree_widget.item(item_id, "values")
        if not values:
            return

        kind = values[0]
        if kind == "Directory":
            # Toggle open state
            is_open = self.tree_widget.item(item_id, "open")
            self.tree_widget.item(item_id, open=not is_open)
        else:
            path = self._get_item_path(item_id)
            self.show_properties(path)

    def on_right_click(self, event):
        """Show the context menu at the cursor position."""
        item_id = self.tree_widget.identify_row(event.y)
        if item_id:
            self.tree_widget.selection_set(item_id)
            self.selected_path = self._get_item_path(item_id)
        self._update_context_menu()
        try:
            self.context_menu.tk_popup(event.x_root, event.y_root, 0)
        finally:
            self.context_menu.grab_release()

    # --------------------------------------------------------------------- #
    #  Context menu
    # --------------------------------------------------------------------- #

    def _create_context_menu(self) -> tk.Menu:
        """Build the right-click context menu."""
        root_widget = self.parent_frame.winfo_toplevel()

        menu_kw = dict(tearoff=0)
        # Try to pick up the parent's palette colours
        try:
            bg = root_widget.cget("bg")
            menu_kw.update(bg="#313244", fg="#cdd6f4",
                           activebackground="#89b4fa",
                           activeforeground="#1e1e2e")
        except tk.TclError:
            pass

        menu = tk.Menu(root_widget, **menu_kw)

        menu.add_command(label="📄 Create File…",
                         command=self.create_file_dialog)
        menu.add_command(label="📁 Create Directory…",
                         command=self.create_directory_dialog)
        menu.add_separator()
        menu.add_command(label="🗑  Delete", command=self.delete_item)
        menu.add_separator()
        menu.add_command(label="ℹ  Properties…",
                         command=lambda: self.show_properties(self.selected_path))
        menu.add_command(label="👁  View Content",
                         command=self._view_content)
        return menu

    def _update_context_menu(self):
        """Enable / disable menu items depending on the selection type."""
        node = self.directory_tree.resolve_path(self.selected_path)
        is_dir = node.is_directory if node else True

        # "View Content" only for files
        try:
            self.context_menu.entryconfigure("👁  View Content",
                                              state=tk.NORMAL if not is_dir
                                              else tk.DISABLED)
        except tk.TclError:
            pass

    # --------------------------------------------------------------------- #
    #  Create file
    # --------------------------------------------------------------------- #

    def create_file_dialog(self):
        """Prompt the user for a filename and block count, then create it."""
        root_w = self.parent_frame.winfo_toplevel()
        try:
            # Use selected directory as base or fall back to "/"
            base = self.selected_path or "/"
            node = self.directory_tree.resolve_path(base)
            if node and not node.is_directory:
                # User selected a file — go to its parent
                base = base.rsplit("/", 1)[0] or "/"

            filename = simpledialog.askstring(
                "Create File",
                f"File name (relative to {base}):",
                parent=root_w)
            if not filename:
                return

            num_blocks = simpledialog.askinteger(
                "Create File", "Number of blocks:", parent=root_w,
                initialvalue=2, minvalue=1, maxvalue=100)
            if num_blocks is None:
                return

            full_path = f"{base.rstrip('/')}/{filename}"

            # Allocate blocks if FSM is available
            blocks: list = []
            if self._fsm is not None:
                blocks = self._fsm.allocate_blocks(num_blocks,
                                                    contiguous=False) or []
                if not blocks:
                    messagebox.showwarning("Allocation Failed",
                                           "Not enough free space.",
                                           parent=root_w)
                    return

            # Build inode
            inode_num = self._inode_counter_ref[0]
            block_size = getattr(self._disk, "block_size", 4096)
            inode = Inode(inode_number=inode_num, file_type="file",
                          size=num_blocks * block_size)

            # Ensure parent directories exist
            parent_dir = full_path.rsplit("/", 1)[0] or "/"
            self.directory_tree.create_directory(parent_dir)

            if not self.directory_tree.create_file(full_path, inode):
                messagebox.showwarning("Create File",
                                       f"Could not create '{full_path}'.",
                                       parent=root_w)
                return

            # FAT allocation
            if self._fat is not None and blocks:
                self._fat.allocate(inode_num, blocks)

            # Write placeholder data
            if self._disk is not None:
                for b in blocks:
                    self._disk.write_block(
                        b,
                        f"DATA_{inode_num}".encode().ljust(block_size, b"\x00"))

            # Journal
            if self._journal is not None:
                txn = self._journal.begin_transaction(
                    "CREATE",
                    {"path": full_path, "inode": inode_num, "blocks": blocks})
                self._journal.commit_transaction(txn)

            self._inode_counter_ref[0] += 1
            self.refresh()
            self._fire_change()
            logger.info("TreeView: created file %s", full_path)

        except Exception as exc:
            logger.exception("create_file_dialog failed")
            messagebox.showerror("Error", str(exc),
                                 parent=root_w)

    # --------------------------------------------------------------------- #
    #  Create directory
    # --------------------------------------------------------------------- #

    def create_directory_dialog(self):
        """Prompt the user for a directory name and create it."""
        root_w = self.parent_frame.winfo_toplevel()
        try:
            base = self.selected_path or "/"
            node = self.directory_tree.resolve_path(base)
            if node and not node.is_directory:
                base = base.rsplit("/", 1)[0] or "/"

            dirname = simpledialog.askstring(
                "Create Directory",
                f"Directory name (relative to {base}):",
                parent=root_w)
            if not dirname:
                return

            full_path = f"{base.rstrip('/')}/{dirname}"

            if not self.directory_tree.create_directory(full_path):
                messagebox.showwarning("Create Directory",
                                       f"Could not create '{full_path}'.",
                                       parent=root_w)
                return

            # Journal
            if self._journal is not None:
                txn = self._journal.begin_transaction(
                    "MKDIR", {"path": full_path})
                self._journal.commit_transaction(txn)

            self.refresh()
            self._fire_change()
            logger.info("TreeView: created directory %s", full_path)

        except Exception as exc:
            logger.exception("create_directory_dialog failed")
            messagebox.showerror("Error", str(exc), parent=root_w)

    # --------------------------------------------------------------------- #
    #  Delete
    # --------------------------------------------------------------------- #

    def delete_item(self):
        """Delete the currently selected file or directory after confirmation."""
        root_w = self.parent_frame.winfo_toplevel()
        path = self.selected_path
        if not path or path == "/":
            messagebox.showwarning("Delete",
                                   "Cannot delete root directory.",
                                   parent=root_w)
            return

        node = self.directory_tree.resolve_path(path)
        if node is None:
            messagebox.showwarning("Delete",
                                   f"'{path}' not found.",
                                   parent=root_w)
            return

        kind = "directory" if node.is_directory else "file"
        if not messagebox.askyesno(
                "Confirm Delete",
                f"Delete {kind} '{path}'?",
                parent=root_w):
            return

        try:
            # Free blocks
            if node.inode is not None and self._fat is not None:
                freed = self._fat.deallocate(node.inode.inode_number)
                if freed and self._fsm is not None:
                    self._fsm.deallocate_blocks(freed)

            self.directory_tree.delete(path, recursive=True)

            # Journal
            if self._journal is not None:
                txn = self._journal.begin_transaction(
                    "DELETE", {"path": path})
                self._journal.commit_transaction(txn)

            self.selected_path = ""
            self.refresh()
            self._fire_change()
            logger.info("TreeView: deleted %s", path)

        except Exception as exc:
            logger.exception("delete_item failed")
            messagebox.showerror("Error", str(exc), parent=root_w)

    # --------------------------------------------------------------------- #
    #  Properties dialog
    # --------------------------------------------------------------------- #

    def show_properties(self, path: str):
        """
        Display a properties dialog for the item at *path*.

        Shows: path, type, size, created / modified times, inode number,
        and block allocation.
        """
        root_w = self.parent_frame.winfo_toplevel()
        if not path:
            return

        node = self.directory_tree.resolve_path(path)
        if node is None:
            messagebox.showwarning("Properties",
                                   f"'{path}' not found.",
                                   parent=root_w)
            return

        kind = "Directory" if node.is_directory else "File"
        lines = [
            f"Path:           {path}",
            f"Type:           {kind}",
        ]

        if node.inode is not None:
            ino = node.inode
            lines.extend([
                f"Inode number:   {ino.inode_number}",
                f"Size:           {self._format_size(ino.size_bytes)}"
                f" ({ino.size_bytes:,} bytes)",
                f"Block count:    {ino.block_count}",
                f"Permissions:    {ino.permissions}",
                f"Owner:          {ino.owner}",
                f"",
                f"Created:        {self._format_date(ino.created_time)}",
                f"Modified:       {self._format_date(ino.modified_time)}",
                f"Accessed:       {self._format_date(ino.accessed_time)}",
            ])

            # Block allocation
            if self._fat is not None:
                blocks = self._fat.get_file_blocks(ino.inode_number)
                if blocks:
                    block_str = ", ".join(str(b) for b in blocks[:20])
                    if len(blocks) > 20:
                        block_str += f" … (+{len(blocks) - 20} more)"
                    lines.append(f"")
                    lines.append(f"Blocks [{len(blocks)}]:  {block_str}")
        else:
            lines.extend([
                f"Created:        {self._format_date(node.created_time)}",
            ])
            if node.is_directory:
                lines.append(
                    f"Children:       {len(node.children)}")

        messagebox.showinfo(f"Properties — {node.name}",
                            "\n".join(lines),
                            parent=root_w)

    # --------------------------------------------------------------------- #
    #  View content (files only)
    # --------------------------------------------------------------------- #

    def _view_content(self):
        """Read and display blocked content from disk for the selected file."""
        root_w = self.parent_frame.winfo_toplevel()
        path = self.selected_path
        if not path:
            return

        node = self.directory_tree.resolve_path(path)
        if node is None or node.is_directory or node.inode is None:
            messagebox.showinfo("View Content",
                                "No content to display.",
                                parent=root_w)
            return

        if self._fat is None or self._disk is None:
            messagebox.showinfo("View Content",
                                "Disk/FAT not available.",
                                parent=root_w)
            return

        blocks = self._fat.get_file_blocks(node.inode.inode_number)
        if not blocks:
            messagebox.showinfo("View Content",
                                "No blocks allocated for this file.",
                                parent=root_w)
            return

        # Read up to the first 5 blocks and display as text
        content_parts: list = []
        for b in blocks[:5]:
            try:
                data = self._disk.read_block(b)
                text = data.rstrip(b"\x00").decode("utf-8", errors="replace")
                content_parts.append(f"[Block {b}] {text}")
            except Exception:
                content_parts.append(f"[Block {b}] <read error>")

        if len(blocks) > 5:
            content_parts.append(f"… ({len(blocks) - 5} more blocks)")

        messagebox.showinfo(f"Content — {node.name}",
                            "\n".join(content_parts),
                            parent=root_w)

    # --------------------------------------------------------------------- #
    #  Selection helpers
    # --------------------------------------------------------------------- #

    def get_selected_path(self) -> Optional[str]:
        """Return the path of the selected item, or ``None`` if nothing selected."""
        sel = self.tree_widget.selection()
        if not sel:
            return None
        return self._get_item_path(sel[0])

    def expand_to_path(self, path: str):
        """
        Expand the tree to reveal *path* and select it.

        If the path does not map to an existing treeview item the
        method silently returns.
        """
        parts = [p for p in path.split("/") if p]
        current_items = self.tree_widget.get_children("")
        current_id = None

        for part in parts:
            found = False
            for cid in current_items:
                text = self.tree_widget.item(cid, "text")
                # Strip icon prefix added during populate
                clean = text.lstrip("📁📄 ").strip()
                if clean == part:
                    self.tree_widget.item(cid, open=True)
                    current_id = cid
                    current_items = self.tree_widget.get_children(cid)
                    found = True
                    break
            if not found:
                return

        if current_id:
            self.tree_widget.selection_set(current_id)
            self.tree_widget.see(current_id)
            self.selected_path = path

    # --------------------------------------------------------------------- #
    #  Search
    # --------------------------------------------------------------------- #

    def search_tree(self, search_term: str) -> List[str]:
        """
        Search the directory tree for items whose name contains *search_term*.

        Matching items are highlighted (selected) in the treeview and
        their paths returned.

        Parameters
        ----------
        search_term : str
            Case-insensitive substring to match against node names.

        Returns
        -------
        list[str]
            Absolute paths of every matching node.
        """
        matches: List[str] = []
        self._search_node(self.directory_tree.root, search_term.lower(),
                          matches)

        # Highlight matches in the widget
        matching_ids: list = []
        self._find_matching_ids("", search_term.lower(), matching_ids)
        if matching_ids:
            self.tree_widget.selection_set(*matching_ids)
            self.tree_widget.see(matching_ids[0])

        return matches

    def _search_node(self, node: DirectoryNode, term: str,
                     results: List[str]):
        """Recursively search from *node* and collect matching paths."""
        if term in node.name.lower():
            results.append(node.get_full_path())
        if node.is_directory:
            for child in node.children.values():
                self._search_node(child, term, results)

    def _find_matching_ids(self, parent: str, term: str,
                           result_ids: list):
        """Walk the treeview items and collect IDs whose text matches."""
        for cid in self.tree_widget.get_children(parent):
            text = self.tree_widget.item(cid, "text").lower()
            if term in text:
                result_ids.append(cid)
            self._find_matching_ids(cid, term, result_ids)

    # --------------------------------------------------------------------- #
    #  Private helpers
    # --------------------------------------------------------------------- #

    def _get_item_path(self, item_id: str) -> str:
        """
        Walk from *item_id* to the root and build the full path.

        Strips emoji icon prefixes added during ``populate_tree``.
        """
        parts: list = []
        current = item_id
        while current:
            text = self.tree_widget.item(current, "text")
            # Strip the emoji icon prefix
            clean = text.lstrip("📁📄 ").strip()
            if clean:
                parts.append(clean)
            current = self.tree_widget.parent(current)
        parts.reverse()
        if not parts:
            return "/"
        return "/" + "/".join(parts)

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        """
        Format a byte count as a human-readable string.

        Examples: ``"0 B"``, ``"4.0 KB"``, ``"1.5 MB"``, ``"2.3 GB"``
        """
        if size_bytes < 0:
            return "0 B"
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 ** 2:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 ** 3:
            return f"{size_bytes / 1024 ** 2:.1f} MB"
        else:
            return f"{size_bytes / 1024 ** 3:.1f} GB"

    @staticmethod
    def _format_date(timestamp: datetime) -> str:
        """
        Format a ``datetime`` for display (``YYYY-MM-DD HH:MM``).
        """
        if isinstance(timestamp, datetime):
            return timestamp.strftime("%Y-%m-%d %H:%M")
        return str(timestamp)

    def _fire_change(self):
        """Notify the parent that the tree model was mutated."""
        if self._on_change:
            try:
                self._on_change()
            except Exception:
                logger.debug("on_change callback failed", exc_info=True)
