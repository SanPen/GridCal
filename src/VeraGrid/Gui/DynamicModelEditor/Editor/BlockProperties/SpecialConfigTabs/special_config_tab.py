# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""Common lifecycle contract for Block Properties special tabs."""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets
from PySide6.QtCore import Signal

from VeraGridEngine.Templates.template_definition import TemplateDefinition


class SpecialConfigTabWidget(QtWidgets.QWidget):
    """Base widget contract used by every block-specific configuration tab.

    Concrete tabs own their generated Designer UI and detached draft. They only
    write validated values to the template builder when Block Properties starts
    its existing structural rebuild transaction.
    """

    draftChanged = Signal()

    # Shiboken 6.10.3 clears only the concrete class's slot count when allocating
    # a wrapper, leaving inherited slots uninitialized. Keep shared attributes
    # in QWidget's instance dictionary; concrete tabs can still declare slots.
    __slots__ = ()

    def __init__(self,
                 builder: TemplateDefinition,
                 tab_title: str,
                 parent: QtWidgets.QWidget | None = None) -> None:
        """Initialize the shared builder reference and tab identity.

        :param builder: Detached template builder owned by Block Properties.
        :param tab_title: User-facing title shown by the parent tab widget.
        :param parent: Owning Block Properties dialog.
        :return: None.
        """
        super().__init__(parent)
        self._builder: TemplateDefinition = builder
        self._tab_title: str = tab_title
        self._prepared_to_delete: bool = False

    def get_tab_title(self) -> str:
        """Return the semantic title displayed by Block Properties.

        :return: User-facing tab title.
        """
        return self._tab_title

    def get_builder(self) -> TemplateDefinition:
        """Return the detached builder receiving validated draft values.

        :return: Template builder owned by the current properties transaction.
        """
        return self._builder

    def has_changes(self) -> bool:
        """Return whether this tab owns unapplied edits.

        Concrete tabs override this query with their detached draft comparison.

        :return: ``False`` in the base implementation.
        """
        return False

    def get_validation_error(self) -> str | None:
        """Validate the complete detached draft without changing the builder.

        Concrete tabs return their first actionable validation message.

        :return: Validation message, or ``None`` when the draft is valid.
        """
        return None

    def apply_draft_to_builder(self) -> None:
        """Copy the validated draft into the detached template builder.

        Concrete tabs override this method. The base has no draft to copy.

        :return: None.
        """
        pass

    def reload_from_builder(self) -> None:
        """Reload the accepted builder state after a successful rebuild.

        Concrete tabs override this method to replace their clean baseline.

        :return: None.
        """
        pass

    def set_read_only(self, read_only: bool) -> None:
        """Enable or disable user interaction for provider-owned blocks.

        :param read_only: Whether all editing controls must be disabled.
        :return: None.
        """
        self.setEnabled(not read_only)

    def prepare_to_delete(self) -> None:
        """Disconnect tab-owned Qt resources before parent destruction.

        Concrete tabs must detach models, plot canvases and other binary-backed
        children before calling this base implementation.

        :return: None.
        """
        if self._prepared_to_delete:
            pass
        else:
            self._prepared_to_delete = True

    def is_prepared_to_delete(self) -> bool:
        """Return whether explicit Qt teardown has already run.

        :return: Whether the tab has released its owned resources.
        """
        return self._prepared_to_delete

    def changeEvent(self, event: QtCore.QEvent) -> None:
        """Allow concrete tabs to refresh generated Designer translations.

        :param event: Incoming Qt change event.
        :return: None.
        """
        QtWidgets.QWidget.changeEvent(self, event)
