# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from typing import List, Optional, Dict

from PySide6 import QtWidgets
from PySide6.QtCore import Signal

from VeraGridEngine.Devices.types import ALL_DEV_TYPES
from VeraGrid.Gui.DynamicModelEditor.Editor.dynamic_block_preparation import prepare_block_for_editing
from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Devices.Dynamic.fmu_template import FmuTemplate
from VeraGrid.Gui.DynamicModelEditor.Workspace.Tabs.dynamic_editor_breadcrumb import DynamicEditorBreadcrumb
from VeraGrid.Gui.DynamicModelEditor.Workspace.Tabs.dynamic_editor_navigation import DynamicEditorNavigation
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.enumerations import DynamicSimulationMode, BlockType, DynEditorGraphicsModes
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGrid.Gui.DynamicModelEditor.Editor.dynamic_editor_models import (
    clone_block_and_create_vf_for_editor,
    copy_block_state,
)

from VeraGrid.Gui.DynamicModelEditor.Editor.dynamic_block_editor import DynamicBlockEditorGUI
from VeraGrid.Gui.DynamicModelEditor.Workspace.dynamic_editor_entries import DynamicEditorEntry


def block_has_direct_computational_content(block: Block) -> bool:
    """Return whether a block owns behavior rather than only one child shell.

    Interface variables, parameters, and mappings may legitimately be mirrored
    on a template container. Equations and runtime logic are what make the
    container itself a meaningful navigation level.

    :param block: Candidate navigation block.
    :return: Whether the block owns equations or runtime behavior directly.
    """
    result: bool = bool(
        block.state_eqs
        or block.algebraic_eqs
        or block.differential_eqs
        or block.init_eqs
        or block.diff_init_eqs
        or block.inequalities
        or block.discrete_eqs
        or block.boolean_guards
        or block.procedural_logic
    )
    return result


def resolve_navigation_content_block(block: Block) -> Block:
    """Skip redundant single-child containers during Ctrl-click navigation.

    The root editor still displays the assigned template as one block with its
    connection variables. Only after Ctrl-click are empty one-child wrappers
    collapsed, preventing repeated views containing the same block again.

    :param block: Block selected in the parent diagram.
    :return: First meaningful block or branching container in its child chain.
    """
    result: Block = block
    visited_uids: set[int] = set()
    searching: bool = True
    while searching:
        if result.uid in visited_uids:
            searching = False
        else:
            visited_uids.add(result.uid)
            is_transparent_container: bool = (
                len(result.children) == 1
                and not block_has_direct_computational_content(result)
            )
            if is_transparent_container:
                result = result.children[0]
            else:
                searching = False
    return result


class DynamicEditorDocument:
    """
    Represents a single editing document opened in a tab.

    A document owns two block trees and one private symbolic factory:

    * ``original_root_block`` — the authoritative model as it was when the
      document was opened.  Never mutated during editing.
    * ``working_root_block`` — an identity-preserving structural copy that the
      editors modify directly.
    * ``working_var_factory`` — an isolated factory owning every variable and
      internal connection used by the working tree.

    The document also provides lifecycle operations:

    * :meth:`commit` — copy the working tree back into the original tree.
    * :meth:`discard` — throw away the working tree and start fresh from
      the original.
    * :meth:`is_dirty` — whether the working tree has unsaved changes.
    """

    __slots__ = (
        "_original_root_block",
        "_source_var_factory",
        "_working_root_block",
        "_working_var_factory",
    )

    def __init__(self,
                 original_root_block: Block,
                 source_var_factory: VarFactory) -> None:
        """
        Create a new document from the original (persistent) block tree.

        An isolated structural copy and private factory are created immediately;
        all subsequent edits target that working state.

        :param original_root_block: The authoritative block tree to edit.
        :param source_var_factory: Factory owning the persistent symbolic graph.
        :return: None.
        """
        self._original_root_block: Block = original_root_block
        self._source_var_factory: VarFactory = source_var_factory
        self._working_root_block, self._working_var_factory = clone_block_and_create_vf_for_editor(
            block=original_root_block,
            source_var_factory=source_var_factory,
        )

    # ------------------------------------------------------------------
    # Read-only properties
    # ------------------------------------------------------------------

    @property
    def original_root_block(self) -> Block:
        """
        :return: The original (persistent) block tree.
        """
        return self._original_root_block

    @property
    def working_root_block(self) -> Block:
        """
        :return: The working (editable) block tree.
        """
        return self._working_root_block

    @property
    def working_var_factory(self) -> VarFactory:
        """
        Return the private symbolic factory owned by this editing document.

        :return: Factory isolated from the persistent circuit state.
        """
        return self._working_var_factory

    @property
    def source_var_factory(self) -> VarFactory:
        """
        Return the persistent circuit variable factory.

        :return: Factory receiving accepted editor transactions.
        """
        return self._source_var_factory

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def commit(self) -> None:
        """
        Copy the working tree back into the original tree.

        This is the single point where edited state is persisted back
        to the authoritative model.  Call this when the user explicitly
        saves or applies changes.

        :return: None.
        """
        copy_block_state(
            source_block=self._working_root_block,
            target_block=self._original_root_block,
        )
        self._source_var_factory.merge_editor_var_factory(
            working_var_factory=self._working_var_factory,
        )

    def rebuild_working_state(self) -> None:
        """
        Recreate an isolated editing session from the committed circuit state.

        This step runs after bus and device reconciliation so the next editor
        observes the final persistent identities produced by the save workflow.

        :return: None.
        """
        working_state: tuple[Block, VarFactory] = clone_block_and_create_vf_for_editor(
            block=self._original_root_block,
            source_var_factory=self._source_var_factory,
        )
        self._working_root_block = working_state[0]
        self._working_var_factory = working_state[1]

    def discard(self) -> None:
        """
        Discard the current working tree and recreate it from the
        original tree.

        :return: None.
        """
        self.rebuild_working_state()

    def is_dirty(self) -> bool:
        """
        Return whether the working tree has unsaved modifications.

        :return: ``True`` if the document has been modified since the
            last commit.  Currently always returns ``False`` (placeholder).
        """
        return False


class DynamicEditorTab(QtWidgets.QWidget):
    """
    Coordinator widget that replaces a bare :class:`DynamicBlockEditorGUI`
    inside the workspace tab bar.

    It owns:

    * A :class:`DynamicEditorNavigation` (which holds the document).
    * A :class:`DynamicEditorBreadcrumb` at the top.
    * Exactly one :class:`DynamicBlockEditorGUI` below the breadcrumb.

    Navigation (going into a child block) destroys the current editor and
    creates a new one.  There is never more than one editor alive inside
    a tab.  All edits target the single working tree owned by the document.
    """

    __slots__ = ()

    dirtyStateChanged = Signal(bool)
    dynamicPlotDefinitionsChanged = Signal(object, object)

    def __init__(
            self,
            var_factory: VarFactory,
            block: Block,
            api_object: ALL_DEV_TYPES,
            circuit: MultiCircuit,
            current_theme: DynEditorGraphicsModes,
            mode: DynamicSimulationMode,
            templates_list: Optional[List[RmsModelTemplate | EmtModelTemplate | FmuTemplate]] = None,
            parent: QtWidgets.QWidget | None = None,
    ) -> None:
        """Create one editor tab and its isolated working document.

        :param var_factory: Factory that owns symbolic variables.
        :param block: Persistent root block copied into the working document.
        :param api_object: Static network device associated with the model.
        :param circuit: Circuit that owns the static device.
        :param current_theme: Initial editor colour mode.
        :param mode: Dynamic simulation mode represented by the tab.
        :param templates_list: Optional templates exposed in the library.
        :param parent: Owning workspace widget.
        :return: None.
        """
        super().__init__(parent)

        self._var_factory = var_factory
        self._api_object = api_object
        self._circuit = circuit
        self._mode = mode
        self.current_theme = current_theme
        self._templates_list = templates_list if templates_list is not None else list()
        self._dynamic_editor_entry: DynamicEditorEntry | None = None
        self._block2blocktype: Dict[int, BlockType] = dict()
        self._prepared_to_delete: bool = False

        # ---- Document + Navigation ----
        document: DynamicEditorDocument = DynamicEditorDocument(
            original_root_block=block,
            source_var_factory=var_factory,
        )
        prepare_block_for_editing(
            document.working_root_block,
            document.working_var_factory,
        )
        self._navigation = DynamicEditorNavigation(document)

        self._layout = QtWidgets.QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)

        self._breadcrumb = DynamicEditorBreadcrumb()
        self._breadcrumb.blockClicked.connect(self._on_breadcrumb_clicked)
        self._layout.addWidget(self._breadcrumb)

        self._editor: DynamicBlockEditorGUI | None = None
        self._create_editor(self._navigation.root_block)

    # ------------------------------------------------------------------
    # Public API — session / workspace compatibility
    # ------------------------------------------------------------------

    def get_dynamic_editor_entry(self) -> DynamicEditorEntry | None:
        """Return the workspace entry associated with this tab.

        :return: Dynamic editor entry, or ``None`` before registration.
        """
        return self._dynamic_editor_entry

    def set_dynamic_editor_entry(self, entry: DynamicEditorEntry) -> None:
        """Associate the tab with one workspace entry.

        :param entry: Device/mode entry represented by the tab.
        :return: None.
        """
        self._dynamic_editor_entry = entry

    def get_dynamic_editor_mode(self) -> DynamicSimulationMode:
        """Return the simulation mode represented by this tab.

        :return: RMS, EMT, or FMU mode.
        """
        return self._mode

    def get_dynamic_editor_display_title(self) -> str:
        """Build the user-facing tab title from device and mode.

        :return: Display title for the workspace tab.
        """
        object_name = self._api_object.name if self._api_object is not None else "Dynamic object"
        return f"{object_name} [{self._mode.name} model]"

    @property
    def has_unapplied_changes(self) -> bool:
        """Return whether the hosted editor contains unapplied changes.

        :return: Dirty state reported by the current editor.
        """
        if self._editor is not None:
            return self._editor.has_unapplied_changes
        else:
            pass
        return False

    def can_close_editor(self, parent: QtWidgets.QWidget | None = None) -> bool:
        """Ask the hosted editor whether its page may close.

        :param parent: Widget used as parent for any confirmation prompt.
        :return: Whether closing may continue.
        """
        if self._editor is not None:
            return self._editor.can_close_editor(parent)
        else:
            pass
        return True

    def prepare_to_delete(self) -> None:
        """
        Release the currently hosted editor before this tab is destroyed.

        The tab owns a breadcrumb and one nested dynamic editor. The nested
        editor allocates scene/view/model objects dynamically, so the tab must
        explicitly detach that subtree before the Python wrapper becomes the
        only remaining owner.

        :return: None.
        """
        if self._prepared_to_delete:
            return
        else:
            pass

        self._prepared_to_delete = True
        self._dispose_editor()

        if self._breadcrumb is not None:
            try:
                self._breadcrumb.blockClicked.disconnect(self._on_breadcrumb_clicked)
            except (RuntimeError, TypeError):
                pass
            self._breadcrumb.prepare_to_delete()
            self._layout.removeWidget(self._breadcrumb)
            self._breadcrumb.setParent(None)
            self._breadcrumb.deleteLater()
            self._breadcrumb = None
        else:
            pass

    def set_dark_mode(self) -> None:
        """Apply dark mode to the hosted editor.

        :return: None.
        """
        if self._editor is not None:
            self._editor.set_dark_mode()
            self.current_theme = DynEditorGraphicsModes.DARK
        else:
            pass

    def set_light_mode(self) -> None:
        """Apply light mode to the hosted editor.

        :return: None.
        """
        if self._editor is not None:
            self._editor.set_light_mode()
            self.current_theme = DynEditorGraphicsModes.LIGHT
        else:
            pass

    # ------------------------------------------------------------------
    # Navigation — always over the working tree
    # ------------------------------------------------------------------

    def navigate_to_block(self, block: Block) -> None:
        """
        Navigate into a child block: prepare it in-place, update state,
        recreate the editor, and refresh the breadcrumb.

        No new copy is created; the block already lives in the working tree.

        :param block: Child block to navigate into.
        :return: None.
        """
        content_block: Block = resolve_navigation_content_block(block)
        if content_block.uid == self._navigation.current_block.uid:
            # Atomic leaf editors render their own DAE as the central node.
            # Ctrl-clicking that presentation must not push the same block onto
            # the breadcrumb repeatedly.
            return
        else:
            pass
        content_block, self._block2blocktype = prepare_block_for_editing(
            content_block,
            self._navigation.document.working_var_factory,
        )
        self._navigation.open_child(content_block)
        self._replace_editor()

    def navigate_to_breadcrumb_block(self, block: Block) -> None:
        """
        Navigate to a specific ancestor block via breadcrumb click.

        :param block: An ancestor block in the current path.
        :return: None.
        """
        self._navigation.go_to(block)
        self._replace_editor()

    def refresh_breadcrumb(self) -> None:
        """
        Refresh the breadcrumb labels from the current navigation path.

        :return: None.
        """
        self._refresh_breadcrumb()

    def apply_changes(self) -> None:
        """
        Persist the active editor and synchronously rebuild its working state.

        Persistence returns before the old editor is disposed, preventing Qt
        from destroying an object while one of its methods is still active.
        The replacement editor then receives a new isolated block tree and
        variable factory copied from the final persistent circuit state.

        :return: None.
        """
        editor: DynamicBlockEditorGUI | None = self._editor
        if editor is not None and not self._prepared_to_delete:
            # Complete the persistent block and factory transaction while the
            # editor that owns the save action remains fully alive.
            editor.persist_changes_only()

            # Bus and device reconciliation is now complete, so the fresh
            # working copy observes the definitive persistent connection graph.
            self._navigation.document.rebuild_working_state()
            self._navigation.reset()

            # Persistence has returned and the previous editor can now be
            # replaced without leaving a deferred Qt callback behind.
            self._replace_editor()
        else:
            pass

    # ------------------------------------------------------------------
    # Editor delegation — forward commonly accessed attributes
    # ------------------------------------------------------------------

    @property
    def editor(self) -> DynamicBlockEditorGUI | None:
        """Return the currently hosted block editor.

        :return: Active editor, or ``None`` during teardown.
        """
        return self._editor

    @property
    def is_root_editor(self) -> bool:
        """Return whether navigation currently points at the document root.

        :return: Root-navigation state.
        """
        return self._navigation.is_root()

    @property
    def root_block(self) -> Block:
        """Return the root block of the working document.

        :return: Working root block.
        """
        return self._navigation.root_block

    @property
    def current_block(self) -> Block:
        """Return the block currently displayed by the editor.

        :return: Current working block.
        """
        return self._navigation.current_block

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _create_editor(self, block: Block) -> None:
        """Create the single block editor hosted by this tab.

        :param block: Working-tree block to display.
        :return: None.
        """
        self._editor = DynamicBlockEditorGUI(
            var_factory=self._navigation.document.working_var_factory,
            root_block=self._navigation.root_block,
            current_block=block,
            api_object=self._api_object,
            circuit=self._circuit,
            mode=self._mode,
            current_theme = self.current_theme,
            templates_list=self._templates_list,
            is_root_editor=self._navigation.is_root(),
            modal=False,
            workspace_embedded=True,
            document=self._navigation.document,
            block2blocktype=self._block2blocktype
        )
        if self._editor is not None:
            self._editor.set_navigation_delegate(self)
            self._editor.dirtyStateChanged.connect(self.dirtyStateChanged)
            self._editor.dynamicPlotDefinitionsChanged.connect(
                self._forward_dynamic_plot_definitions_changed
            )
            self._layout.addWidget(self._editor)
            self._refresh_breadcrumb()
        else:
            pass

    def _replace_editor(self) -> None:
        """Replace the hosted editor after a navigation change.

        :return: None.
        """
        self._dispose_editor()
        self._create_editor(self._navigation.current_block)

    def _dispose_editor(self) -> None:
        """
        Disconnect, detach, and queue the currently hosted editor for deletion.

        :return: None.
        """
        editor: DynamicBlockEditorGUI | None = self._editor
        if editor is None:
            return
        else:
            pass

        try:
            editor.dirtyStateChanged.disconnect(self.dirtyStateChanged)
        except (RuntimeError, TypeError):
            pass
        try:
            editor.dynamicPlotDefinitionsChanged.disconnect(
                self._forward_dynamic_plot_definitions_changed
            )
        except (RuntimeError, TypeError):
            pass
        editor.prepare_to_delete()
        self._layout.removeWidget(editor)
        editor.setParent(None)
        editor.deleteLater()
        self._editor = None

    def _forward_dynamic_plot_definitions_changed(
            self,
            mode: object,
            source: object,
    ) -> None:
        """
        Forward an immediate plot-asset change from the hosted editor.

        :param mode: RMS or EMT simulation mode emitted by the editor.
        :param source: Editor instance that changed the persistent assets.
        :return: None.
        """
        self.dynamicPlotDefinitionsChanged.emit(mode, source)

    def _refresh_breadcrumb(self) -> None:
        """Render the current navigation path in the breadcrumb widget.

        :return: None.
        """
        path: List[Block] = self._navigation.breadcrumb_path()
        self._breadcrumb.set_path(path)

    def _on_breadcrumb_clicked(self, block: Block) -> None:
        """Navigate to the ancestor selected in the breadcrumb.

        :param block: Working-tree ancestor selected by the user.
        :return: None.
        """
        self.navigate_to_breadcrumb_block(block)
