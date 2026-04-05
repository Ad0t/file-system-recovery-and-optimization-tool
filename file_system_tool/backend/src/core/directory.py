"""
directory.py - Directory tree module.

Provides DirectoryNode and DirectoryTree classes for managing
the hierarchical directory structure of the simulated file system.
Supports absolute and relative path resolution, recursive operations,
and tree visualization.

Dependencies:
    - re (stdlib): Name validation.
    - datetime (stdlib): Creation timestamps.
    - Inode (type-checking only): Avoids circular import.

Usage::

    from src.core.directory import DirectoryTree
    from src.core.inode import Inode

    tree = DirectoryTree()
    tree.create_directory('/home/user/docs')    # mkdir -p
    inode = Inode(inode_number=1, file_type='file')
    tree.create_file('/home/user/docs/notes.txt', inode)
    tree.change_directory('/home/user')
    print(tree.get_tree_structure())
"""

import logging
import re
from datetime import datetime
from typing import Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .inode import Inode  # avoid circular import at runtime

logger = logging.getLogger(__name__)

# Characters allowed in file / directory names (letters, digits, . - _ space)
_VALID_NAME_RE = re.compile(r'^[\w.\- ]+$')


# ===================================================================== #
#  DirectoryNode
# ===================================================================== #

class DirectoryNode:
    """
    A single node in the directory tree (either a file or a directory).

    Attributes:
        name (str): Name of this file or directory.
        is_directory (bool): True for directories, False for files.
        inode (Inode | None): Associated inode (may be None for dirs
            in a simple implementation).
        children (dict[str, DirectoryNode]): Child nodes (only meaningful
            when ``is_directory`` is True).
        parent (DirectoryNode | None): Parent directory (None for root).
        created_time (datetime): When this node was created.
    """

    def __init__(self, name: str, is_directory: bool = True,
                 parent: Optional["DirectoryNode"] = None):
        """
        Initialize a directory node.

        Args:
            name (str): Node name.
            is_directory (bool): True for directory, False for file.
            parent (DirectoryNode | None): Parent directory node.
        """
        self.name: str = name
        self.is_directory: bool = is_directory
        self.inode: Optional["Inode"] = None
        self.children: Dict[str, "DirectoryNode"] = {} if is_directory else {}
        self.parent: Optional["DirectoryNode"] = parent
        self.created_time: datetime = datetime.now()

    # ------------------------------------------------------------------ #
    #  Child management
    # ------------------------------------------------------------------ #

    def add_child(self, name: str, node: "DirectoryNode") -> bool:
        """
        Add a child node to this directory.

        Args:
            name (str): Name for the child entry.
            node (DirectoryNode): The child node to add.

        Returns:
            bool: True on success. False if this node is not a directory
                or if *name* already exists.
        """
        if not self.is_directory:
            logger.warning(
                "Cannot add child '%s' to non-directory '%s'",
                name, self.name,
            )
            return False
        if name in self.children:
            logger.warning(
                "Child '%s' already exists in '%s'", name, self.name
            )
            return False

        node.parent = self
        self.children[name] = node
        return True

    def remove_child(self, name: str) -> bool:
        """
        Remove a child node by name.

        Args:
            name (str): Name of the child to remove.

        Returns:
            bool: True if removed, False if not found.
        """
        if name not in self.children:
            return False
        removed = self.children.pop(name)
        removed.parent = None
        return True

    def get_child(self, name: str) -> Optional["DirectoryNode"]:
        """
        Look up a child by name.

        Args:
            name (str): Child name.

        Returns:
            DirectoryNode | None: The child, or None if not found.
        """
        return self.children.get(name)

    # ------------------------------------------------------------------ #
    #  Path helpers
    # ------------------------------------------------------------------ #

    def get_full_path(self) -> str:
        """
        Build the full absolute path from root to this node.

        Returns:
            str: Path string, e.g. ``'/home/user/file.txt'``.
        """
        parts: List[str] = []
        current: Optional["DirectoryNode"] = self
        while current is not None and current.parent is not None:
            parts.append(current.name)
            current = current.parent
        if not parts:
            return "/"
        return "/" + "/".join(reversed(parts))

    # ------------------------------------------------------------------ #
    #  Listing
    # ------------------------------------------------------------------ #

    def list_children(self) -> List[str]:
        """
        Return an alphabetically sorted list of child names.

        Returns:
            list[str]: Sorted child names (empty list for files).
        """
        return sorted(self.children.keys())

    # ------------------------------------------------------------------ #
    #  Dunder
    # ------------------------------------------------------------------ #

    def __repr__(self) -> str:
        kind = "DIR" if self.is_directory else "FILE"
        return f"DirectoryNode(name='{self.name}', type={kind})"


# ===================================================================== #
#  DirectoryTree
# ===================================================================== #

class DirectoryTree:
    """
    Manages the full directory hierarchy for the simulated file system.

    Provides POSIX-like operations: ``mkdir -p``, ``cd``, ``ls``,
    path resolution with ``.`` / ``..``, and a ``tree``-style
    visualisation.

    Attributes:
        root (DirectoryNode): The root directory (``/``).
        current_directory (DirectoryNode): The current working directory.
        inode_map (dict[int, DirectoryNode]): Lookup from inode number
            to the node that owns it.
    """

    def __init__(self):
        """Create the root directory and set it as the current directory."""
        self.root = DirectoryNode(name="/", is_directory=True)
        self.current_directory: DirectoryNode = self.root
        self.inode_map: Dict[int, DirectoryNode] = {}

    # ------------------------------------------------------------------ #
    #  Path utilities (internal)
    # ------------------------------------------------------------------ #

    @staticmethod
    def _validate_name(name: str) -> bool:
        """Return True if *name* is a legal file/directory name."""
        if not name or name in (".", ".."):
            return True  # special names handled elsewhere
        return bool(_VALID_NAME_RE.match(name))

    def _split_path(self, path: str):
        """
        Split a path string into individual components.

        Returns:
            tuple[bool, list[str]]: (is_absolute, components).
        """
        is_absolute = path.startswith("/")
        parts = [p for p in path.split("/") if p]
        return is_absolute, parts

    # ------------------------------------------------------------------ #
    #  Path resolution
    # ------------------------------------------------------------------ #

    def resolve_path(self, path: str) -> Optional[DirectoryNode]:
        """
        Convert a path string to a DirectoryNode.

        Handles:
          - Absolute paths (``/home/user``).
          - Relative paths (``docs/file.txt``).
          - Special components: ``.`` (current dir) and ``..`` (parent dir).

        Args:
            path (str): The path to resolve.

        Returns:
            DirectoryNode | None: The node, or None if the path does
                not exist.
        """
        if not path:
            return None

        is_absolute, parts = self._split_path(path)
        current = self.root if is_absolute else self.current_directory

        for part in parts:
            if part == ".":
                continue
            elif part == "..":
                current = current.parent if current.parent else current
            else:
                child = current.get_child(part)
                if child is None:
                    return None
                current = child

        return current

    # ------------------------------------------------------------------ #
    #  Directory operations
    # ------------------------------------------------------------------ #

    def create_directory(self, path: str,
                         inode: Optional["Inode"] = None) -> bool:
        """
        Create a directory at *path*, including intermediate parents.

        Behaves like ``mkdir -p``.

        Args:
            path (str): Absolute or relative path.
            inode (Inode | None): Optional inode to associate.

        Returns:
            bool: True if the directory was created (or already exists),
                False on validation error.

        Example::

            >>> tree = DirectoryTree()
            >>> tree.create_directory('/home/user/docs')
            True
            >>> tree.resolve_path('/home/user/docs') is not None
            True
        """
        is_absolute, parts = self._split_path(path)
        if not parts:
            return False

        current = self.root if is_absolute else self.current_directory

        for part in parts:
            if part == ".":
                continue
            elif part == "..":
                current = current.parent if current.parent else current
                continue

            if not self._validate_name(part):
                logger.warning("Invalid directory name: '%s'", part)
                return False

            child = current.get_child(part)
            if child is not None:
                if not child.is_directory:
                    logger.warning(
                        "'%s' exists as a file, cannot create directory", part
                    )
                    return False
                current = child
            else:
                new_dir = DirectoryNode(name=part, is_directory=True)
                current.add_child(part, new_dir)
                current = new_dir

        # Attach inode to the final directory
        if inode is not None:
            current.inode = inode
            self.inode_map[inode.inode_number] = current

        logger.debug("Directory created: %s", current.get_full_path())
        return True

    def create_file(self, path: str, inode: "Inode") -> bool:
        """
        Create a file at *path*.

        The parent directory must already exist. The file must have an
        associated inode.

        Args:
            path (str): Absolute or relative path to the new file.
            inode (Inode): The inode for this file.

        Returns:
            bool: True on success, False if the file already exists or
                the parent directory is missing.
        """
        is_absolute, parts = self._split_path(path)
        if not parts:
            return False

        file_name = parts[-1]
        parent_parts = parts[:-1]

        if not self._validate_name(file_name):
            logger.warning("Invalid file name: '%s'", file_name)
            return False

        # Resolve parent directory
        parent = self.root if is_absolute else self.current_directory
        for part in parent_parts:
            if part == ".":
                continue
            elif part == "..":
                parent = parent.parent if parent.parent else parent
            else:
                child = parent.get_child(part)
                if child is None or not child.is_directory:
                    logger.warning(
                        "Parent directory '%s' does not exist", part
                    )
                    return False
                parent = child

        # Check if file already exists
        if parent.get_child(file_name) is not None:
            logger.warning(
                "File '%s' already exists in '%s'",
                file_name, parent.get_full_path(),
            )
            return False

        file_node = DirectoryNode(name=file_name, is_directory=False)
        file_node.inode = inode
        parent.add_child(file_name, file_node)
        self.inode_map[inode.inode_number] = file_node

        logger.debug("File created: %s", file_node.get_full_path())
        return True

    def delete(self, path: str, recursive: bool = False) -> bool:
        """
        Delete a file or directory at *path*.

        Args:
            path (str): Path to the target.
            recursive (bool): If True, delete non-empty directories
                and all their contents.

        Returns:
            bool: True on success, False if the path does not exist,
                is the root, or the directory is non-empty without
                *recursive*.
        """
        node = self.resolve_path(path)
        if node is None:
            logger.warning("delete: path '%s' not found", path)
            return False
        if node is self.root:
            logger.warning("delete: cannot delete root directory")
            return False

        if node.is_directory and node.children and not recursive:
            logger.warning(
                "delete: directory '%s' is not empty (use recursive=True)",
                node.get_full_path(),
            )
            return False

        # Recursively remove from inode_map
        self._unregister_inodes(node)

        # Remove from parent
        parent = node.parent
        if parent:
            parent.remove_child(node.name)

        # If we just deleted the current directory, reset to root
        if self.current_directory is node:
            self.current_directory = self.root

        logger.debug("Deleted: %s", path)
        return True

    def _unregister_inodes(self, node: DirectoryNode) -> None:
        """Recursively remove a node (and its children) from inode_map."""
        if node.inode is not None:
            self.inode_map.pop(node.inode.inode_number, None)
        if node.is_directory:
            for child in node.children.values():
                self._unregister_inodes(child)

    # ------------------------------------------------------------------ #
    #  Navigation
    # ------------------------------------------------------------------ #

    def change_directory(self, path: str) -> bool:
        """
        Change the current working directory.

        Args:
            path (str): Path to the target directory.

        Returns:
            bool: True if successful, False if the path is invalid
                or is not a directory.
        """
        node = self.resolve_path(path)
        if node is None:
            logger.warning("cd: path '%s' not found", path)
            return False
        if not node.is_directory:
            logger.warning("cd: '%s' is not a directory", path)
            return False

        self.current_directory = node
        return True

    def get_current_path(self) -> str:
        """
        Return the absolute path of the current working directory.

        Returns:
            str: Current directory path.
        """
        return self.current_directory.get_full_path()

    # ------------------------------------------------------------------ #
    #  Listing & lookup
    # ------------------------------------------------------------------ #

    def list_directory(self, path: str = ".") -> List[Dict]:
        """
        List the contents of a directory.

        Args:
            path (str): Path to the directory to list (default: current).

        Returns:
            list[dict]: Each dict contains:
                - name (str)
                - is_directory (bool)
                - size (int): File size from inode, or 0.
                - modified_time (str): ISO-formatted timestamp, or ''.
                Returns an empty list if the path is invalid.
        """
        node = self.resolve_path(path)
        if node is None or not node.is_directory:
            return []

        entries: List[Dict] = []
        for name in sorted(node.children.keys()):
            child = node.children[name]
            size = 0
            modified = ""
            if child.inode is not None:
                size = child.inode.size_bytes
                modified = child.inode.modified_time.isoformat()
            entries.append({
                "name": name,
                "is_directory": child.is_directory,
                "size": size,
                "modified_time": modified,
            })
        return entries

    def find_by_inode(self, inode_number: int) -> Optional[DirectoryNode]:
        """
        Look up a directory node by its inode number.

        Args:
            inode_number (int): The inode number to search for.

        Returns:
            DirectoryNode | None
        """
        return self.inode_map.get(inode_number)

    # ------------------------------------------------------------------ #
    #  Tree visualisation
    # ------------------------------------------------------------------ #

    def get_tree_structure(self, node: Optional[DirectoryNode] = None,
                           prefix: str = "") -> str:
        """
        Generate a ``tree``-style visualisation of the directory hierarchy.

        Example output::

            /
            ├── home/
            │   ├── user/
            │   │   └── file.txt
            └── var/

        Args:
            node (DirectoryNode | None): Starting node (default: root).
            prefix (str): Internal indentation prefix (used by recursion).

        Returns:
            str: Multi-line tree string.
        """
        if node is None:
            node = self.root
            lines = [node.name]
        else:
            lines = []

        children = sorted(node.children.keys())
        for i, name in enumerate(children):
            child = node.children[name]
            is_last = (i == len(children) - 1)
            connector = "└── " if is_last else "├── "
            suffix = "/" if child.is_directory else ""
            lines.append(f"{prefix}{connector}{name}{suffix}")

            if child.is_directory and child.children:
                extension = "    " if is_last else "│   "
                subtree = self.get_tree_structure(child, prefix + extension)
                lines.append(subtree)

        return "\n".join(lines)

    # ------------------------------------------------------------------ #
    #  Dunder
    # ------------------------------------------------------------------ #

    def __repr__(self) -> str:
        return (
            f"DirectoryTree(cwd='{self.get_current_path()}', "
            f"inodes={len(self.inode_map)})"
        )
