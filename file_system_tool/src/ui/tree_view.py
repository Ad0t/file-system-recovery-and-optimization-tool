"""
tree_view.py - TreeView component for the File System Simulator GUI.

Provides a rich, interactive tree widget that visualises the simulated
directory hierarchy.  Supports navigation, right-click context menus,
file/directory creation and deletion, property inspection, and search.

Dependencies:
    - tkinter             : GUI framework
    - src.core.directory  : DirectoryTree / DirectoryNode
    - src.core.inode      : Inode (for file creation)

Usage::

    import tkinter as tk
    from tkinter import ttk
    from src.core.directory import DirectoryTree
    from src.ui.tree_view import TreeView

    root = tk.Tk()
    frame = ttk.Frame(root)
    frame.pack(fill="both", expand=True)
    tree_view = TreeView(frame, DirectoryTree())
    root.mainloop()
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import logging
from datetime import datetime
from typing import List, Optional, Callable, Dict, Any

from src.core.directory import DirectoryTree, DirectoryNode
from src.core.inode import Inode

logger = logging.getLogger(__name__)


# ===================================================================== #
#  Color / Font constants  (mirrors main_window.py palette)
# ===================================================================== #

COLORS = {
    "bg_dark":        "#1a1a2e",
    "bg_panel":       "#16213e",
    "bg_card":        "#0f3460",
    "accent_primary": "#e94560",
    "accent_green":   "#00d2a0",
    "accent_yellow":  "#f5c542",
    "accent_blue":    "#4fc3f7",
    "accent_orange":  "#ff8c42",
    "text_primary":   "#e0e0e0",
    "text_secondary": "#a0a0b0",
    "text_header":    "#ffffff",
    "border":         "#2a2a4a",
    "highlight":      "#3a3a6a",
}

FONT_BODY    = ("Segoe UI", 10)
FONT_SMALL   = ("Segoe UI", 9)
FONT_SUBHEAD = ("Segoe UI", 11, "bold")
FONT_MONO    = ("Consolas", 10)
FONT_MONO_SM = ("Consolas", 9)

# Visual icons
ICON_DIR      = "📁"
ICON_DIR_OPEN = "📂"
ICON_FILE     = "📄"
ICON_ROOT     = "🖥️"


# ===================================================================== #
#  TreeView Component
# ===================================================================== #

class TreeView:
    """
    Interactive tree-view component backed by a DirectoryTree.

    Attributes:
        parent_frame (ttk.Frame): The container this widget lives in.
        directory_tree (DirectoryTree): The underlying directory model.
        tree_widget (ttk.Treeview): The Tkinter Treeview widget.
        selected_path (str | None): Currently selected absolute path.
        context_menu (tk.Menu): Right-click popup menu.
    """

    # ----------------------------------------------------------------- #
    #  Construction
    # ----------------------------------------------------------------- #

    def __init__(
        self,
        parent_frame: ttk.Frame,
        directory_tree: DirectoryTree,
        *,
        on_select_callback: Optional[Callable[[str], None]] = None,
        inode_counter_start: int = 100,
        fat: Any = None,
        fsm: Any = None,
        disk: Any = None,
    ):
        """
        Initialise the tree-view component.

        Args:
            parent_frame: Parent ttk.Frame to embed into.
            directory_tree: DirectoryTree model to visualise.
            on_select_callback: Optional callback invoked with the
                selected path whenever the selection changes.
            inode_counter_start: Starting inode number for newly created
                files via the UI.
            fat: Optional FileAllocationTable reference for showing
                block allocation in properties.
            fsm: Optional FreeSpaceManager reference.
            disk: Optional Disk reference for block-size info.
        """
        self.parent_frame = parent_frame
        self.directory_tree = directory_tree
        self.selected_path: Optional[str] = None
        self._on_select_callback = on_select_callback
        self._inode_counter = inode_counter_start

        # Optional references for enriched properties display
        self._fat = fat
        self._fsm = fsm
        self._disk = disk

        # Mapping: tree-widget item-id → DirectoryNode
        self._item_to_node: Dict[str, DirectoryNode] = {}

        # Search state
        self._search_matches: List[str] = []

        # ---------- Build UI ----------
        self._build_toolbar()
        self._build_treeview()
        self._create_context_menu()
        self._create_tooltip()

        # Populate and select root
        self.refresh()

    # ----------------------------------------------------------------- #
    #  Toolbar (search bar + refresh button)
    # ----------------------------------------------------------------- #

    def _build_toolbar(self) -> None:
        """Build a search / toolbar strip above the tree."""
        toolbar = tk.Frame(self.parent_frame, bg=COLORS["bg_dark"])
        toolbar.pack(fill="x", padx=2, pady=(4, 0))

        # Search
        tk.Label(toolbar, text="🔍", bg=COLORS["bg_dark"],
                 fg=COLORS["text_secondary"],
                 font=FONT_BODY).pack(side="left", padx=(4, 0))

        self._sv_search = tk.StringVar()
        self._ent_search = tk.Entry(
            toolbar, textvariable=self._sv_search,
            bg=COLORS["bg_panel"], fg=COLORS["text_primary"],
            insertbackground=COLORS["text_primary"],
            font=FONT_SMALL, width=20, relief="flat",
        )
        self._ent_search.pack(side="left", padx=4, fill="x", expand=True)
        self._ent_search.bind("<Return>", lambda _: self._do_search())

        tk.Button(
            toolbar, text="Search", font=FONT_SMALL,
            bg=COLORS["bg_card"], fg=COLORS["accent_blue"],
            relief="flat", cursor="hand2",
            command=self._do_search,
        ).pack(side="left", padx=2)

        tk.Button(
            toolbar, text="⟳", font=FONT_BODY,
            bg=COLORS["bg_card"], fg=COLORS["accent_green"],
            relief="flat", cursor="hand2", width=3,
            command=self.refresh,
        ).pack(side="right", padx=4)

    # ----------------------------------------------------------------- #
    #  Treeview widget
    # ----------------------------------------------------------------- #

    def _build_treeview(self) -> None:
        """Create the ttk.Treeview with four data columns + scrollbars."""
        container = tk.Frame(self.parent_frame, bg=COLORS["bg_dark"])
        container.pack(fill="both", expand=True, padx=2, pady=2)

        columns = ("type", "size", "modified")
        self.tree_widget = ttk.Treeview(
            container,
            columns=columns,
            show="tree headings",
            selectmode="browse",
        )

        # Column configuration
        self.tree_widget.heading("#0", text="Name", anchor="w")
        self.tree_widget.heading("type", text="Type", anchor="center")
        self.tree_widget.heading("size", text="Size", anchor="e")
        self.tree_widget.heading("modified", text="Modified", anchor="center")

        self.tree_widget.column("#0", width=260, minwidth=150, stretch=True)
        self.tree_widget.column("type", width=80, minwidth=60, anchor="center")
        self.tree_widget.column("size", width=90, minwidth=60, anchor="e")
        self.tree_widget.column("modified", width=140, minwidth=100, anchor="center")

        # Scrollbars
        vsb = ttk.Scrollbar(container, orient="vertical",
                             command=self.tree_widget.yview)
        hsb = ttk.Scrollbar(container, orient="horizontal",
                             command=self.tree_widget.xview)
        self.tree_widget.configure(yscrollcommand=vsb.set,
                                    xscrollcommand=hsb.set)

        # Grid layout
        self.tree_widget.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        container.rowconfigure(0, weight=1)
        container.columnconfigure(0, weight=1)

        # Tag-based colouring
        self.tree_widget.tag_configure(
            "directory", foreground=COLORS["accent_blue"])
        self.tree_widget.tag_configure(
            "file", foreground=COLORS["text_primary"])
        self.tree_widget.tag_configure(
            "search_match", background=COLORS["highlight"])

        # Event bindings
        self.tree_widget.bind("<<TreeviewSelect>>", self.on_select)
        self.tree_widget.bind("<Double-1>", self.on_double_click)
        self.tree_widget.bind("<Button-3>", self.on_right_click)
        self.tree_widget.bind("<Motion>", self._on_motion)

    # ----------------------------------------------------------------- #
    #  Context menu
    # ----------------------------------------------------------------- #

    def _create_context_menu(self) -> None:
        """Build the right-click popup menu."""
        self.context_menu = tk.Menu(
            self.parent_frame, tearoff=0,
            bg=COLORS["bg_panel"], fg=COLORS["text_primary"],
            activebackground=COLORS["bg_card"],
            activeforeground=COLORS["text_header"],
            font=FONT_SMALL,
        )

        # Items are shown / hidden dynamically in on_right_click()
        self.context_menu.add_command(
            label=f"{ICON_FILE}  Create File",
            command=self.create_file_dialog)
        self.context_menu.add_command(
            label=f"{ICON_DIR}  Create Directory",
            command=self.create_directory_dialog)
        self.context_menu.add_separator()
        self.context_menu.add_command(
            label="🗑️  Delete",
            command=self.delete_item)
        self.context_menu.add_separator()
        self.context_menu.add_command(
            label="ℹ️  Properties",
            command=lambda: self.show_properties(self.selected_path))
        self.context_menu.add_command(
            label="👁️  View Content",
            command=self._view_file_content)

    # ----------------------------------------------------------------- #
    #  Tooltip (hover info)
    # ----------------------------------------------------------------- #

    def _create_tooltip(self) -> None:
        """Create a floating tooltip label (hidden by default)."""
        self._tooltip = tk.Toplevel(self.parent_frame)
        self._tooltip.withdraw()
        self._tooltip.overrideredirect(True)
        self._tooltip_label = tk.Label(
            self._tooltip,
            bg=COLORS["bg_card"], fg=COLORS["text_primary"],
            font=FONT_SMALL, justify="left",
            padx=8, pady=4, wraplength=320,
        )
        self._tooltip_label.pack()

    def _on_motion(self, event: tk.Event) -> None:
        """Show a tooltip with extra info when hovering over a tree item."""
        item_id = self.tree_widget.identify_row(event.y)
        if not item_id or item_id not in self._item_to_node:
            self._tooltip.withdraw()
            return

        node = self._item_to_node[item_id]
        path = node.get_full_path()
        tip_lines = [f"Path: {path}"]
        if node.inode:
            tip_lines.append(f"Inode: #{node.inode.inode_number}")
            tip_lines.append(f"Permissions: {node.inode.permissions}")
            tip_lines.append(f"Owner: {node.inode.owner}")
        tip_lines.append(f"Created: {self._format_date(node.created_time)}")
        tip_text = "\n".join(tip_lines)

        self._tooltip_label.configure(text=tip_text)
        x = event.x_root + 16
        y = event.y_root + 12
        self._tooltip.geometry(f"+{x}+{y}")
        self._tooltip.deiconify()

    # ================================================================= #
    #  Tree population
    # ================================================================= #

    def populate_tree(
        self,
        parent_item: str = "",
        parent_node: Optional[DirectoryNode] = None,
    ) -> None:
        """
        Recursively populate the treeview widget from the directory model.

        Args:
            parent_item: Treeview item-id for the visual parent.
            parent_node: DirectoryNode to start from (root if None).
        """
        if parent_node is None:
            parent_node = self.directory_tree.root

        # Sort children: directories first, then files, both alphabetical
        children = sorted(
            parent_node.children.values(),
            key=lambda n: (not n.is_directory, n.name.lower()),
        )

        for child in children:
            icon = ICON_DIR if child.is_directory else ICON_FILE
            node_type = "Directory" if child.is_directory else "File"
            size_str = ""
            modified_str = ""
            tag = "directory" if child.is_directory else "file"

            if child.inode is not None:
                size_str = self._format_size(child.inode.size_bytes)
                modified_str = self._format_date(child.inode.modified_time)
            elif child.is_directory:
                size_str = f"{len(child.children)} items"
                modified_str = self._format_date(child.created_time)
            else:
                modified_str = self._format_date(child.created_time)

            item_id = self.tree_widget.insert(
                parent_item, "end",
                text=f" {icon}  {child.name}",
                values=(node_type, size_str, modified_str),
                open=False,
                tags=(tag,),
            )
            self._item_to_node[item_id] = child

            # Recurse into directories
            if child.is_directory and child.children:
                self.populate_tree(parent_item=item_id, parent_node=child)

    def refresh(self) -> None:
        """Clear and rebuild the tree, restoring the previous selection."""
        prev_path = self.selected_path

        # Clear existing items
        self.tree_widget.delete(*self.tree_widget.get_children())
        self._item_to_node.clear()

        # Insert root node
        root = self.directory_tree.root
        root_id = self.tree_widget.insert(
            "", "end",
            text=f" {ICON_ROOT}  / (root)",
            values=("Root", f"{len(root.children)} items",
                    self._format_date(root.created_time)),
            open=True,
            tags=("directory",),
        )
        self._item_to_node[root_id] = root

        # Populate children
        self.populate_tree(parent_item=root_id, parent_node=root)

        # Try to restore selection
        if prev_path:
            self.expand_to_path(prev_path)

    # ================================================================= #
    #  Event handlers
    # ================================================================= #

    def on_select(self, event: tk.Event) -> None:
        """Handle item selection in the tree."""
        selection = self.tree_widget.selection()
        if not selection:
            self.selected_path = None
            return

        item_id = selection[0]
        node = self._item_to_node.get(item_id)
        if node:
            self.selected_path = node.get_full_path()
            if self._on_select_callback:
                self._on_select_callback(self.selected_path)

    def on_double_click(self, event: tk.Event) -> None:
        """Handle double-click: toggle directory or show file properties."""
        item_id = self.tree_widget.identify_row(event.y)
        if not item_id:
            return

        node = self._item_to_node.get(item_id)
        if node is None:
            return

        if node.is_directory:
            # Toggle open/close
            is_open = self.tree_widget.item(item_id, "open")
            self.tree_widget.item(item_id, open=not is_open)
        else:
            # Show properties for files
            self.show_properties(node.get_full_path())

    def on_right_click(self, event: tk.Event) -> None:
        """Show the context menu, adjusting options for item type."""
        # Select the item under cursor
        item_id = self.tree_widget.identify_row(event.y)
        if item_id:
            self.tree_widget.selection_set(item_id)
            self.tree_widget.focus(item_id)

        node = self._item_to_node.get(item_id) if item_id else None

        # Show / hide menu entries based on node type
        #  0 = Create File, 1 = Create Dir, 2 = separator,
        #  3 = Delete, 4 = separator, 5 = Properties, 6 = View Content
        is_dir = node.is_directory if node else True
        is_root = (node is self.directory_tree.root) if node else False

        self.context_menu.entryconfigure(0, state="normal" if is_dir else "disabled")
        self.context_menu.entryconfigure(1, state="normal" if is_dir else "disabled")
        self.context_menu.entryconfigure(3, state="disabled" if is_root else "normal")
        self.context_menu.entryconfigure(6, state="normal" if not is_dir else "disabled")

        try:
            self.context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.context_menu.grab_release()

    # ================================================================= #
    #  File / directory creation dialogs
    # ================================================================= #

    def create_file_dialog(self) -> None:
        """Open a dialog to create a new file in the selected directory."""
        parent_path = self.selected_path or "/"
        parent_node = self.directory_tree.resolve_path(parent_path)
        if parent_node is None or not parent_node.is_directory:
            messagebox.showwarning("Invalid Target",
                                   "Please select a directory first.")
            return

        # Build a small dialog
        dialog = tk.Toplevel(self.parent_frame)
        dialog.title("Create File")
        dialog.geometry("360x200")
        dialog.configure(bg=COLORS["bg_dark"])
        dialog.resizable(False, False)
        dialog.transient(self.parent_frame.winfo_toplevel())
        dialog.grab_set()

        tk.Label(dialog, text="Create New File",
                 bg=COLORS["bg_dark"], fg=COLORS["text_header"],
                 font=FONT_SUBHEAD).pack(pady=(12, 6))

        form = tk.Frame(dialog, bg=COLORS["bg_dark"])
        form.pack(padx=20, fill="x")

        tk.Label(form, text="Filename:", bg=COLORS["bg_dark"],
                 fg=COLORS["text_primary"], font=FONT_BODY
                 ).grid(row=0, column=0, sticky="w", pady=4)
        ent_name = tk.Entry(form, bg=COLORS["bg_panel"],
                            fg=COLORS["text_primary"],
                            insertbackground=COLORS["text_primary"],
                            font=FONT_BODY, width=24)
        ent_name.grid(row=0, column=1, padx=6, pady=4)
        ent_name.focus_set()

        tk.Label(form, text="Size (bytes):", bg=COLORS["bg_dark"],
                 fg=COLORS["text_primary"], font=FONT_BODY
                 ).grid(row=1, column=0, sticky="w", pady=4)
        ent_size = tk.Entry(form, bg=COLORS["bg_panel"],
                            fg=COLORS["text_primary"],
                            insertbackground=COLORS["text_primary"],
                            font=FONT_BODY, width=24)
        ent_size.insert(0, "1024")
        ent_size.grid(row=1, column=1, padx=6, pady=4)

        def _do_create():
            name = ent_name.get().strip()
            if not name:
                messagebox.showwarning("Missing Name",
                                       "Please enter a filename.",
                                       parent=dialog)
                return
            try:
                size = int(ent_size.get())
            except ValueError:
                messagebox.showwarning("Invalid Size",
                                       "Size must be a positive integer.",
                                       parent=dialog)
                return

            inode = Inode(
                inode_number=self._inode_counter,
                file_type="file",
                size=max(size, 0),
            )
            self._inode_counter += 1

            full_path = parent_path.rstrip("/") + "/" + name
            if self.directory_tree.create_file(full_path, inode):
                self.refresh()
                dialog.destroy()
            else:
                messagebox.showerror(
                    "Creation Failed",
                    f"Could not create '{full_path}'.\n"
                    "The name may already exist or be invalid.",
                    parent=dialog,
                )

        btn_bar = tk.Frame(dialog, bg=COLORS["bg_dark"])
        btn_bar.pack(pady=12)
        tk.Button(btn_bar, text="Create", bg=COLORS["accent_green"],
                  fg="#000", font=FONT_BODY, width=10, relief="flat",
                  cursor="hand2", command=_do_create).pack(side="left", padx=6)
        tk.Button(btn_bar, text="Cancel", bg=COLORS["bg_card"],
                  fg=COLORS["text_primary"], font=FONT_BODY,
                  width=10, relief="flat", cursor="hand2",
                  command=dialog.destroy).pack(side="left", padx=6)

    def create_directory_dialog(self) -> None:
        """Open a dialog to create a new sub-directory."""
        parent_path = self.selected_path or "/"
        parent_node = self.directory_tree.resolve_path(parent_path)
        if parent_node is None or not parent_node.is_directory:
            messagebox.showwarning("Invalid Target",
                                   "Please select a directory first.")
            return

        dialog = tk.Toplevel(self.parent_frame)
        dialog.title("Create Directory")
        dialog.geometry("340x150")
        dialog.configure(bg=COLORS["bg_dark"])
        dialog.resizable(False, False)
        dialog.transient(self.parent_frame.winfo_toplevel())
        dialog.grab_set()

        tk.Label(dialog, text="Create New Directory",
                 bg=COLORS["bg_dark"], fg=COLORS["text_header"],
                 font=FONT_SUBHEAD).pack(pady=(12, 6))

        form = tk.Frame(dialog, bg=COLORS["bg_dark"])
        form.pack(padx=20, fill="x")

        tk.Label(form, text="Directory name:", bg=COLORS["bg_dark"],
                 fg=COLORS["text_primary"], font=FONT_BODY
                 ).grid(row=0, column=0, sticky="w", pady=4)
        ent_name = tk.Entry(form, bg=COLORS["bg_panel"],
                            fg=COLORS["text_primary"],
                            insertbackground=COLORS["text_primary"],
                            font=FONT_BODY, width=22)
        ent_name.grid(row=0, column=1, padx=6, pady=4)
        ent_name.focus_set()

        def _do_create():
            name = ent_name.get().strip()
            if not name:
                messagebox.showwarning("Missing Name",
                                       "Please enter a directory name.",
                                       parent=dialog)
                return

            full_path = parent_path.rstrip("/") + "/" + name
            if self.directory_tree.create_directory(full_path):
                self.refresh()
                dialog.destroy()
            else:
                messagebox.showerror(
                    "Creation Failed",
                    f"Could not create directory '{full_path}'.",
                    parent=dialog,
                )

        btn_bar = tk.Frame(dialog, bg=COLORS["bg_dark"])
        btn_bar.pack(pady=12)
        tk.Button(btn_bar, text="Create", bg=COLORS["accent_green"],
                  fg="#000", font=FONT_BODY, width=10, relief="flat",
                  cursor="hand2", command=_do_create).pack(side="left", padx=6)
        tk.Button(btn_bar, text="Cancel", bg=COLORS["bg_card"],
                  fg=COLORS["text_primary"], font=FONT_BODY,
                  width=10, relief="flat", cursor="hand2",
                  command=dialog.destroy).pack(side="left", padx=6)

    # ================================================================= #
    #  Deletion
    # ================================================================= #

    def delete_item(self) -> None:
        """Delete the currently selected file or directory."""
        if not self.selected_path or self.selected_path == "/":
            messagebox.showinfo("Cannot Delete",
                                "Select a file or directory to delete.\n"
                                "The root directory cannot be deleted.")
            return

        node = self.directory_tree.resolve_path(self.selected_path)
        if node is None:
            messagebox.showwarning("Not Found",
                                   f"'{self.selected_path}' not found.")
            return

        kind = "directory" if node.is_directory else "file"
        extra = ""
        if node.is_directory and node.children:
            extra = f"\n\nThis directory contains {len(node.children)} item(s).\nAll contents will be deleted."

        confirmed = messagebox.askyesno(
            "Confirm Deletion",
            f"Delete {kind} '{self.selected_path}'?{extra}",
        )
        if not confirmed:
            return

        success = self.directory_tree.delete(self.selected_path, recursive=True)
        if success:
            self.selected_path = None
            self.refresh()
        else:
            messagebox.showerror("Deletion Failed",
                                 f"Could not delete '{self.selected_path}'.")

    # ================================================================= #
    #  Properties dialog
    # ================================================================= #

    def show_properties(self, path: str) -> None:
        """
        Show a properties dialog for the item at *path*.

        Displays: path, type, size, timestamps, inode info, and
        block allocation (if FAT is available).
        """
        if not path:
            messagebox.showinfo("No Selection", "Select an item first.")
            return

        node = self.directory_tree.resolve_path(path)
        if node is None:
            messagebox.showwarning("Not Found", f"'{path}' not found.")
            return

        dialog = tk.Toplevel(self.parent_frame)
        dialog.title(f"Properties — {node.name}")
        dialog.geometry("440x450")
        dialog.configure(bg=COLORS["bg_dark"])
        dialog.resizable(False, True)
        dialog.transient(self.parent_frame.winfo_toplevel())

        # Header
        icon = ICON_DIR if node.is_directory else ICON_FILE
        tk.Label(dialog,
                 text=f"  {icon}  {node.name}",
                 bg=COLORS["bg_panel"], fg=COLORS["text_header"],
                 font=("Segoe UI", 14, "bold"),
                 anchor="w", padx=12, pady=10,
                 ).pack(fill="x")

        # Properties text
        txt = tk.Text(
            dialog, wrap="word",
            bg=COLORS["bg_dark"], fg=COLORS["text_primary"],
            font=FONT_MONO, relief="flat",
            insertbackground=COLORS["text_primary"],
            padx=14, pady=10,
        )
        txt.pack(fill="both", expand=True)

        props = []
        props.append(f"  Path:        {path}")
        props.append(f"  Type:        {'Directory' if node.is_directory else 'File'}")
        props.append(f"  Created:     {self._format_date(node.created_time)}")

        if node.inode:
            ino = node.inode
            props.append(f"  Inode #:     {ino.inode_number}")
            props.append(f"  Size:        {self._format_size(ino.size_bytes)} ({ino.size_bytes:,} bytes)")
            props.append(f"  Blocks:      {ino.block_count}")
            props.append(f"  Modified:    {self._format_date(ino.modified_time)}")
            props.append(f"  Accessed:    {self._format_date(ino.accessed_time)}")
            props.append(f"  Permissions: {ino.permissions}")
            props.append(f"  Owner:       {ino.owner}")
            props.append(f"  Link Count:  {ino.link_count}")

            # Block allocation from FAT
            if self._fat and hasattr(self._fat, "file_to_blocks"):
                alloc = self._fat.file_to_blocks.get(ino.inode_number)
                if alloc is not None:
                    props.append(f"")
                    props.append(f"  ── Block Allocation ──")
                    props.append(f"  Allocated:   {alloc}")
                    fragmented = self._fat.is_fragmented(ino.inode_number)
                    props.append(f"  Fragmented:  {'Yes' if fragmented else 'No'}")

            # Direct pointers
            if ino.direct_pointers:
                props.append(f"")
                props.append(f"  ── Inode Pointers ──")
                props.append(f"  Direct:      {ino.direct_pointers}")
                if ino.single_indirect is not None:
                    props.append(f"  Single Ind.: {ino.single_indirect}")
                if ino.double_indirect is not None:
                    props.append(f"  Double Ind.: {ino.double_indirect}")
        else:
            if node.is_directory:
                props.append(f"  Contents:    {len(node.children)} item(s)")
                props.append(f"  (No inode assigned)")

        txt.insert("1.0", "\n".join(props))
        txt.configure(state="disabled")

        tk.Button(dialog, text="Close", bg=COLORS["bg_card"],
                  fg=COLORS["text_primary"], font=FONT_BODY,
                  width=10, relief="flat", cursor="hand2",
                  command=dialog.destroy).pack(pady=10)

    # ================================================================= #
    #  View file content (placeholder visual)
    # ================================================================= #

    def _view_file_content(self) -> None:
        """Show simulated file content for the selected file."""
        if not self.selected_path:
            return

        node = self.directory_tree.resolve_path(self.selected_path)
        if node is None or node.is_directory:
            messagebox.showinfo("Info", "Select a file to view content.")
            return

        dialog = tk.Toplevel(self.parent_frame)
        dialog.title(f"Content — {node.name}")
        dialog.geometry("480x300")
        dialog.configure(bg=COLORS["bg_dark"])
        dialog.transient(self.parent_frame.winfo_toplevel())

        tk.Label(dialog, text=f"  {ICON_FILE}  {node.name}",
                 bg=COLORS["bg_panel"], fg=COLORS["text_header"],
                 font=FONT_SUBHEAD, anchor="w", padx=12, pady=8,
                 ).pack(fill="x")

        txt = tk.Text(dialog, wrap="word",
                      bg=COLORS["bg_dark"], fg=COLORS["accent_green"],
                      font=FONT_MONO, relief="flat", padx=10, pady=8)
        txt.pack(fill="both", expand=True)

        # Try to read content from disk via FAT if available
        content_lines = []
        if node.inode and self._fat and self._disk:
            blocks = self._fat.file_to_blocks.get(node.inode.inode_number, [])
            if isinstance(blocks, list):
                for b in blocks:
                    try:
                        data = self._disk.read_block(b)
                        if isinstance(data, bytes):
                            # Show hex + ascii preview
                            hex_str = data[:64].hex()
                            ascii_str = "".join(
                                chr(c) if 32 <= c < 127 else "."
                                for c in data[:64]
                            )
                            content_lines.append(
                                f"Block {b:4d}: {hex_str[:32]}...  |{ascii_str}|")
                        else:
                            content_lines.append(f"Block {b:4d}: <empty>")
                    except Exception:
                        content_lines.append(f"Block {b:4d}: <read error>")

        if not content_lines:
            content_lines = [
                "(Simulated file — no raw disk data available)",
                "",
                f"File: {node.name}",
                f"Size: {self._format_size(node.inode.size_bytes) if node.inode else 'unknown'}",
                f"Inode: #{node.inode.inode_number if node.inode else 'N/A'}",
            ]

        txt.insert("1.0", "\n".join(content_lines))
        txt.configure(state="disabled")

        tk.Button(dialog, text="Close", bg=COLORS["bg_card"],
                  fg=COLORS["text_primary"], font=FONT_BODY,
                  width=10, relief="flat", cursor="hand2",
                  command=dialog.destroy).pack(pady=8)

    # ================================================================= #
    #  Path / selection helpers
    # ================================================================= #

    def get_selected_path(self) -> Optional[str]:
        """Return the absolute path of the currently selected item."""
        return self.selected_path

    def expand_to_path(self, path: str) -> None:
        """
        Expand the tree to show a specific path and select it.

        Args:
            path: Absolute path to expand to (e.g. ``'/home/user/file.txt'``).
        """
        if not path or path == "/":
            # Select root
            children = self.tree_widget.get_children()
            if children:
                self.tree_widget.selection_set(children[0])
                self.tree_widget.see(children[0])
            return

        # Walk the tree items to find a matching node
        target_node = self.directory_tree.resolve_path(path)
        if target_node is None:
            return

        for item_id, node in self._item_to_node.items():
            if node is target_node:
                # Open all ancestors
                parent = self.tree_widget.parent(item_id)
                while parent:
                    self.tree_widget.item(parent, open=True)
                    parent = self.tree_widget.parent(parent)

                self.tree_widget.selection_set(item_id)
                self.tree_widget.see(item_id)
                self.tree_widget.focus(item_id)
                self.selected_path = path
                return

    # ================================================================= #
    #  Search
    # ================================================================= #

    def search_tree(self, search_term: str) -> List[str]:
        """
        Search for items whose name matches *search_term*.

        Args:
            search_term: Case-insensitive substring to match.

        Returns:
            List of absolute paths that matched.
        """
        if not search_term:
            return []

        term = search_term.lower()
        matches: List[str] = []

        # Clear previous highlights
        for item_id in self._item_to_node:
            tags = list(self.tree_widget.item(item_id, "tags"))
            if "search_match" in tags:
                tags.remove("search_match")
                self.tree_widget.item(item_id, tags=tags)

        # Search
        for item_id, node in self._item_to_node.items():
            if term in node.name.lower():
                path = node.get_full_path()
                matches.append(path)
                # Highlight
                tags = list(self.tree_widget.item(item_id, "tags"))
                tags.append("search_match")
                self.tree_widget.item(item_id, tags=tags)
                # Ensure visible
                parent = self.tree_widget.parent(item_id)
                while parent:
                    self.tree_widget.item(parent, open=True)
                    parent = self.tree_widget.parent(parent)

        self._search_matches = matches

        # Select first match
        if matches:
            self.expand_to_path(matches[0])

        return matches

    def _do_search(self) -> None:
        """Handle search from the toolbar entry."""
        term = self._sv_search.get().strip()
        matches = self.search_tree(term)
        if not term:
            return
        if matches:
            messagebox.showinfo(
                "Search Results",
                f"Found {len(matches)} match(es):\n\n"
                + "\n".join(matches[:15])
                + ("\n…" if len(matches) > 15 else ""),
            )
        else:
            messagebox.showinfo("Search Results",
                                f"No items matching '{term}'.")

    # ================================================================= #
    #  Internal helper: get full path for a tree item
    # ================================================================= #

    def _get_item_path(self, item_id: str) -> Optional[str]:
        """
        Get the full filesystem path for a treeview item.

        Args:
            item_id: ttk.Treeview item identifier.

        Returns:
            Absolute path string, or None if item is unknown.
        """
        node = self._item_to_node.get(item_id)
        if node:
            return node.get_full_path()
        return None

    # ================================================================= #
    #  Formatting helpers
    # ================================================================= #

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        """
        Format a byte count in human-readable form.

        Examples: ``"0 B"``, ``"4.0 KB"``, ``"1.5 MB"``, ``"2.3 GB"``
        """
        if size_bytes < 0:
            return "0 B"
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 ** 2:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 ** 3:
            return f"{size_bytes / (1024 ** 2):.1f} MB"
        else:
            return f"{size_bytes / (1024 ** 3):.1f} GB"

    @staticmethod
    def _format_date(timestamp: datetime) -> str:
        """
        Format a datetime for compact display.

        Example: ``"2024-03-15 14:30"``
        """
        if isinstance(timestamp, datetime):
            return timestamp.strftime("%Y-%m-%d %H:%M")
        return str(timestamp) if timestamp else ""
