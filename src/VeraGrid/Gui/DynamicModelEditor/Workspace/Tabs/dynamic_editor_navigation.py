# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from typing import TYPE_CHECKING, List

from VeraGridEngine.Utils.Symbolic.block import Block

if TYPE_CHECKING:
    from VeraGrid.Gui.DynamicModelEditor.Workspace.Tabs.dynamic_editor_tab import DynamicEditorDocument
else:
    pass


class DynamicEditorNavigation:
    """
    Domain object that tracks the current position inside a block hierarchy
    owned by a :class:`DynamicEditorDocument`.

    The navigation owns the document reference and exposes the working-tree
    root through a property so that callers never need to reach into the
    document directly.
    """

    __slots__ = ("_document", "_path")

    def __init__(self, document: DynamicEditorDocument) -> None:
        """
        :param document: The editing document whose working tree is navigated.
        :return: None.
        """
        self._document: DynamicEditorDocument = document
        self._path: List[Block] = list((document.working_root_block,))

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def document(self) -> DynamicEditorDocument:
        """
        :return: The document backing this navigation.
        """
        return self._document

    @property
    def root_block(self) -> Block:
        """
        :return: The root block of the working tree.
        """
        return self._document.working_root_block

    @property
    def current_block(self) -> Block:
        """
        :return: The block currently being edited.
        """
        return self._path[-1]

    # ------------------------------------------------------------------
    # Navigation operations
    # ------------------------------------------------------------------

    def open_child(self, block: Block) -> None:
        """
        Navigate into a direct child of the current block.

        :param block: A child of :pyattr:`current_block`.
        :return: None.
        """
        self._path.append(block)

    def reset(self) -> None:
        """
        Reset navigation to the current working root owned by the document.

        :return: None.
        """
        self._path = list((self._document.working_root_block,))

    def go_to(self, block: Block) -> None:
        """
        Jump to any block in the current path.

        The target *must* already be in the path (i.e. an ancestor of the
        current block or the current block itself).

        :param block: Target block to navigate to.
        :raises ValueError: If *block* is not part of the current path.
        :return: None.
        """
        for index, ancestor in enumerate(self._path):
            if ancestor.uid == block.uid:
                self._path = self._path[: index + 1]
                return
            else:
                pass
        raise ValueError(
            f"Block '{block.name}' (uid={block.uid}) is not in the current path."
        )

    def breadcrumb_path(self) -> List[Block]:
        """
        Return the full path from root to the current block.

        The returned list always starts with the root block and ends with
        :pyattr:`current_block`.  It is a *copy* so callers cannot mutate
        the internal state.

        :return: Ordered list of ancestor blocks including root and current.
        """
        return list(self._path)

    def depth(self) -> int:
        """
        Return the current depth (0 = root).

        :return: Number of navigation steps from the root.
        """
        return len(self._path) - 1

    def is_root(self) -> bool:
        """
        Return whether the current block is the root block.

        :return: ``True`` when at root level.
        """
        return len(self._path) == 1
