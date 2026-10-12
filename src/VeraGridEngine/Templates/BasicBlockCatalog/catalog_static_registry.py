# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from functools import lru_cache
from typing import Sequence


class BasicBlockCatalogStaticRecord:
    """
    Immutable static record for one shipped basic-block catalog template.
    """

    __slots__ = (
        "_template_key",
        "_typ_id",
        "_blkdef_name",
        "_sample_display_name",
        "_display_label",
        "_category_path",
        "_inputs",
        "_outputs",
        "_states",
        "_params",
        "_unsupported_lines",
        "_module_name",
        "_module_filename",
    )

    def __init__(self,
                 template_key: str,
                 typ_id: str,
                 blkdef_name: str,
                 sample_display_name: str,
                 display_label: str,
                 category_path: Sequence[str],
                 inputs: Sequence[str],
                 outputs: Sequence[str],
                 states: Sequence[str],
                 params: Sequence[str],
                 unsupported_lines: Sequence[str],
                 module_name: str,
                 module_filename: str) -> None:
        """
        Store one immutable static catalog record.

        :param template_key: Stable semantic lookup key.
        :param typ_id: Imported type identifier.
        :param blkdef_name: Raw source block name.
        :param sample_display_name: Clean human-facing source name.
        :param display_label: Unique label exposed in the editor.
        :param category_path: Full editor category path.
        :param inputs: Input names.
        :param outputs: Output names.
        :param states: State names.
        :param params: Runtime parameter names.
        :param unsupported_lines: Pending markers for non editor-ready templates.
        :param module_name: Standalone module stem.
        :param module_filename: Standalone module filename.
        :returns: None.
        """
        self._template_key = template_key
        self._typ_id = typ_id
        self._blkdef_name = blkdef_name
        self._sample_display_name = sample_display_name
        self._display_label = display_label
        self._category_path = tuple(category_path)
        self._inputs = tuple(inputs)
        self._outputs = tuple(outputs)
        self._states = tuple(states)
        self._params = tuple(params)
        self._unsupported_lines = tuple(unsupported_lines)
        self._module_name = module_name
        self._module_filename = module_filename

    @property
    def template_key(self) -> str:
        """
        Return the template lookup key.

        :returns: Value.
        """
        return self._template_key

    @property
    def typ_id(self) -> str:
        """
        Return the imported type identifier.

        :returns: Value.
        """
        return self._typ_id

    @property
    def blkdef_name(self) -> str:
        """
        Return the raw block name.

        :returns: Value.
        """
        return self._blkdef_name

    @property
    def sample_display_name(self) -> str:
        """
        Return the clean source name.

        :returns: Value.
        """
        return self._sample_display_name

    @property
    def display_label(self) -> str:
        """
        Return the unique editor label.

        :returns: Value.
        """
        return self._display_label

    @property
    def category_path(self) -> Sequence[str]:
        """
        Return the category path.

        :returns: Value.
        """
        return self._category_path

    @property
    def inputs(self) -> Sequence[str]:
        """
        Return the input-name tuple.

        :returns: Value.
        """
        return self._inputs

    @property
    def outputs(self) -> Sequence[str]:
        """
        Return the output-name tuple.

        :returns: Value.
        """
        return self._outputs

    @property
    def states(self) -> Sequence[str]:
        """
        Return the state-name tuple.

        :returns: Value.
        """
        return self._states

    @property
    def params(self) -> Sequence[str]:
        """
        Return the parameter-name tuple.

        :returns: Value.
        """
        return self._params

    @property
    def unsupported_lines(self) -> Sequence[str]:
        """
        Return the unsupported marker tuple.

        :returns: Value.
        """
        return self._unsupported_lines

    @property
    def module_name(self) -> str:
        """
        Return the standalone module stem.

        :returns: Value.
        """
        return self._module_name

    @property
    def module_filename(self) -> str:
        """
        Return the standalone module filename.

        :returns: Value.
        """
        return self._module_filename

def build_basic_block_catalog_pending_template_reason() -> str:
    """
    Return the canonical pending reason for non-executable templates.

    :returns: Pending reason.
    """
    return "template_has_no_executable_content"


@lru_cache(maxsize=1)
def get_basic_block_catalog_static_records() -> Sequence[BasicBlockCatalogStaticRecord]:
    """
    Return the immutable static records for the shipped basic-block catalog.

    :returns: Static catalog records.
    """
    records: list[BasicBlockCatalogStaticRecord] = list()

    # The records are emitted as a static snapshot so runtime discovery does not
    # depend on package paths, module iteration, or manifest side files.
    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='a_x_c1_x_c2',
            typ_id='2',
            blkdef_name='a(x-c1)(x-c2)',
            sample_display_name='a(x-c1)(x-c2)',
            display_label='a(x-c1)(x-c2)',
            category_path=('Native', 'Math and Functions', 'Scaling and Products'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=('a', 'c1', 'c2'),
            unsupported_lines=(),
            module_name='typ_2__a_x_c1_x_c2',
            module_filename='typ_2__a_x_c1_x_c2.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='ax_2_bx_c',
            typ_id='3',
            blkdef_name='ax^2 + bx + c',
            sample_display_name='ax^2 + bx + c',
            display_label='ax^2 + bx + c',
            category_path=('Native', 'Math and Functions', 'Scaling and Products'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=('a', 'b', 'c'),
            unsupported_lines=(),
            module_name='typ_3__ax_2_bx_c',
            module_filename='typ_3__ax_2_bx_c.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='mx_n',
            typ_id='4',
            blkdef_name='mx + n',
            sample_display_name='mx + n',
            display_label='mx + n',
            category_path=('Native', 'Math and Functions', 'Scaling and Products'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=('m', 'n'),
            unsupported_lines=(),
            module_name='typ_4__mx_n',
            module_filename='typ_4__mx_n.py',
        )
    )

    # records.append(
    #     BasicBlockCatalogStaticRecord(
    #         template_key='inverse_lookup_array_linear',
    #         typ_id='5',
    #         blkdef_name='Inverse Lookup array (linear)',
    #         sample_display_name='Inverse Lookup array (linear)',
    #         display_label='Inverse Lookup array (linear)',
    #         category_path=('Native', 'Lookup and Tables', 'Arrays and Matrices'),
    #         inputs=('yi',),
    #         outputs=('yo',),
    #         states=(),
    #         params=('array_K',),
    #         unsupported_lines=(),
    #         module_name='typ_5__inverse_lookup_array_linear',
    #         module_filename='typ_5__inverse_lookup_array_linear.py',
    #     )
    # )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='inverse_lookup_array_object_linear',
            typ_id='6',
            blkdef_name='Inverse Lookup array object (linear)',
            sample_display_name='Inverse Lookup array object (linear)',
            display_label='Inverse Lookup array object (linear)',
            category_path=('Native', 'Arrays and Matrices'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=('oarray_K',),
            unsupported_lines=(),
            module_name='typ_6__inverse_lookup_array_object_linear',
            module_filename='typ_6__inverse_lookup_array_object_linear.py',
        )
    )
    #
    # records.append(
    #     BasicBlockCatalogStaticRecord(
    #         template_key='lookup_array_linear',
    #         typ_id='7',
    #         blkdef_name='Lookup array (linear)',
    #         sample_display_name='Lookup array (linear)',
    #         display_label='Lookup array (linear)',
    #         category_path=('Native', 'Lookup and Tables', 'Arrays and Matrices'),
    #         inputs=('yi',),
    #         outputs=('yo',),
    #         states=(),
    #         params=('array_K',),
    #         unsupported_lines=(),
    #         module_name='typ_7__lookup_array_linear',
    #         module_filename='typ_7__lookup_array_linear.py',
    #     )
    # )
    #
    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='lookup_array_linear_noclipping',
            typ_id='8',
            blkdef_name='Lookup array (linear_noclipping)',
            sample_display_name='Lookup array (linear_noclipping)',
            display_label='Lookup array (linear noclipping)',
            category_path=('Native', 'Arrays and Matrices'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=('array_K',),
            unsupported_lines=(),
            module_name='typ_8__lookup_array_linear_noclipping',
            module_filename='typ_8__lookup_array_linear_noclipping.py',
        )
    )
    #
    # records.append(
    #     BasicBlockCatalogStaticRecord(
    #         template_key='lookup_array_spline',
    #         typ_id='9',
    #         blkdef_name='Lookup array (spline)',
    #         sample_display_name='Lookup array (spline)',
    #         display_label='Lookup array (spline)',
    #         category_path=('Native', 'Lookup and Tables', 'Arrays and Matrices'),
    #         inputs=('yi',),
    #         outputs=('yo',),
    #         states=(),
    #         params=('array_K',),
    #         unsupported_lines=(),
    #         module_name='typ_9__lookup_array_spline',
    #         module_filename='typ_9__lookup_array_spline.py',
    #     )
    # )
    #
    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='lookup_array_1x3_linear_fixed',
            typ_id='10',
            blkdef_name='Lookup array 1x3 (linear_fixed)',
            sample_display_name='Lookup array 1x3 (linear_fixed)',
            display_label='Lookup array 1x3 (linear fixed)',
            category_path=('Native', 'Arrays and Matrices'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=('arr_x1', 'arr_x2', 'arr_x3', 'arr_y1', 'arr_y2', 'arr_y3', 'vClip'),
            unsupported_lines=(),
            module_name='typ_10__lookup_array_1x3_linear_fixed',
            module_filename='typ_10__lookup_array_1x3_linear_fixed.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='lookup_array_1x3_linear_variable',
            typ_id='11',
            blkdef_name='Lookup array 1x3 (linear_variable)',
            sample_display_name='Lookup array 1x3 (linear_variable)',
            display_label='Lookup array 1x3 (linear variable)',
            category_path=('Native', 'Arrays and Matrices'),
            inputs=('yi', 'arr_x1', 'arr_x2', 'arr_x3', 'arr_y1', 'arr_y2', 'arr_y3'),
            outputs=('yo',),
            states=(),
            params=('vClip',),
            unsupported_lines=(),
            module_name='typ_11__lookup_array_1x3_linear_variable',
            module_filename='typ_11__lookup_array_1x3_linear_variable.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='lookup_array_1x4_linear_fixed',
            typ_id='12',
            blkdef_name='Lookup array 1x4 (linear_fixed)',
            sample_display_name='Lookup array 1x4 (linear_fixed)',
            display_label='Lookup array 1x4 (linear fixed)',
            category_path=('Native', 'Arrays and Matrices'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=('arr_x1', 'arr_x2', 'arr_x3', 'arr_x4', 'arr_y1', 'arr_y2', 'arr_y3', 'arr_y4', 'vClip'),
            unsupported_lines=(),
            module_name='typ_12__lookup_array_1x4_linear_fixed',
            module_filename='typ_12__lookup_array_1x4_linear_fixed.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='lookup_array_1x4_linear_variable',
            typ_id='13',
            blkdef_name='Lookup array 1x4 (linear_variable)',
            sample_display_name='Lookup array 1x4 (linear_variable)',
            display_label='Lookup array 1x4 (linear variable)',
            category_path=('Native', 'Arrays and Matrices'),
            inputs=('yi', 'arr_x1', 'arr_x2', 'arr_x3', 'arr_x4', 'arr_y1', 'arr_y2', 'arr_y3', 'arr_y4'),
            outputs=('yo',),
            states=(),
            params=('vClip',),
            unsupported_lines=(),
            module_name='typ_13__lookup_array_1x4_linear_variable',
            module_filename='typ_13__lookup_array_1x4_linear_variable.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='lookup_array_object_linear',
            typ_id='14',
            blkdef_name='Lookup array object (linear)',
            sample_display_name='Lookup array object (linear)',
            display_label='Lookup array object (linear)',
            category_path=('Native', 'Arrays and Matrices'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=('oarray_K',),
            unsupported_lines=(),
            module_name='typ_14__lookup_array_object_linear',
            module_filename='typ_14__lookup_array_object_linear.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='lookup_array_object_linear_noclipping',
            typ_id='15',
            blkdef_name='Lookup array object (linear_noclipping)',
            sample_display_name='Lookup array object (linear_noclipping)',
            display_label='Lookup array object (linear noclipping)',
            category_path=('Native', 'Arrays and Matrices'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=('oarray_K',),
            unsupported_lines=(),
            module_name='typ_15__lookup_array_object_linear_noclipping',
            module_filename='typ_15__lookup_array_object_linear_noclipping.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='lookup_array_object_spline',
            typ_id='16',
            blkdef_name='Lookup array object (spline)',
            sample_display_name='Lookup array object (spline)',
            display_label='Lookup array object (spline)',
            category_path=('Native', 'Arrays and Matrices'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=('oarray_K',),
            unsupported_lines=(),
            module_name='typ_16__lookup_array_object_spline',
            module_filename='typ_16__lookup_array_object_spline.py',
        )
    )

    ############################ missing these two ######################################

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='lookup_matrix_linear',
            typ_id='17',
            blkdef_name='Lookup matrix (linear)',
            sample_display_name='Lookup matrix (linear)',
            display_label='Lookup matrix (linear)',
            category_path=('Native', 'Lookup and Tables', 'Arrays and Matrices'),
            inputs=('yi1', 'yi2'),
            outputs=('yo',),
            states=(),
            params=('matrix_K',),
            unsupported_lines=(),
            module_name='typ_17__lookup_matrix_linear',
            module_filename='typ_17__lookup_matrix_linear.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='lookup_matrix_spline',
            typ_id='18',
            blkdef_name='Lookup matrix (spline)',
            sample_display_name='Lookup matrix (spline)',
            display_label='Lookup matrix (spline)',
            category_path=('Native', 'Lookup and Tables', 'Arrays and Matrices'),
            inputs=('yi1', 'yi2'),
            outputs=('yo',),
            states=(),
            params=('matrix_K',),
            unsupported_lines=(),
            module_name='typ_18__lookup_matrix_spline',
            module_filename='typ_18__lookup_matrix_spline.py',
        )
    )

    ###################################################################################################

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='lookup_matrix_object_linear',
            typ_id='19',
            blkdef_name='Lookup matrix object (linear)',
            sample_display_name='Lookup matrix object (linear)',
            display_label='Lookup matrix object (linear)',
            category_path=('Native', 'Arrays and Matrices'),
            inputs=('yi1', 'yi2'),
            outputs=('yo',),
            states=(),
            params=('omatrix_K',),
            unsupported_lines=(),
            module_name='typ_19__lookup_matrix_object_linear',
            module_filename='typ_19__lookup_matrix_object_linear.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='lookup_matrix_object_spline',
            typ_id='20',
            blkdef_name='Lookup matrix object (spline)',
            sample_display_name='Lookup matrix object (spline)',
            display_label='Lookup matrix object (spline)',
            category_path=('Native', 'Arrays and Matrices'),
            inputs=('yi1', 'yi2'),
            outputs=('yo',),
            states=(),
            params=('omatrix_K',),
            unsupported_lines=(),
            module_name='typ_20__lookup_matrix_object_spline',
            module_filename='typ_20__lookup_matrix_object_spline.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='yi_equals_c',
            typ_id='21',
            blkdef_name='yi equals C',
            sample_display_name='yi equals C',
            display_label='yi equals C',
            category_path=('Native', 'Logic and Events', 'Comparators'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=('C',),
            unsupported_lines=(),
            module_name='typ_21__yi_equals_c',
            module_filename='typ_21__yi_equals_c.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='yi_greater_than_c',
            typ_id='22',
            blkdef_name='yi greater than C',
            sample_display_name='yi greater than C',
            display_label='yi greater than C',
            category_path=('Native', 'Logic and Events', 'Comparators'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=('C',),
            unsupported_lines=(),
            module_name='typ_22__yi_greater_than_c',
            module_filename='typ_22__yi_greater_than_c.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='yi_greater_than_or_equal_c',
            typ_id='23',
            blkdef_name='yi greater than or equal C',
            sample_display_name='yi greater than or equal C',
            display_label='yi greater than or equal C',
            category_path=('Native', 'Logic and Events', 'Comparators'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=('C',),
            unsupported_lines=(),
            module_name='typ_23__yi_greater_than_or_equal_c',
            module_filename='typ_23__yi_greater_than_or_equal_c.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='yi_less_than_c',
            typ_id='24',
            blkdef_name='yi less than C',
            sample_display_name='yi less than C',
            display_label='yi less than C',
            category_path=('Native', 'Logic and Events', 'Comparators'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=('C',),
            unsupported_lines=(),
            module_name='typ_24__yi_less_than_c',
            module_filename='typ_24__yi_less_than_c.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='yi_less_than_or_equal_c',
            typ_id='25',
            blkdef_name='yi less than or equal C',
            sample_display_name='yi less than or equal C',
            display_label='yi less than or equal C',
            category_path=('Native', 'Logic and Events', 'Comparators'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=('C',),
            unsupported_lines=(),
            module_name='typ_25__yi_less_than_or_equal_c',
            module_filename='typ_25__yi_less_than_or_equal_c.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='yi_not_equals_c',
            typ_id='26',
            blkdef_name='yi not equals C',
            sample_display_name='yi not equals C',
            display_label='yi not equals C',
            category_path=('Native', 'Logic and Events', 'Comparators'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=('C',),
            unsupported_lines=(),
            module_name='typ_26__yi_not_equals_c',
            module_filename='typ_26__yi_not_equals_c.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='yi1_equals_yi2',
            typ_id='27',
            blkdef_name='yi1 equals yi2',
            sample_display_name='yi1 equals yi2',
            display_label='yi1 equals yi2',
            category_path=('Native', 'Logic and Events', 'Comparators'),
            inputs=('yi1', 'yi2'),
            outputs=('yo',),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_27__yi1_equals_yi2',
            module_filename='typ_27__yi1_equals_yi2.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='yi1_greater_than_or_equal_yi2',
            typ_id='28',
            blkdef_name='yi1 greater than or equal yi2',
            sample_display_name='yi1 greater than or equal yi2',
            display_label='yi1 greater than or equal yi2',
            category_path=('Native', 'Logic and Events', 'Comparators'),
            inputs=('yi1', 'yi2'),
            outputs=('yo',),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_28__yi1_greater_than_or_equal_yi2',
            module_filename='typ_28__yi1_greater_than_or_equal_yi2.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='yi1_greater_than_yi2',
            typ_id='29',
            blkdef_name='yi1 greater than yi2',
            sample_display_name='yi1 greater than yi2',
            display_label='yi1 greater than yi2',
            category_path=('Native', 'Logic and Events', 'Comparators'),
            inputs=('yi1', 'yi2'),
            outputs=('yo',),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_29__yi1_greater_than_yi2',
            module_filename='typ_29__yi1_greater_than_yi2.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='yi1_less_or_equal_than_yi2',
            typ_id='30',
            blkdef_name='yi1 less or equal than yi2',
            sample_display_name='yi1 less or equal than yi2',
            display_label='yi1 less or equal than yi2',
            category_path=('Native', 'Logic and Events', 'Comparators'),
            inputs=('yi1', 'yi2'),
            outputs=('yo',),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_30__yi1_less_or_equal_than_yi2',
            module_filename='typ_30__yi1_less_or_equal_than_yi2.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='yi1_less_than_yi2',
            typ_id='31',
            blkdef_name='yi1 less than yi2',
            sample_display_name='yi1 less than yi2',
            display_label='yi1 less than yi2',
            category_path=('Native', 'Logic and Events', 'Comparators'),
            inputs=('yi1', 'yi2'),
            outputs=('yo',),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_31__yi1_less_than_yi2',
            module_filename='typ_31__yi1_less_than_yi2.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='yi1_not_equals_yi2',
            typ_id='32',
            blkdef_name='yi1 not equals yi2',
            sample_display_name='yi1 not equals yi2',
            display_label='yi1 not equals yi2',
            category_path=('Native', 'Logic and Events', 'Comparators'),
            inputs=('yi1', 'yi2'),
            outputs=('yo',),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_32__yi1_not_equals_yi2',
            module_filename='typ_32__yi1_not_equals_yi2.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='abs_in_greater_than_c_ip',
            typ_id='33',
            blkdef_name='abs(in) greater than C _ip',
            sample_display_name='abs(in) greater than C _ip',
            display_label='abs(in) greater than C (pulse)',
            category_path=('Native', 'Waveforms and Time', 'Signal Generators'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=('C', 'Tpick', 'Tdrop'),
            unsupported_lines=(),
            module_name='typ_33__abs_in_greater_than_c_ip',
            module_filename='typ_33__abs_in_greater_than_c_ip.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='abs_in_less_than_c_ip',
            typ_id='34',
            blkdef_name='abs(in) less than C _ip',
            sample_display_name='abs(in) less than C _ip',
            display_label='abs(in) less than C (pulse)',
            category_path=('Native', 'Waveforms and Time', 'Signal Generators'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=('C', 'Tpick', 'Tdrop'),
            unsupported_lines=(),
            module_name='typ_34__abs_in_less_than_c_ip',
            module_filename='typ_34__abs_in_less_than_c_ip.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='yi_equals_c_ip',
            typ_id='35',
            blkdef_name='yi equals C _ip',
            sample_display_name='yi equals C _ip',
            display_label='yi equals C (pulse)',
            category_path=('Native', 'Waveforms and Time', 'Signal Generators'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=('C', 'Tpick', 'Tdrop'),
            unsupported_lines=(),
            module_name='typ_35__yi_equals_c_ip',
            module_filename='typ_35__yi_equals_c_ip.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='yi_greater_than_c_ip',
            typ_id='36',
            blkdef_name='yi greater than C _ip',
            sample_display_name='yi greater than C _ip',
            display_label='yi greater than C (pulse)',
            category_path=('Native', 'Waveforms and Time', 'Signal Generators'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=('C', 'Tpick', 'Tdrop'),
            unsupported_lines=(),
            module_name='typ_36__yi_greater_than_c_ip',
            module_filename='typ_36__yi_greater_than_c_ip.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='yi_greater_than_or_equal_c_ip',
            typ_id='37',
            blkdef_name='yi greater than or equal C _ip',
            sample_display_name='yi greater than or equal C _ip',
            display_label='yi greater than or equal C (pulse)',
            category_path=('Native', 'Waveforms and Time', 'Signal Generators'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=('C', 'Tpick', 'Tdrop'),
            unsupported_lines=(),
            module_name='typ_37__yi_greater_than_or_equal_c_ip',
            module_filename='typ_37__yi_greater_than_or_equal_c_ip.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='yi_less_than_c_ip',
            typ_id='38',
            blkdef_name='yi less than C _ip',
            sample_display_name='yi less than C _ip',
            display_label='yi less than C (pulse)',
            category_path=('Native', 'Waveforms and Time', 'Signal Generators'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=('C', 'Tpick', 'Tdrop'),
            unsupported_lines=(),
            module_name='typ_38__yi_less_than_c_ip',
            module_filename='typ_38__yi_less_than_c_ip.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='yi_less_than_or_equal_c_ip',
            typ_id='39',
            blkdef_name='yi less than or equal C _ip',
            sample_display_name='yi less than or equal C _ip',
            display_label='yi less than or equal C (pulse)',
            category_path=('Native', 'Waveforms and Time', 'Signal Generators'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=('C', 'Tpick', 'Tdrop'),
            unsupported_lines=(),
            module_name='typ_39__yi_less_than_or_equal_c_ip',
            module_filename='typ_39__yi_less_than_or_equal_c_ip.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='yi1_equals_yi2_ip',
            typ_id='40',
            blkdef_name='yi1 equals yi2 _ip',
            sample_display_name='yi1 equals yi2 _ip',
            display_label='yi1 equals yi2 (pulse)',
            category_path=('Native', 'Waveforms and Time', 'Signal Generators'),
            inputs=('yi1', 'yi2'),
            outputs=('yo',),
            states=(),
            params=('Tpick', 'Tdrop'),
            unsupported_lines=(),
            module_name='typ_40__yi1_equals_yi2_ip',
            module_filename='typ_40__yi1_equals_yi2_ip.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='yi1_greater_than_or_equal_yi2_ip',
            typ_id='41',
            blkdef_name='yi1 greater than or equal yi2 _ip',
            sample_display_name='yi1 greater than or equal yi2 _ip',
            display_label='yi1 greater than or equal yi2 (pulse)',
            category_path=('Native', 'Waveforms and Time', 'Signal Generators'),
            inputs=('yi1', 'yi2'),
            outputs=('yo',),
            states=(),
            params=('Tpick', 'Tdrop'),
            unsupported_lines=(),
            module_name='typ_41__yi1_greater_than_or_equal_yi2_ip',
            module_filename='typ_41__yi1_greater_than_or_equal_yi2_ip.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='yi1_greater_than_yi2_ip',
            typ_id='42',
            blkdef_name='yi1 greater than yi2 _ip',
            sample_display_name='yi1 greater than yi2 _ip',
            display_label='yi1 greater than yi2 (pulse)',
            category_path=('Native', 'Waveforms and Time', 'Signal Generators'),
            inputs=('yi1', 'yi2'),
            outputs=('yo',),
            states=(),
            params=('Tpick', 'Tdrop'),
            unsupported_lines=(),
            module_name='typ_42__yi1_greater_than_yi2_ip',
            module_filename='typ_42__yi1_greater_than_yi2_ip.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='yi1_less_than_or_equal_yi2_ip',
            typ_id='43',
            blkdef_name='yi1 less than or equal yi2  _ip',
            sample_display_name='yi1 less than or equal yi2  _ip',
            display_label='yi1 less than or equal yi2 (pulse)',
            category_path=('Native', 'Waveforms and Time', 'Signal Generators'),
            inputs=('yi1', 'yi2'),
            outputs=('yo',),
            states=(),
            params=('Tpick', 'Tdrop'),
            unsupported_lines=(),
            module_name='typ_43__yi1_less_than_or_equal_yi2_ip',
            module_filename='typ_43__yi1_less_than_or_equal_yi2_ip.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='yi1_less_than_yi2_ip',
            typ_id='44',
            blkdef_name='yi1 less than yi2 _ip',
            sample_display_name='yi1 less than yi2 _ip',
            display_label='yi1 less than yi2 (pulse)',
            category_path=('Native', 'Waveforms and Time', 'Signal Generators'),
            inputs=('yi1', 'yi2'),
            outputs=('yo',),
            states=(),
            params=('Tpick', 'Tdrop'),
            unsupported_lines=(),
            module_name='typ_44__yi1_less_than_yi2_ip',
            module_filename='typ_44__yi1_less_than_yi2_ip.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='yi_greater_than_c_eps',
            typ_id='45',
            blkdef_name='yi greater than C _eps',
            sample_display_name='yi greater than C _eps',
            display_label='yi greater than C eps',
            category_path=('Native', 'Logic and Events', 'Comparators'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=('C', 'eps'),
            unsupported_lines=(),
            module_name='typ_45__yi_greater_than_c_eps',
            module_filename='typ_45__yi_greater_than_c_eps.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='yi_less_than_c_eps',
            typ_id='46',
            blkdef_name='yi less than C _eps',
            sample_display_name='yi less than C _eps',
            display_label='yi less than C eps',
            category_path=('Native', 'Logic and Events', 'Comparators'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=('C', 'eps'),
            unsupported_lines=(),
            module_name='typ_46__yi_less_than_c_eps',
            module_filename='typ_46__yi_less_than_c_eps.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='yi1_greater_than_yi2_eps',
            typ_id='47',
            blkdef_name='yi1 greater than yi2 _eps',
            sample_display_name='yi1 greater than yi2 _eps',
            display_label='yi1 greater than yi2 eps',
            category_path=('Native', 'Logic and Events', 'Comparators'),
            inputs=('yi1', 'yi2'),
            outputs=('yo',),
            states=(),
            params=('eps',),
            unsupported_lines=(),
            module_name='typ_47__yi1_greater_than_yi2_eps',
            module_filename='typ_47__yi1_greater_than_yi2_eps.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='yi1_less_than_yi2_eps',
            typ_id='48',
            blkdef_name='yi1 less than yi2 _eps',
            sample_display_name='yi1 less than yi2 _eps',
            display_label='yi1 less than yi2 eps',
            category_path=('Native', 'Logic and Events', 'Comparators'),
            inputs=('yi1', 'yi2'),
            outputs=('yo',),
            states=(),
            params=('eps',),
            unsupported_lines=(),
            module_name='typ_48__yi1_less_than_yi2_eps',
            module_filename='typ_48__yi1_less_than_yi2_eps.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='c_form_a',
            typ_id='49',
            blkdef_name='-C',
            sample_display_name='-C',
            display_label='-C',
            category_path=('Native', 'Math and Functions', 'Constants and Scaling'),
            inputs=(),
            outputs=('yo',),
            states=(),
            params=('C',),
            unsupported_lines=(),
            module_name='typ_49__c',
            module_filename='typ_49__c.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='0',
            typ_id='50',
            blkdef_name='0',
            sample_display_name='0',
            display_label='0',
            category_path=('Native', 'Math and Functions', 'Constants and Scaling'),
            inputs=(),
            outputs=('yo',),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_50__0',
            module_filename='typ_50__0.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1',
            typ_id='51',
            blkdef_name='1',
            sample_display_name='1',
            display_label='1',
            category_path=('Native', 'Math and Functions', 'Constants and Scaling'),
            inputs=(),
            outputs=('yo',),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_51__1',
            module_filename='typ_51__1.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_sqrt2',
            typ_id='52',
            blkdef_name='1/SQRT2',
            sample_display_name='1/SQRT2',
            display_label='1/SQRT2',
            category_path=('Native', 'Math and Functions', 'Constants and Scaling'),
            inputs=(),
            outputs=('yo',),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_52__1_sqrt2',
            module_filename='typ_52__1_sqrt2.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='2pi_form_a',
            typ_id='53',
            blkdef_name='2PI',
            sample_display_name='2PI',
            display_label='2PI [form A]',
            category_path=('Native', 'Math and Functions', 'Constants and Scaling'),
            inputs=(),
            outputs=('yo',),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_53__2pi',
            module_filename='typ_53__2pi.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='bias',
            typ_id='54',
            blkdef_name='Bias',
            sample_display_name='Bias',
            display_label='Bias',
            category_path=('Native', 'Math and Functions', 'Scaling and Products'),
            inputs=(),
            outputs=('yo',),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_54__bias',
            module_filename='typ_54__bias.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='c_form_b',
            typ_id='55',
            blkdef_name='C',
            sample_display_name='C',
            display_label='C [param: C; form A]',
            category_path=('Native', 'Math and Functions', 'Constants and Scaling'),
            inputs=(),
            outputs=('yo',),
            states=(),
            params=('C',),
            unsupported_lines=(),
            module_name='typ_55__c',
            module_filename='typ_55__c.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='c1_c2',
            typ_id='56',
            blkdef_name='C1/C2',
            sample_display_name='C1/C2',
            display_label='C1/C2',
            category_path=('Native', 'Math and Functions', 'Constants and Scaling'),
            inputs=(),
            outputs=('yo',),
            states=(),
            params=('C1', 'C2'),
            unsupported_lines=(),
            module_name='typ_56__c1_c2',
            module_filename='typ_56__c1_c2.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='e',
            typ_id='57',
            blkdef_name='E',
            sample_display_name='E',
            display_label='E',
            category_path=('Native', 'Math and Functions', 'Constants and Scaling'),
            inputs=(),
            outputs=('yo',),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_57__e',
            module_filename='typ_57__e.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='pi',
            typ_id='58',
            blkdef_name='PI',
            sample_display_name='PI',
            display_label='PI',
            category_path=('Native', 'Math and Functions', 'Constants and Scaling'),
            inputs=(),
            outputs=('yo',),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_58__pi',
            module_filename='typ_58__pi.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='pi_2',
            typ_id='59',
            blkdef_name='PI/2',
            sample_display_name='PI/2',
            display_label='PI/2',
            category_path=('Native', 'Math and Functions', 'Constants and Scaling'),
            inputs=(),
            outputs=('yo',),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_59__pi_2',
            module_filename='typ_59__pi_2.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='sqrt_2_3',
            typ_id='60',
            blkdef_name='SQRT(2/3)',
            sample_display_name='SQRT(2/3)',
            display_label='SQRT(2/3)',
            category_path=('Native', 'Math and Functions', 'Constants and Scaling'),
            inputs=(),
            outputs=('yo',),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_60__sqrt_2_3',
            module_filename='typ_60__sqrt_2_3.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='sqrt_3_2',
            typ_id='61',
            blkdef_name='SQRT(3/2)',
            sample_display_name='SQRT(3/2)',
            display_label='SQRT(3/2)',
            category_path=('Native', 'Math and Functions', 'Constants and Scaling'),
            inputs=(),
            outputs=('yo',),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_61__sqrt_3_2',
            module_filename='typ_61__sqrt_3_2.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='sqrt_c1_c2',
            typ_id='62',
            blkdef_name='SQRT(C1/C2)',
            sample_display_name='SQRT(C1/C2)',
            display_label='SQRT(C1/C2)',
            category_path=('Native', 'Math and Functions', 'Constants and Scaling'),
            inputs=(),
            outputs=('yo',),
            states=(),
            params=('C1', 'C2'),
            unsupported_lines=(),
            module_name='typ_62__sqrt_c1_c2',
            module_filename='typ_62__sqrt_c1_c2.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='sqrt2',
            typ_id='63',
            blkdef_name='SQRT2',
            sample_display_name='SQRT2',
            display_label='SQRT2',
            category_path=('Native', 'Math and Functions', 'Constants and Scaling'),
            inputs=(),
            outputs=('yo',),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_63__sqrt2',
            module_filename='typ_63__sqrt2.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='sqrt3',
            typ_id='64',
            blkdef_name='SQRT3',
            sample_display_name='SQRT3',
            display_label='SQRT3',
            category_path=('Native', 'Math and Functions', 'Constants and Scaling'),
            inputs=(),
            outputs=('yo',),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_64__sqrt3',
            module_filename='typ_64__sqrt3.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='aflipflop',
            typ_id='65',
            blkdef_name='aflipflop',
            sample_display_name='aflipflop',
            display_label='Analog flip-flop',
            category_path=('Native', 'Logic and Events', 'Gates and Memory'),
            inputs=('yi', 'set', 'rst'),
            outputs=('yo',),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_65__aflipflop',
            module_filename='typ_65__aflipflop.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='balanced',
            typ_id='66',
            blkdef_name='balanced',
            sample_display_name='balanced',
            display_label='balanced',
            category_path=('Native', 'Transforms', 'RMS and Sequence'),
            inputs=(),
            outputs=('yo',),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_66__balanced',
            module_filename='typ_66__balanced.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='delay',
            typ_id='67',
            blkdef_name='delay',
            sample_display_name='delay',
            display_label='delay',
            category_path=('Native', 'Continuous', 'Delays and Memory'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=('T',),
            unsupported_lines=(),
            module_name='typ_67__delay',
            module_filename='typ_67__delay.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='flipflop',
            typ_id='68',
            blkdef_name='flipflop',
            sample_display_name='flipflop',
            display_label='Flip-flop',
            category_path=('Native', 'Logic and Events', 'Gates and Memory'),
            inputs=('set', 'rst'),
            outputs=('yo',),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_68__flipflop',
            module_filename='typ_68__flipflop.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='gradlim_const',
            typ_id='69',
            blkdef_name='gradlim_const',
            sample_display_name='gradlim_const',
            display_label='Gradient limiter (constant)',
            category_path=('Native', 'Limits and Nonlinearities', 'Limiters'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=('gradmax', 'gradmin'),
            unsupported_lines=(),
            module_name='typ_69__gradlim_const',
            module_filename='typ_69__gradlim_const.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='invlapprox',
            typ_id='70',
            blkdef_name='invlapprox',
            sample_display_name='invlapprox',
            display_label='invlapprox',
            category_path=('Native', 'Lookup and Tables', 'Arrays and Matrices'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=('array_K',),
            unsupported_lines=('template_has_no_executable_content',),
            module_name='typ_70__invlapprox',
            module_filename='typ_70__invlapprox.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='lapprox',
            typ_id='71',
            blkdef_name='lapprox',
            sample_display_name='lapprox',
            display_label='lapprox',
            category_path=('Native', 'Lookup and Tables', 'Arrays and Matrices'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=('array_K',),
            unsupported_lines=('template_has_no_executable_content',),
            module_name='typ_71__lapprox',
            module_filename='typ_71__lapprox.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='lapprox2',
            typ_id='72',
            blkdef_name='lapprox2',
            sample_display_name='lapprox2',
            display_label='lapprox2',
            category_path=('Native', 'Lookup and Tables', 'Arrays and Matrices'),
            inputs=('row', 'col'),
            outputs=('yo',),
            states=(),
            params=('matrix_K',),
            unsupported_lines=('template_has_no_executable_content',),
            module_name='typ_72__lapprox2',
            module_filename='typ_72__lapprox2.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='lapproxext',
            typ_id='73',
            blkdef_name='lapproxext',
            sample_display_name='lapproxext',
            display_label='lapproxext',
            category_path=('Native', 'Lookup and Tables', 'Arrays and Matrices'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=('array_K',),
            unsupported_lines=('template_has_no_executable_content',),
            module_name='typ_73__lapproxext',
            module_filename='typ_73__lapproxext.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='lastvalue_form_a',
            typ_id='74',
            blkdef_name='lastvalue',
            sample_display_name='lastvalue',
            display_label='Last value [form A]',
            category_path=('Native', 'Continuous', 'Delays and Memory'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_74__lastvalue',
            module_filename='typ_74__lastvalue.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='lim',
            typ_id='75',
            blkdef_name='lim',
            sample_display_name='lim',
            display_label='lim',
            category_path=('Native', 'Limits and Nonlinearities', 'Limiters'),
            inputs=('yi', 'y_min', 'y_max'),
            outputs=('yo',),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_75__lim',
            module_filename='typ_75__lim.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='lim_const',
            typ_id='76',
            blkdef_name='lim_const',
            sample_display_name='lim_const',
            display_label='lim const',
            category_path=('Native', 'Limits and Nonlinearities', 'Limiters'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=('y_max', 'y_min'),
            unsupported_lines=(),
            module_name='typ_76__lim_const',
            module_filename='typ_76__lim_const.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='movingavg',
            typ_id='77',
            blkdef_name='movingavg',
            sample_display_name='movingavg',
            display_label='Moving average',
            category_path=('Native', 'Continuous', 'Delays and Memory'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=('Tdel', 'Tlength'),
            unsupported_lines=(),
            module_name='typ_77__movingavg',
            module_filename='typ_77__movingavg.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='picdro',
            typ_id='78',
            blkdef_name='picdro',
            sample_display_name='picdro',
            display_label='PI droop',
            category_path=('Native', 'Control and Measurement', 'Controllers'),
            inputs=('condition', 'Tpick', 'Tdrop'),
            outputs=('yo',),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_78__picdro',
            module_filename='typ_78__picdro.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='picdro_const',
            typ_id='79',
            blkdef_name='picdro_const',
            sample_display_name='picdro_const',
            display_label='PI droop (constant)',
            category_path=('Native', 'Control and Measurement', 'Controllers'),
            inputs=('condition',),
            outputs=('yo',),
            states=(),
            params=('Tpick', 'Tdrop'),
            unsupported_lines=(),
            module_name='typ_79__picdro_const',
            module_filename='typ_79__picdro_const.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='rms',
            typ_id='80',
            blkdef_name='rms',
            sample_display_name='rms',
            display_label='rms',
            category_path=('Native', 'Transforms', 'RMS and Sequence'),
            inputs=(),
            outputs=('yo',),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_80__rms',
            module_filename='typ_80__rms.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='sapprox',
            typ_id='81',
            blkdef_name='sapprox',
            sample_display_name='sapprox',
            display_label='sapprox',
            category_path=('Native', 'Lookup and Tables', 'Arrays and Matrices'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=('array_K',),
            unsupported_lines=('template_has_no_executable_content',),
            module_name='typ_81__sapprox',
            module_filename='typ_81__sapprox.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='sapprox2',
            typ_id='82',
            blkdef_name='sapprox2',
            sample_display_name='sapprox2',
            display_label='sapprox2',
            category_path=('Native', 'Lookup and Tables', 'Arrays and Matrices'),
            inputs=('row', 'col'),
            outputs=('yo',),
            states=(),
            params=('matrix_K',),
            unsupported_lines=('template_has_no_executable_content',),
            module_name='typ_82__sapprox2',
            module_filename='typ_82__sapprox2.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='select',
            typ_id='83',
            blkdef_name='select',
            sample_display_name='select',
            display_label='Selector',
            category_path=('Native', 'Logic and Events', 'Switching and Selection'),
            inputs=('condition', 'y_true', 'y_false'),
            outputs=('yo',),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_83__select',
            module_filename='typ_83__select.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='select_const',
            typ_id='84',
            blkdef_name='select_const',
            sample_display_name='select_const',
            display_label='Selector (constant)',
            category_path=('Native', 'Logic and Events', 'Switching and Selection'),
            inputs=('condition',),
            outputs=('yo',),
            states=(),
            params=('K_true', 'K_false'),
            unsupported_lines=(),
            module_name='typ_84__select_const',
            module_filename='typ_84__select_const.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='selfix',
            typ_id='85',
            blkdef_name='selfix',
            sample_display_name='selfix',
            display_label='Set if condition',
            category_path=('Native', 'Logic and Events', 'Switching and Selection'),
            inputs=('condition', 'y_true', 'y_false'),
            outputs=('yo',),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_85__selfix',
            module_filename='typ_85__selfix.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='selfix_const',
            typ_id='86',
            blkdef_name='selfix_const',
            sample_display_name='selfix_const',
            display_label='Set if condition (constant)',
            category_path=('Native', 'Logic and Events', 'Switching and Selection'),
            inputs=('condition',),
            outputs=('yo',),
            states=(),
            params=('K_true', 'K_false'),
            unsupported_lines=(),
            module_name='typ_86__selfix_const',
            module_filename='typ_86__selfix_const.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='time_form_a',
            typ_id='87',
            blkdef_name='time',
            sample_display_name='time',
            display_label='time',
            category_path=('Native', 'Waveforms and Time', 'Time Sources and Timers'),
            inputs=(),
            outputs=('yo',),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_87__time',
            module_filename='typ_87__time.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='backlash',
            typ_id='88',
            blkdef_name='Backlash',
            sample_display_name='Backlash',
            display_label='Backlash',
            category_path=('Native', 'Limits and Nonlinearities', 'Deadbands and Rate Limiters'),
            inputs=('yi',),
            outputs=('yo',),
            states=('Backlash__x',),
            params=('db',),
            unsupported_lines=(),
            module_name='typ_88__backlash',
            module_filename='typ_88__backlash.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='deadband_p',
            typ_id='89',
            blkdef_name='Deadband [p',
            sample_display_name='Deadband [p',
            display_label='Deadband (parameter)',
            category_path=('Native', 'Limits and Nonlinearities', 'Deadbands and Rate Limiters'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=('db', 'y_max', 'y_min'),
            unsupported_lines=(),
            module_name='typ_89__deadband_p',
            module_filename='typ_89__deadband_p.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='deadband_bypass',
            typ_id='90',
            blkdef_name='Deadband _bypass',
            sample_display_name='Deadband _bypass',
            display_label='Deadband (bypass)',
            category_path=('Native', 'Limits and Nonlinearities', 'Deadbands and Rate Limiters'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=('db',),
            unsupported_lines=(),
            module_name='typ_90__deadband_bypass',
            module_filename='typ_90__deadband_bypass.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='deadband_discontinuous',
            typ_id='91',
            blkdef_name='Deadband discontinuous',
            sample_display_name='Deadband discontinuous',
            display_label='Deadband discontinuous',
            category_path=('Native', 'Limits and Nonlinearities', 'Deadbands and Rate Limiters'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=('db',),
            unsupported_lines=(),
            module_name='typ_91__deadband_discontinuous',
            module_filename='typ_91__deadband_discontinuous.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='deadband_offset_p',
            typ_id='92',
            blkdef_name='Deadband offset [p',
            sample_display_name='Deadband offset [p',
            display_label='Deadband offset (parameter)',
            category_path=('Native', 'Limits and Nonlinearities', 'Deadbands and Rate Limiters'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=('db', 'y_max', 'y_min'),
            unsupported_lines=(),
            module_name='typ_92__deadband_offset_p',
            module_filename='typ_92__deadband_offset_p.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='deadband_offset_bypass',
            typ_id='93',
            blkdef_name='Deadband offset _bypass',
            sample_display_name='Deadband offset _bypass',
            display_label='Deadband offset (bypass)',
            category_path=('Native', 'Limits and Nonlinearities', 'Deadbands and Rate Limiters'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=('db',),
            unsupported_lines=(),
            module_name='typ_93__deadband_offset_bypass',
            module_filename='typ_93__deadband_offset_bypass.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='deadband_stepped_p',
            typ_id='94',
            blkdef_name='Deadband stepped [p',
            sample_display_name='Deadband stepped [p',
            display_label='Deadband stepped (parameter)',
            category_path=('Native', 'Limits and Nonlinearities', 'Deadbands and Rate Limiters'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=('db', 'y_max', 'y_min'),
            unsupported_lines=(),
            module_name='typ_94__deadband_stepped_p',
            module_filename='typ_94__deadband_stepped_p.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='deadband_stepped_bypass',
            typ_id='95',
            blkdef_name='Deadband stepped _bypass',
            sample_display_name='Deadband stepped _bypass',
            display_label='Deadband stepped (bypass)',
            category_path=('Native', 'Limits and Nonlinearities', 'Deadbands and Rate Limiters'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=('db',),
            unsupported_lines=(),
            module_name='typ_95__deadband_stepped_bypass',
            module_filename='typ_95__deadband_stepped_bypass.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='deadband',
            typ_id='96',
            blkdef_name='Deadband',
            sample_display_name='Deadband',
            display_label='Deadband',
            category_path=('Native', 'Limits and Nonlinearities', 'Deadbands and Rate Limiters'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=('db',),
            unsupported_lines=(),
            module_name='typ_96__deadband',
            module_filename='typ_96__deadband.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='ke_st_bypass_incforward',
            typ_id='97',
            blkdef_name='Ke^-sT _bypass_incforward',
            sample_display_name='Ke^-sT _bypass_incforward',
            display_label='Ke^-sT (bypass) incforward',
            category_path=('Native', 'Continuous', 'Delays and Memory'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=('K', 'T'),
            unsupported_lines=(),
            module_name='typ_97__ke_st_bypass_incforward',
            module_filename='typ_97__ke_st_bypass_incforward.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='ke_st_incforward',
            typ_id='98',
            blkdef_name='Ke^-sT _incforward',
            sample_display_name='Ke^-sT _incforward',
            display_label='Ke^-sT (forward increment)',
            category_path=('Native', 'Continuous', 'Delays and Memory'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=('K', 'T'),
            unsupported_lines=(),
            module_name='typ_98__ke_st_incforward',
            module_filename='typ_98__ke_st_incforward.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='pade_approximant_r12_incbackward',
            typ_id='99',
            blkdef_name='Pade approximant R12 _incbackward',
            sample_display_name='Pade approximant R12 _incbackward',
            display_label='Pade approximant R12 (backward increment)',
            category_path=('Native', 'Continuous', 'Delays and Memory'),
            inputs=('yi',),
            outputs=('yo',),
            states=('Pade approximant R12 _incbackward__x1', 'Pade approximant R12 _incbackward__x2'),
            params=('Td',),
            unsupported_lines=(),
            module_name='typ_99__pade_approximant_r12_incbackward',
            module_filename='typ_99__pade_approximant_r12_incbackward.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='pade_approximant_r12_incforward',
            typ_id='100',
            blkdef_name='Pade approximant R12 _incforward',
            sample_display_name='Pade approximant R12 _incforward',
            display_label='Pade approximant R12 (forward increment)',
            category_path=('Native', 'Continuous', 'Delays and Memory'),
            inputs=('yi',),
            outputs=('yo',),
            states=('Pade approximant R12 _incforward__x1', 'Pade approximant R12 _incforward__x2'),
            params=('Td',),
            unsupported_lines=(),
            module_name='typ_100__pade_approximant_r12_incforward',
            module_filename='typ_100__pade_approximant_r12_incforward.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='e_s0_01_incforward',
            typ_id='101',
            blkdef_name='e^-s0.01 _incforward',
            sample_display_name='e^-s0.01 _incforward',
            display_label='e^-s0.01 (forward increment)',
            category_path=('Native', 'Continuous', 'Delays and Memory'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_101__e_s0_01_incforward',
            module_filename='typ_101__e_s0_01_incforward.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='e_st_bypass',
            typ_id='102',
            blkdef_name='e^-sT _bypass',
            sample_display_name='e^-sT _bypass',
            display_label='e^-sT (bypass)',
            category_path=('Native', 'Continuous', 'Delays and Memory'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=('T',),
            unsupported_lines=(),
            module_name='typ_102__e_st_bypass',
            module_filename='typ_102__e_st_bypass.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='e_st_bypass_incbackward',
            typ_id='103',
            blkdef_name='e^-sT _bypass_incbackward',
            sample_display_name='e^-sT _bypass_incbackward',
            display_label='e^-sT (bypass) incbackward',
            category_path=('Native', 'Continuous', 'Delays and Memory'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=('T',),
            unsupported_lines=(),
            module_name='typ_103__e_st_bypass_incbackward',
            module_filename='typ_103__e_st_bypass_incbackward.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='e_st_bypass_incforward',
            typ_id='104',
            blkdef_name='e^-sT _bypass_incforward',
            sample_display_name='e^-sT _bypass_incforward',
            display_label='e^-sT (bypass) incforward',
            category_path=('Native', 'Continuous', 'Delays and Memory'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=('T',),
            unsupported_lines=(),
            module_name='typ_104__e_st_bypass_incforward',
            module_filename='typ_104__e_st_bypass_incforward.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='e_st_incbackward',
            typ_id='105',
            blkdef_name='e^-sT _incbackward',
            sample_display_name='e^-sT _incbackward',
            display_label='e^-sT (backward increment)',
            category_path=('Native', 'Continuous', 'Delays and Memory'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=('T',),
            unsupported_lines=(),
            module_name='typ_105__e_st_incbackward',
            module_filename='typ_105__e_st_incbackward.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='e_st_incforward',
            typ_id='106',
            blkdef_name='e^-sT _incforward',
            sample_display_name='e^-sT _incforward',
            display_label='e^-sT (forward increment)',
            category_path=('Native', 'Continuous', 'Delays and Memory'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=('T',),
            unsupported_lines=(),
            module_name='typ_106__e_st_incforward',
            module_filename='typ_106__e_st_incforward.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='lastvalue_incbackward',
            typ_id='107',
            blkdef_name='lastvalue _incbackward',
            sample_display_name='lastvalue _incbackward',
            display_label='lastvalue (backward increment)',
            category_path=('Native', 'Continuous', 'Delays and Memory'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_107__lastvalue_incbackward',
            module_filename='typ_107__lastvalue_incbackward.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='lastvalue_incforward',
            typ_id='108',
            blkdef_name='lastvalue _incforward',
            sample_display_name='lastvalue _incforward',
            display_label='lastvalue (forward increment)',
            category_path=('Native', 'Continuous', 'Delays and Memory'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_108__lastvalue_incforward',
            module_filename='typ_108__lastvalue_incforward.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='lastvalue_form_b',
            typ_id='109',
            blkdef_name='lastvalue',
            sample_display_name='lastvalue',
            display_label='Last value [form B]',
            category_path=('Native', 'Continuous', 'Delays and Memory'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_109__lastvalue',
            module_filename='typ_109__lastvalue.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='s_1_st',
            typ_id='110',
            blkdef_name='s/(1+sT)',
            sample_display_name='s/(1+sT)',
            display_label='s/(1+sT)',
            category_path=('Native', 'Continuous', 'Integrators and Derivatives'),
            inputs=('yi',),
            outputs=('yo',),
            states=('s/(1+sT)__x',),
            params=('T',),
            unsupported_lines=(),
            module_name='typ_110__s_1_st',
            module_filename='typ_110__s_1_st.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='sk_1_0_01s',
            typ_id='111',
            blkdef_name='sK/(1+0.01s)',
            sample_display_name='sK/(1+0.01s)',
            display_label='sK/(1+0.01s)',
            category_path=('Native', 'Control and Measurement', 'Controllers'),
            inputs=('yi',),
            outputs=('yo',),
            states=('sK/(1+0.01s)__x',),
            params=('K',),
            unsupported_lines=(),
            module_name='typ_111__sk_1_0_01s',
            module_filename='typ_111__sk_1_0_01s.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='sk_1_st_fb',
            typ_id='112',
            blkdef_name='sK/(1+sT) _fb',
            sample_display_name='sK/(1+sT) _fb',
            display_label='sK/(1+sT) (feedback)',
            category_path=('Native', 'Control and Measurement', 'Controllers'),
            inputs=('yi',),
            outputs=('yo',),
            states=('sK/(1+sT) _fb__x',),
            params=('K', 'T'),
            unsupported_lines=(),
            module_name='typ_112__sk_1_st_fb',
            module_filename='typ_112__sk_1_st_fb.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='sk_1_st',
            typ_id='113',
            blkdef_name='sK/(1+sT)',
            sample_display_name='sK/(1+sT)',
            display_label='sK/(1+sT)',
            category_path=('Native', 'Control and Measurement', 'Controllers'),
            inputs=('yi',),
            outputs=('yo',),
            states=('sK/(1+sT)__x',),
            params=('K', 'T'),
            unsupported_lines=(),
            module_name='typ_113__sk_1_st',
            module_filename='typ_113__sk_1_st.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='el_power',
            typ_id='114',
            blkdef_name='El. Power',
            sample_display_name='El. Power',
            display_label='El. Power',
            category_path=('Native', 'Control and Measurement', 'Measurements and Units'),
            inputs=('pgt', 'cosn'),
            outputs=('pelec',),
            states=(),
            params=('IPB',),
            unsupported_lines=(),
            module_name='typ_114__el_power',
            module_filename='typ_114__el_power.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='pq_calculator',
            typ_id='115',
            blkdef_name='PQ Calculator',
            sample_display_name='PQ Calculator',
            display_label='PQ Calculator',
            category_path=('Native', 'Control and Measurement', 'Measurements and Units'),
            inputs=('ur', 'ui', 'ir', 'ii'),
            outputs=('P', 'Q'),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_115__pq_calculator',
            module_filename='typ_115__pq_calculator.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='power_base',
            typ_id='116',
            blkdef_name='Power_base',
            sample_display_name='Power_base',
            display_label='Power base',
            category_path=('Native', 'Control and Measurement', 'Measurements and Units'),
            inputs=('pg', 'sgnn', 'cosn'),
            outputs=('pelec',),
            states=(),
            params=('PN',),
            unsupported_lines=(),
            module_name='typ_116__power_base',
            module_filename='typ_116__power_base.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='h0w0_q_s_w0_2_sw0_q_s_2',
            typ_id='117',
            blkdef_name='(H0w0/Q)s/(w0^2+sw0/Q+s^2)',
            sample_display_name='(H0w0/Q)s/(w0^2+sw0/Q+s^2)',
            display_label='(H0w0/Q)s/(w0^2+sw0/Q+s^2)',
            category_path=('Native', 'Continuous', 'Transfer Functions and Filters'),
            inputs=('yi',),
            outputs=('yo',),
            states=('(H0w0/Q)s/(w0^2+sw0/Q+s^2)__x1', '(H0w0/Q)s/(w0^2+sw0/Q+s^2)__x2'),
            params=('Flow', 'Fhigh', 'H0'),
            unsupported_lines=(),
            module_name='typ_117__h0w0_q_s_w0_2_sw0_q_s_2',
            module_filename='typ_117__h0w0_q_s_w0_2_sw0_q_s_2.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='s_w0_2_s_2',
            typ_id='118',
            blkdef_name='s/(w0^2+s^2)',
            sample_display_name='s/(w0^2+s^2)',
            display_label='s/(w0^2+s^2)',
            category_path=('Native', 'Continuous', 'Integrators and Derivatives'),
            inputs=('yi',),
            outputs=('yo',),
            states=('s/(w0^2+s^2)__x1', 's/(w0^2+s^2)__x2'),
            params=('f0',),
            unsupported_lines=(),
            module_name='typ_118__s_w0_2_s_2',
            module_filename='typ_118__s_w0_2_s_2.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='st_1_st_bypass_form_a',
            typ_id='119',
            blkdef_name='-sT/(1+sT) _bypass',
            sample_display_name='-sT/(1+sT) _bypass',
            display_label='-sT/(1+sT) (bypass)',
            category_path=('Native', 'Continuous', 'Integrators and Derivatives'),
            inputs=('yi',),
            outputs=('yo',),
            states=('-sT/(1+sT) _bypass__x',),
            params=('T',),
            unsupported_lines=(),
            module_name='typ_119__st_1_st_bypass',
            module_filename='typ_119__st_1_st_bypass.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='st_1_st',
            typ_id='120',
            blkdef_name='-sT/(1+sT)',
            sample_display_name='-sT/(1+sT)',
            display_label='-sT/(1+sT)',
            category_path=('Native', 'Continuous', 'Integrators and Derivatives'),
            inputs=('yi',),
            outputs=('yo',),
            states=('-sT/(1+sT)__x',),
            params=('T',),
            unsupported_lines=(),
            module_name='typ_120__st_1_st',
            module_filename='typ_120__st_1_st.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='skt_1_st',
            typ_id='121',
            blkdef_name='sKT/(1+sT)',
            sample_display_name='sKT/(1+sT)',
            display_label='sKT/(1+sT)',
            category_path=('Native', 'Continuous', 'Transfer Functions and Filters'),
            inputs=('yi',),
            outputs=('yo',),
            states=('sKT/(1+sT)__x',),
            params=('K', 'T'),
            unsupported_lines=(),
            module_name='typ_121__skt_1_st',
            module_filename='typ_121__skt_1_st.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='sktd_1_st',
            typ_id='122',
            blkdef_name='sKTd/(1+sT)',
            sample_display_name='sKTd/(1+sT)',
            display_label='sKTd/(1+sT)',
            category_path=('Native', 'Continuous', 'Transfer Functions and Filters'),
            inputs=('yi',),
            outputs=('yo',),
            states=('sKTd/(1+sT)__x',),
            params=('K', 'Td', 'T'),
            unsupported_lines=(),
            module_name='typ_122__sktd_1_st',
            module_filename='typ_122__sktd_1_st.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='st_1_st_bypass_form_b',
            typ_id='123',
            blkdef_name='sT/(1+sT) _bypass',
            sample_display_name='sT/(1+sT) _bypass',
            display_label='sT/(1+sT) (bypass)',
            category_path=('Native', 'Continuous', 'Integrators and Derivatives'),
            inputs=('yi',),
            outputs=('yo',),
            states=('sT/(1+sT) _bypass__x',),
            params=('T',),
            unsupported_lines=(),
            module_name='typ_123__st_1_st_bypass',
            module_filename='typ_123__st_1_st_bypass.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='st_1_st_enable',
            typ_id='124',
            blkdef_name='sT/(1+sT) _enable',
            sample_display_name='sT/(1+sT) _enable',
            display_label='sT/(1+sT) (enable)',
            category_path=('Native', 'Logic and Events', 'Timers and Enables'),
            inputs=('yi',),
            outputs=('yo',),
            states=('sT/(1+sT) _enable__x',),
            params=('T',),
            unsupported_lines=(),
            module_name='typ_124__st_1_st_enable',
            module_filename='typ_124__st_1_st_enable.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='stb_1_sta_fb',
            typ_id='125',
            blkdef_name='sTb/(1+sTa) _fb',
            sample_display_name='sTb/(1+sTa) _fb',
            display_label='sTb/(1+sTa) (feedback)',
            category_path=('Native', 'Continuous', 'Transfer Functions and Filters'),
            inputs=('yi',),
            outputs=('yo',),
            states=('sTb/(1+sTa) _fb__x',),
            params=('Tb', 'Ta'),
            unsupported_lines=(),
            module_name='typ_125__stb_1_sta_fb',
            module_filename='typ_125__stb_1_sta_fb.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='stld_1_stlg_fb',
            typ_id='126',
            blkdef_name='sTld/(1+sTlg) _fb',
            sample_display_name='sTld/(1+sTlg) _fb',
            display_label='sTld/(1+sTlg) (feedback)',
            category_path=('Native', 'Continuous', 'Transfer Functions and Filters'),
            inputs=('yi',),
            outputs=('yo',),
            states=('sTld/(1+sTlg) _fb__x',),
            params=('Tld', 'Tlg'),
            unsupported_lines=(),
            module_name='typ_126__stld_1_stlg_fb',
            module_filename='typ_126__stld_1_stlg_fb.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_k_1_st_bypass_form_a',
            typ_id='127',
            blkdef_name='(1-K)/(1+sT) _bypass',
            sample_display_name='(1-K)/(1+sT) _bypass',
            display_label='(1-K)/(1+sT) (bypass)',
            category_path=('Native', 'Continuous', 'Transfer Functions and Filters'),
            inputs=('yi',),
            outputs=('yo',),
            states=('(1-K)/(1+sT) _bypass__x',),
            params=('K', 'T'),
            unsupported_lines=(),
            module_name='typ_127__1_k_1_st_bypass',
            module_filename='typ_127__1_k_1_st_bypass.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_k_1_st',
            typ_id='128',
            blkdef_name='(1-K)/(1+sT)',
            sample_display_name='(1-K)/(1+sT)',
            display_label='(1-K)/(1+sT)',
            category_path=('Native', 'Continuous', 'Transfer Functions and Filters'),
            inputs=('yi',),
            outputs=('yo',),
            states=('(1-K)/(1+sT)__x',),
            params=('K', 'T'),
            unsupported_lines=(),
            module_name='typ_128__1_k_1_st',
            module_filename='typ_128__1_k_1_st.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_1_st_p_form_a',
            typ_id='129',
            blkdef_name='1/(1+sT) (p)',
            sample_display_name='1/(1+sT) (p)',
            display_label='1/(1+sT) (parameter) [param: T/y_max; 1 state]',
            category_path=('Native', 'Continuous', 'Transfer Functions and Filters'),
            inputs=('yi',),
            outputs=('yo',),
            states=('1/(1+sT) (p)__x',),
            params=('T', 'y_max'),
            unsupported_lines=(),
            module_name='typ_129__1_1_st_p',
            module_filename='typ_129__1_1_st_p.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_1_st_p_form_b',
            typ_id='130',
            blkdef_name='1/(1+sT) (p',
            sample_display_name='1/(1+sT) (p',
            display_label='1/(1+sT) (parameter input) [1 input; param: T/y_max/r_max+2; 1 state]',
            category_path=('Native', 'Continuous', 'Transfer Functions and Filters'),
            inputs=('yi',),
            outputs=('yo',),
            states=('1/(1+sT) (p__x',),
            params=('T', 'y_max', 'r_max', 'y_min', 'r_min'),
            unsupported_lines=(),
            module_name='typ_130__1_1_st_p',
            module_filename='typ_130__1_1_st_p.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_1_st_s_form_a',
            typ_id='131',
            blkdef_name='1/(1+sT) (s)',
            sample_display_name='1/(1+sT) (s)',
            display_label='1/(1+sT) (signal)',
            category_path=('Native', 'Continuous', 'Transfer Functions and Filters'),
            inputs=('yi', 'y_max'),
            outputs=('yo',),
            states=('1/(1+sT) (s)__x',),
            params=('T',),
            unsupported_lines=(),
            module_name='typ_131__1_1_st_s',
            module_filename='typ_131__1_1_st_s.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_1_st_s_form_b',
            typ_id='132',
            blkdef_name='1/(1+sT) (s',
            sample_display_name='1/(1+sT) (s',
            display_label='1/(1+sT) (signal input) [signal: y_max/y_min; param: T; 1 state]',
            category_path=('Native', 'Continuous', 'Transfer Functions and Filters'),
            inputs=('yi', 'y_max', 'y_min'),
            outputs=('yo',),
            states=('1/(1+sT) (s__x',),
            params=('T',),
            unsupported_lines=(),
            module_name='typ_132__1_1_st_s',
            module_filename='typ_132__1_1_st_s.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_1_st_p_form_c',
            typ_id='133',
            blkdef_name='1/(1+sT) [(p',
            sample_display_name='1/(1+sT) [(p',
            display_label='1/(1+sT) (parameter input) [1 input; param: T/y_max/y_min; 1 state]',
            category_path=('Native', 'Continuous', 'Transfer Functions and Filters'),
            inputs=('yi',),
            outputs=('yo',),
            states=('1/(1+sT) [(p__x',),
            params=('T', 'y_max', 'y_min'),
            unsupported_lines=(),
            module_name='typ_133__1_1_st_p',
            module_filename='typ_133__1_1_st_p.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_1_st_bypass',
            typ_id='134',
            blkdef_name='1/(1+sT) _bypass',
            sample_display_name='1/(1+sT) _bypass',
            display_label='1/(1+sT) (bypass)',
            category_path=('Native', 'Continuous', 'Transfer Functions and Filters'),
            inputs=('yi',),
            outputs=('yo',),
            states=('1/(1+sT) _bypass__x',),
            params=('T',),
            unsupported_lines=(),
            module_name='typ_134__1_1_st_bypass',
            module_filename='typ_134__1_1_st_bypass.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_1_st_enable',
            typ_id='135',
            blkdef_name='1/(1+sT) _enable',
            sample_display_name='1/(1+sT) _enable',
            display_label='1/(1+sT) (enable)',
            category_path=('Native', 'Logic and Events', 'Timers and Enables'),
            inputs=('yi', 'enable'),
            outputs=('yo',),
            states=('1/(1+sT) _enable__x',),
            params=('T',),
            unsupported_lines=(),
            module_name='typ_135__1_1_st_enable',
            module_filename='typ_135__1_1_st_enable.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_1_st_and_sx',
            typ_id='136',
            blkdef_name='1/(1+sT) and sx',
            sample_display_name='1/(1+sT) and sx',
            display_label='1/(1+sT) and sx',
            category_path=('Native', 'Continuous', 'Transfer Functions and Filters'),
            inputs=('yi',),
            outputs=('yo', 'dx'),
            states=('1/(1+sT) and sx__x',),
            params=('T',),
            unsupported_lines=(),
            module_name='typ_136__1_1_st_and_sx',
            module_filename='typ_136__1_1_st_and_sx.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_1_st_p_form_d',
            typ_id='137',
            blkdef_name='1/(1+sT) {p',
            sample_display_name='1/(1+sT) {p',
            display_label='1/(1+sT) (parameter) [param: T/rup/rdown; 1 state]',
            category_path=('Native', 'Continuous', 'Transfer Functions and Filters'),
            inputs=('yi',),
            outputs=('yo',),
            states=('1/(1+sT) {p__x',),
            params=('T', 'rup', 'rdown'),
            unsupported_lines=(),
            module_name='typ_137__1_1_st_p',
            module_filename='typ_137__1_1_st_p.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_1_st',
            typ_id='138',
            blkdef_name='1/(1+sT)',
            sample_display_name='1/(1+sT)',
            display_label='1/(1+sT)',
            category_path=('Native', 'Continuous', 'Transfer Functions and Filters'),
            inputs=('yi',),
            outputs=('yo',),
            states=('1/(1+sT)__x',),
            params=('T',),
            unsupported_lines=(),
            module_name='typ_138__1_1_st',
            module_filename='typ_138__1_1_st.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_1_st_2',
            typ_id='139',
            blkdef_name='1/(1+sT/2)',
            sample_display_name='1/(1+sT/2)',
            display_label='1/(1+sT/2)',
            category_path=('Native', 'Continuous', 'Transfer Functions and Filters'),
            inputs=('yi',),
            outputs=('yo',),
            states=('1/(1+sT/2)__x',),
            params=('T',),
            unsupported_lines=(),
            module_name='typ_139__1_1_st_2',
            module_filename='typ_139__1_1_st_2.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_k_st_bypass',
            typ_id='140',
            blkdef_name='1/(K+sT) _bypass',
            sample_display_name='1/(K+sT) _bypass',
            display_label='1/(K+sT) (bypass)',
            category_path=('Native', 'Continuous', 'Transfer Functions and Filters'),
            inputs=('yi',),
            outputs=('yo',),
            states=('1/(K+sT) _bypass__x',),
            params=('K', 'T'),
            unsupported_lines=(),
            module_name='typ_140__1_k_st_bypass',
            module_filename='typ_140__1_k_st_bypass.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_k_st_form_a',
            typ_id='141',
            blkdef_name='1/(K+sT)',
            sample_display_name='1/(K+sT)',
            display_label='1/(K+sT)',
            category_path=('Native', 'Continuous', 'Transfer Functions and Filters'),
            inputs=('yi',),
            outputs=('yo',),
            states=('1/(K+sT)__x',),
            params=('K', 'T'),
            unsupported_lines=(),
            module_name='typ_141__1_k_st',
            module_filename='typ_141__1_k_st.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_k_t1_t2_1_1_1_st2',
            typ_id='142',
            blkdef_name='1/K(T1/T2-1)(1/(1+sT2))',
            sample_display_name='1/K(T1/T2-1)(1/(1+sT2))',
            display_label='1/K(T1/T2-1)(1/(1+sT2))',
            category_path=('Native', 'Continuous', 'Transfer Functions and Filters'),
            inputs=('yi',),
            outputs=('yo',),
            states=('1/K(T1/T2-1)(1/(1+sT2))__x',),
            params=('K', 'T1', 'T2'),
            unsupported_lines=(),
            module_name='typ_142__1_k_t1_t2_1_1_1_st2',
            module_filename='typ_142__1_k_t1_t2_1_1_1_st2.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_k_1_st_bypass_form_b',
            typ_id='143',
            blkdef_name='1/K/(1+sT) _bypass',
            sample_display_name='1/K/(1+sT) _bypass',
            display_label='1/K/(1+sT) (bypass)',
            category_path=('Native', 'Control and Measurement', 'Controllers'),
            inputs=('yi',),
            outputs=('yo',),
            states=('1/K/(1+sT) _bypass__x',),
            params=('K', 'T'),
            unsupported_lines=(),
            module_name='typ_143__1_k_1_st_bypass',
            module_filename='typ_143__1_k_1_st_bypass.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='butterworth_2nd_order',
            typ_id='144',
            blkdef_name='Butterworth 2nd order',
            sample_display_name='Butterworth 2nd order',
            display_label='Butterworth 2nd order',
            category_path=('Native', 'Continuous', 'Transfer Functions and Filters'),
            inputs=('yi',),
            outputs=('yo',),
            states=('Butterworth 2nd order__x1', 'Butterworth 2nd order__x2'),
            params=('wc',),
            unsupported_lines=(),
            module_name='typ_144__butterworth_2nd_order',
            module_filename='typ_144__butterworth_2nd_order.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='butterworth_3rd_order',
            typ_id='145',
            blkdef_name='Butterworth 3rd order',
            sample_display_name='Butterworth 3rd order',
            display_label='Butterworth 3rd order',
            category_path=('Native', 'Continuous', 'Transfer Functions and Filters'),
            inputs=('yi',),
            outputs=('yo',),
            states=('Butterworth 3rd order__x1', 'Butterworth 3rd order__x2', 'Butterworth 3rd order__x3'),
            params=('wc',),
            unsupported_lines=(),
            module_name='typ_145__butterworth_3rd_order',
            module_filename='typ_145__butterworth_3rd_order.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='k_1_st_p_form_a',
            typ_id='146',
            blkdef_name='K/(1+sT) (p',
            sample_display_name='K/(1+sT) (p',
            display_label='K/(1+sT) (parameter input) [signal: y_max; param: K/T/y_min; 1 state]',
            category_path=('Native', 'Control and Measurement', 'Controllers'),
            inputs=('yi', 'y_max'),
            outputs=('yo',),
            states=('K/(1+sT) (p__x',),
            params=('K', 'T', 'y_min'),
            unsupported_lines=(),
            module_name='typ_146__k_1_st_p',
            module_filename='typ_146__k_1_st_p.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='k_1_st_s',
            typ_id='147',
            blkdef_name='K/(1+sT) (s',
            sample_display_name='K/(1+sT) (s',
            display_label='K/(1+sT) (signal input)',
            category_path=('Native', 'Control and Measurement', 'Controllers'),
            inputs=('yi', 'y_max', 'y_min'),
            outputs=('yo',),
            states=('K/(1+sT) (s__x',),
            params=('K', 'T'),
            unsupported_lines=(),
            module_name='typ_147__k_1_st_s',
            module_filename='typ_147__k_1_st_s.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='k_1_st_sp',
            typ_id='148',
            blkdef_name='K/(1+sT) (sp',
            sample_display_name='K/(1+sT) (sp',
            display_label='K/(1+sT) (sp',
            category_path=('Native', 'Control and Measurement', 'Controllers'),
            inputs=('yi', 'ylim'),
            outputs=('yo',),
            states=('K/(1+sT) (sp__x',),
            params=('K', 'T', 'y_max', 'y_min'),
            unsupported_lines=(),
            module_name='typ_148__k_1_st_sp',
            module_filename='typ_148__k_1_st_sp.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='k_1_st_p_form_b',
            typ_id='149',
            blkdef_name='K/(1+sT) [(p',
            sample_display_name='K/(1+sT) [(p',
            display_label='K/(1+sT) (parameter input) [1 input; param: K/T/y_max+1; 1 state]',
            category_path=('Native', 'Control and Measurement', 'Controllers'),
            inputs=('yi',),
            outputs=('yo',),
            states=('K/(1+sT) [(p__x',),
            params=('K', 'T', 'y_max', 'y_min'),
            unsupported_lines=(),
            module_name='typ_149__k_1_st_p',
            module_filename='typ_149__k_1_st_p.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='k_1_st_bypass',
            typ_id='150',
            blkdef_name='K/(1+sT) _bypass',
            sample_display_name='K/(1+sT) _bypass',
            display_label='K/(1+sT) (bypass)',
            category_path=('Native', 'Control and Measurement', 'Controllers'),
            inputs=('yi',),
            outputs=('yo',),
            states=('K/(1+sT) _bypass__x',),
            params=('K', 'T'),
            unsupported_lines=(),
            module_name='typ_150__k_1_st_bypass',
            module_filename='typ_150__k_1_st_bypass.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='k_1_st',
            typ_id='151',
            blkdef_name='K/(1+sT)',
            sample_display_name='K/(1+sT)',
            display_label='K/(1+sT)',
            category_path=('Native', 'Control and Measurement', 'Controllers'),
            inputs=('yi',),
            outputs=('yo',),
            states=('K/(1+sT)__x',),
            params=('K', 'T'),
            unsupported_lines=(),
            module_name='typ_151__k_1_st',
            module_filename='typ_151__k_1_st.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='k1_k2_1_st',
            typ_id='152',
            blkdef_name='K1 + K2/(1+sT)',
            sample_display_name='K1 + K2/(1+sT)',
            display_label='K1 + K2/(1+sT)',
            category_path=('Native', 'Continuous', 'Transfer Functions and Filters'),
            inputs=('yi',),
            outputs=('yo',),
            states=('K1 + K2/(1+sT)__x',),
            params=('K1', 'K2', 'T'),
            unsupported_lines=(),
            module_name='typ_152__k1_k2_1_st',
            module_filename='typ_152__k1_k2_1_st.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='kt_1_st',
            typ_id='153',
            blkdef_name='KT/(1+sT)',
            sample_display_name='KT/(1+sT)',
            display_label='KT/(1+sT)',
            category_path=('Native', 'Continuous', 'Transfer Functions and Filters'),
            inputs=('yi',),
            outputs=('yo',),
            states=('KT/(1+sT)__x',),
            params=('K', 'T'),
            unsupported_lines=(),
            module_name='typ_153__kt_1_st',
            module_filename='typ_153__kt_1_st.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_1_st_p_rst_hold',
            typ_id='154',
            blkdef_name='1/(1+sT) (p) _rst_hold',
            sample_display_name='1/(1+sT) (p) _rst_hold',
            display_label='1/(1+sT) (parameter) (reset hold)',
            category_path=('Native', 'Continuous', 'Transfer Functions and Filters'),
            inputs=('yi', 'hold', 'rst'),
            outputs=('yo',),
            states=('1/(1+sT) (p) _rst_hold__x',),
            params=('T', 'y_max'),
            unsupported_lines=(),
            module_name='typ_154__1_1_st_p_rst_hold',
            module_filename='typ_154__1_1_st_p_rst_hold.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_1_st_p_form_e',
            typ_id='155',
            blkdef_name='1/(1+sT) (p',
            sample_display_name='1/(1+sT) (p',
            display_label='1/(1+sT) (parameter input) [signal: hold/rst; param: T/y_max/r_max+2; 1 state]',
            category_path=('Native', 'Continuous', 'Transfer Functions and Filters'),
            inputs=('yi', 'hold', 'rst'),
            outputs=('yo',),
            states=('1/(1+sT) (p__x',),
            params=('T', 'y_max', 'r_max', 'y_min', 'r_min'),
            unsupported_lines=(),
            module_name='typ_155__1_1_st_p',
            module_filename='typ_155__1_1_st_p.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_1_st_s_rst_hold',
            typ_id='156',
            blkdef_name='1/(1+sT) (s) _rst_hold',
            sample_display_name='1/(1+sT) (s) _rst_hold',
            display_label='1/(1+sT) (signal) (reset hold)',
            category_path=('Native', 'Continuous', 'Transfer Functions and Filters'),
            inputs=('yi', 'hold', 'y_max', 'rst'),
            outputs=('yo',),
            states=('1/(1+sT) (s) _rst_hold__x',),
            params=('T',),
            unsupported_lines=(),
            module_name='typ_156__1_1_st_s_rst_hold',
            module_filename='typ_156__1_1_st_s_rst_hold.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_1_st_s_form_c',
            typ_id='157',
            blkdef_name='1/(1+sT) (s',
            sample_display_name='1/(1+sT) (s',
            display_label='1/(1+sT) (signal input) [signal: hold/y_max/rst+1; param: T; 1 state]',
            category_path=('Native', 'Continuous', 'Transfer Functions and Filters'),
            inputs=('yi', 'hold', 'y_max', 'rst', 'y_min'),
            outputs=('yo',),
            states=('1/(1+sT) (s__x',),
            params=('T',),
            unsupported_lines=(),
            module_name='typ_157__1_1_st_s',
            module_filename='typ_157__1_1_st_s.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_1_st_p_form_f',
            typ_id='158',
            blkdef_name='1/(1+sT) [(p',
            sample_display_name='1/(1+sT) [(p',
            display_label='1/(1+sT) (parameter input) [signal: hold/rst; param: T/y_max/y_min; 1 state]',
            category_path=('Native', 'Continuous', 'Transfer Functions and Filters'),
            inputs=('yi', 'hold', 'rst'),
            outputs=('yo',),
            states=('1/(1+sT) [(p__x',),
            params=('T', 'y_max', 'y_min'),
            unsupported_lines=(),
            module_name='typ_158__1_1_st_p',
            module_filename='typ_158__1_1_st_p.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_1_st_rst_hold',
            typ_id='159',
            blkdef_name='1/(1+sT) _rst_hold',
            sample_display_name='1/(1+sT) _rst_hold',
            display_label='1/(1+sT) (reset hold)',
            category_path=('Native', 'Continuous', 'Transfer Functions and Filters'),
            inputs=('yi', 'hold', 'rst'),
            outputs=('yo',),
            states=('1/(1+sT) _rst_hold__x',),
            params=('T',),
            unsupported_lines=(),
            module_name='typ_159__1_1_st_rst_hold',
            module_filename='typ_159__1_1_st_rst_hold.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='butterworth_2nd_order_rst_hold',
            typ_id='160',
            blkdef_name='Butterworth 2nd order _rst_hold',
            sample_display_name='Butterworth 2nd order _rst_hold',
            display_label='Butterworth 2nd order (reset hold)',
            category_path=('Native', 'Continuous', 'Transfer Functions and Filters'),
            inputs=('yi', 'hold', 'rst'),
            outputs=('yo',),
            states=('Butterworth 2nd order _rst_hold__x1', 'Butterworth 2nd order _rst_hold__x2'),
            params=('wc',),
            unsupported_lines=(),
            module_name='typ_160__butterworth_2nd_order_rst_hold',
            module_filename='typ_160__butterworth_2nd_order_rst_hold.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='butterworth_3rd_order_rst_hold',
            typ_id='161',
            blkdef_name='Butterworth 3rd order _rst_hold',
            sample_display_name='Butterworth 3rd order _rst_hold',
            display_label='Butterworth 3rd order (reset hold)',
            category_path=('Native', 'Continuous', 'Transfer Functions and Filters'),
            inputs=('yi', 'hold', 'rst'),
            outputs=('yo',),
            states=('Butterworth 3rd order _rst_hold__x1', 'Butterworth 3rd order _rst_hold__x2', 'Butterworth 3rd order _rst_hold__x3'),
            params=('wc',),
            unsupported_lines=(),
            module_name='typ_161__butterworth_3rd_order_rst_hold',
            module_filename='typ_161__butterworth_3rd_order_rst_hold.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_1_st_p_rst_sig_hold',
            typ_id='162',
            blkdef_name='1/(1+sT) (p) _rst_sig_hold',
            sample_display_name='1/(1+sT) (p) _rst_sig_hold',
            display_label='1/(1+sT) (parameter) (reset signal hold)',
            category_path=('Native', 'Continuous', 'Transfer Functions and Filters'),
            inputs=('yi', 'hold', 'x_rst', 'rst'),
            outputs=('yo',),
            states=('1/(1+sT) (p) _rst_sig_hold__x',),
            params=('T', 'y_max'),
            unsupported_lines=(),
            module_name='typ_162__1_1_st_p_rst_sig_hold',
            module_filename='typ_162__1_1_st_p_rst_sig_hold.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_1_st_p_form_g',
            typ_id='163',
            blkdef_name='1/(1+sT) (p',
            sample_display_name='1/(1+sT) (p',
            display_label='1/(1+sT) (parameter input) [signal: hold/x_rst/rst; param: T/y_max/r_max+2; 1 state]',
            category_path=('Native', 'Continuous', 'Transfer Functions and Filters'),
            inputs=('yi', 'hold', 'x_rst', 'rst'),
            outputs=('yo',),
            states=('1/(1+sT) (p__x',),
            params=('T', 'y_max', 'r_max', 'y_min', 'r_min'),
            unsupported_lines=(),
            module_name='typ_163__1_1_st_p',
            module_filename='typ_163__1_1_st_p.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_1_st_s_rst_sig_hold',
            typ_id='164',
            blkdef_name='1/(1+sT) (s) _rst_sig_hold',
            sample_display_name='1/(1+sT) (s) _rst_sig_hold',
            display_label='1/(1+sT) (signal) (reset signal hold)',
            category_path=('Native', 'Continuous', 'Transfer Functions and Filters'),
            inputs=('yi', 'hold', 'x_rst', 'y_max', 'rst'),
            outputs=('yo',),
            states=('1/(1+sT) (s) _rst_sig_hold__x',),
            params=('T',),
            unsupported_lines=(),
            module_name='typ_164__1_1_st_s_rst_sig_hold',
            module_filename='typ_164__1_1_st_s_rst_sig_hold.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_1_st_s_form_d',
            typ_id='165',
            blkdef_name='1/(1+sT) (s',
            sample_display_name='1/(1+sT) (s',
            display_label='1/(1+sT) (signal input) [signal: hold/x_rst/y_max+2; param: T; 1 state]',
            category_path=('Native', 'Continuous', 'Transfer Functions and Filters'),
            inputs=('yi', 'hold', 'x_rst', 'y_max', 'rst', 'y_min'),
            outputs=('yo',),
            states=('1/(1+sT) (s__x',),
            params=('T',),
            unsupported_lines=(),
            module_name='typ_165__1_1_st_s',
            module_filename='typ_165__1_1_st_s.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_1_st_p_form_h',
            typ_id='166',
            blkdef_name='1/(1+sT) [(p',
            sample_display_name='1/(1+sT) [(p',
            display_label='1/(1+sT) (parameter input) [signal: hold/x_rst/rst; param: T/y_max/y_min; 1 state]',
            category_path=('Native', 'Continuous', 'Transfer Functions and Filters'),
            inputs=('yi', 'hold', 'x_rst', 'rst'),
            outputs=('yo',),
            states=('1/(1+sT) [(p__x',),
            params=('T', 'y_max', 'y_min'),
            unsupported_lines=(),
            module_name='typ_166__1_1_st_p',
            module_filename='typ_166__1_1_st_p.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_1_st_rst_sig_hold',
            typ_id='167',
            blkdef_name='1/(1+sT) _rst_sig_hold',
            sample_display_name='1/(1+sT) _rst_sig_hold',
            display_label='1/(1+sT) (reset signal hold)',
            category_path=('Native', 'Continuous', 'Transfer Functions and Filters'),
            inputs=('yi', 'hold', 'x_rst', 'rst'),
            outputs=('yo',),
            states=('1/(1+sT) _rst_sig_hold__x',),
            params=('T',),
            unsupported_lines=(),
            module_name='typ_167__1_1_st_rst_sig_hold',
            module_filename='typ_167__1_1_st_rst_sig_hold.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='multiply_1_form_a',
            typ_id='168',
            blkdef_name='Multiply (-1)',
            sample_display_name='Multiply (-1)',
            display_label='Multiply (-1)',
            category_path=('Native', 'Math and Functions', 'Scaling and Products'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_168__multiply_1',
            module_filename='typ_168__multiply_1.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='multiply_k_form_a',
            typ_id='169',
            blkdef_name='Multiply (-K)',
            sample_display_name='Multiply (-K)',
            display_label='Multiply (-K)',
            category_path=('Native', 'Math and Functions', 'Scaling and Products'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=('K',),
            unsupported_lines=(),
            module_name='typ_169__multiply_k',
            module_filename='typ_169__multiply_k.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='multiply_1_k_form_a',
            typ_id='170',
            blkdef_name='Multiply (1-K)',
            sample_display_name='Multiply (1-K)',
            display_label='Multiply (1-K)',
            category_path=('Native', 'Math and Functions', 'Scaling and Products'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=('K',),
            unsupported_lines=(),
            module_name='typ_170__multiply_1_k',
            module_filename='typ_170__multiply_1_k.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='multiply_1_k1_k2',
            typ_id='171',
            blkdef_name='Multiply (1-K1-K2)',
            sample_display_name='Multiply (1-K1-K2)',
            display_label='Multiply (1-K1-K2)',
            category_path=('Native', 'Math and Functions', 'Scaling and Products'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=('K1', 'K2'),
            unsupported_lines=(),
            module_name='typ_171__multiply_1_k1_k2',
            module_filename='typ_171__multiply_1_k1_k2.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='multiply_1_form_b',
            typ_id='172',
            blkdef_name='Multiply 1',
            sample_display_name='Multiply 1',
            display_label='Multiply 1',
            category_path=('Native', 'Math and Functions', 'Scaling and Products'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_172__multiply_1',
            module_filename='typ_172__multiply_1.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='multiply_1_k_p',
            typ_id='173',
            blkdef_name='Multiply 1/K [p',
            sample_display_name='Multiply 1/K [p',
            display_label='Multiply 1/K (parameter)',
            category_path=('Native', 'Math and Functions', 'Scaling and Products'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=('K', 'y_max', 'y_min'),
            unsupported_lines=(),
            module_name='typ_173__multiply_1_k_p',
            module_filename='typ_173__multiply_1_k_p.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='multiply_1_k_form_b',
            typ_id='174',
            blkdef_name='Multiply 1/K',
            sample_display_name='Multiply 1/K',
            display_label='Multiply 1/K',
            category_path=('Native', 'Math and Functions', 'Scaling and Products'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=('K',),
            unsupported_lines=(),
            module_name='typ_174__multiply_1_k',
            module_filename='typ_174__multiply_1_k.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='multiply_1_k1k2_p',
            typ_id='175',
            blkdef_name='Multiply 1/K1K2 [p',
            sample_display_name='Multiply 1/K1K2 [p',
            display_label='Multiply 1/K1K2 (parameter)',
            category_path=('Native', 'Math and Functions', 'Scaling and Products'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=('K1', 'K2', 'y_max', 'y_min'),
            unsupported_lines=(),
            module_name='typ_175__multiply_1_k1k2_p',
            module_filename='typ_175__multiply_1_k1k2_p.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='multiply_1_sqrt2',
            typ_id='176',
            blkdef_name='Multiply 1/SQRT2',
            sample_display_name='Multiply 1/SQRT2',
            display_label='Multiply 1/SQRT2',
            category_path=('Native', 'Continuous', 'Transfer Functions and Filters'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_176__multiply_1_sqrt2',
            module_filename='typ_176__multiply_1_sqrt2.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='multiply_1_sqrt3',
            typ_id='177',
            blkdef_name='Multiply 1/SQRT3',
            sample_display_name='Multiply 1/SQRT3',
            display_label='Multiply 1/SQRT3',
            category_path=('Native', 'Continuous', 'Transfer Functions and Filters'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_177__multiply_1_sqrt3',
            module_filename='typ_177__multiply_1_sqrt3.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='multiply_k_p',
            typ_id='178',
            blkdef_name='Multiply K [p',
            sample_display_name='Multiply K [p',
            display_label='Multiply K (parameter)',
            category_path=('Native', 'Math and Functions', 'Scaling and Products'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=('K', 'y_max', 'y_min'),
            unsupported_lines=(),
            module_name='typ_178__multiply_k_p',
            module_filename='typ_178__multiply_k_p.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='multiply_k_form_b',
            typ_id='179',
            blkdef_name='Multiply K',
            sample_display_name='Multiply K',
            display_label='Multiply K',
            category_path=('Native', 'Math and Functions', 'Scaling and Products'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=('K',),
            unsupported_lines=(),
            module_name='typ_179__multiply_k',
            module_filename='typ_179__multiply_k.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='multiply_k1_k2_k3_form_a',
            typ_id='180',
            blkdef_name='Multiply K1 K2 / K3',
            sample_display_name='Multiply K1 K2 / K3',
            display_label='Multiply K1 K2 / K3',
            category_path=('Native', 'Math and Functions', 'Scaling and Products'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=('K1', 'K2', 'K3'),
            unsupported_lines=(),
            module_name='typ_180__multiply_k1_k2_k3',
            module_filename='typ_180__multiply_k1_k2_k3.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='multiply_k1_k2_k3_form_b',
            typ_id='181',
            blkdef_name='Multiply K1 K2 K3',
            sample_display_name='Multiply K1 K2 K3',
            display_label='Multiply K1 K2 K3',
            category_path=('Native', 'Math and Functions', 'Scaling and Products'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=('K1', 'K2', 'K3'),
            unsupported_lines=(),
            module_name='typ_181__multiply_k1_k2_k3',
            module_filename='typ_181__multiply_k1_k2_k3.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='multiply_k1_k2_form_a',
            typ_id='182',
            blkdef_name='Multiply K1 K2',
            sample_display_name='Multiply K1 K2',
            display_label='Multiply K1 K2',
            category_path=('Native', 'Math and Functions', 'Scaling and Products'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=('K1', 'K2'),
            unsupported_lines=(),
            module_name='typ_182__multiply_k1_k2',
            module_filename='typ_182__multiply_k1_k2.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='multiply_k1_k2_form_b',
            typ_id='183',
            blkdef_name='Multiply K1/K2',
            sample_display_name='Multiply K1/K2',
            display_label='Multiply K1/K2',
            category_path=('Native', 'Math and Functions', 'Scaling and Products'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=('K1', 'K2'),
            unsupported_lines=(),
            module_name='typ_183__multiply_k1_k2',
            module_filename='typ_183__multiply_k1_k2.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='multiply_pi',
            typ_id='184',
            blkdef_name='Multiply PI',
            sample_display_name='Multiply PI',
            display_label='Multiply PI',
            category_path=('Native', 'Control and Measurement', 'Controllers'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_184__multiply_pi',
            module_filename='typ_184__multiply_pi.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='multiply_sqrt_2_3',
            typ_id='185',
            blkdef_name='Multiply SQRT(2/3)',
            sample_display_name='Multiply SQRT(2/3)',
            display_label='Multiply SQRT(2/3)',
            category_path=('Native', 'Continuous', 'Transfer Functions and Filters'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_185__multiply_sqrt_2_3',
            module_filename='typ_185__multiply_sqrt_2_3.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='multiply_sqrt_3_2',
            typ_id='186',
            blkdef_name='Multiply SQRT(3/2)',
            sample_display_name='Multiply SQRT(3/2)',
            display_label='Multiply SQRT(3/2)',
            category_path=('Native', 'Continuous', 'Transfer Functions and Filters'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_186__multiply_sqrt_3_2',
            module_filename='typ_186__multiply_sqrt_3_2.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='multiply_sqrt_k1_k2',
            typ_id='187',
            blkdef_name='Multiply SQRT(K1/K2)',
            sample_display_name='Multiply SQRT(K1/K2)',
            display_label='Multiply SQRT(K1/K2)',
            category_path=('Native', 'Continuous', 'Transfer Functions and Filters'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=('K1', 'K2'),
            unsupported_lines=(),
            module_name='typ_187__multiply_sqrt_k1_k2',
            module_filename='typ_187__multiply_sqrt_k1_k2.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='multiply_sqrt2',
            typ_id='188',
            blkdef_name='Multiply SQRT2',
            sample_display_name='Multiply SQRT2',
            display_label='Multiply SQRT2',
            category_path=('Native', 'Math and Functions', 'Scaling and Products'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_188__multiply_sqrt2',
            module_filename='typ_188__multiply_sqrt2.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='multiply_sqrt3',
            typ_id='189',
            blkdef_name='Multiply SQRT3',
            sample_display_name='Multiply SQRT3',
            display_label='Multiply SQRT3',
            category_path=('Native', 'Math and Functions', 'Scaling and Products'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_189__multiply_sqrt3',
            module_filename='typ_189__multiply_sqrt3.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_b1s_b2ss_1_a1s_a2ss_bypass',
            typ_id='190',
            blkdef_name='(1+B1s+B2ss)/(1+A1s+A2ss) _bypass',
            sample_display_name='(1+B1s+B2ss)/(1+A1s+A2ss) _bypass',
            display_label='(1+B1s+B2ss)/(1+A1s+A2ss) (bypass)',
            category_path=('Native', 'Continuous', 'Transfer Functions and Filters'),
            inputs=('yi',),
            outputs=('yo',),
            states=('(1+B1s+B2ss)/(1+A1s+A2ss) _bypass__x1', '(1+B1s+B2ss)/(1+A1s+A2ss) _bypass__x2'),
            params=('A1', 'A2', 'B1', 'B2'),
            unsupported_lines=(),
            module_name='typ_190__1_b1s_b2ss_1_a1s_a2ss_bypass',
            module_filename='typ_190__1_b1s_b2ss_1_a1s_a2ss_bypass.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_kstc_1_sta_1_stb_1_stc_bypass',
            typ_id='191',
            blkdef_name='(1+KsTc)/((1+sTa)(1+sTb)(1+sTc)) _bypass',
            sample_display_name='(1+KsTc)/((1+sTa)(1+sTb)(1+sTc)) _bypass',
            display_label='(1+KsTc)/((1+sTa)(1+sTb)(1+sTc)) (bypass)',
            category_path=('Native', 'Control and Measurement', 'Controllers'),
            inputs=('yi',),
            outputs=('yo',),
            states=('(1+KsTc)/((1+sTa)(1+sTb)(1+sTc)) _bypass__xa', '(1+KsTc)/((1+sTa)(1+sTb)(1+sTc)) _bypass__xb', '(1+KsTc)/((1+sTa)(1+sTb)(1+sTc)) _bypass__xc'),
            params=('Ta', 'Tb', 'Tc', 'K'),
            unsupported_lines=(),
            module_name='typ_191__1_kstc_1_sta_1_stb_1_stc_bypass',
            module_filename='typ_191__1_kstc_1_sta_1_stb_1_stc_bypass.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_b1s_b2ss_1_a1s_a2ss',
            typ_id='192',
            blkdef_name='(1+b1s+b2ss)/(1+a1s+a2ss)',
            sample_display_name='(1+b1s+b2ss)/(1+a1s+a2ss)',
            display_label='(1+b1s+b2ss)/(1+a1s+a2ss)',
            category_path=('Native', 'Continuous', 'Transfer Functions and Filters'),
            inputs=('yi',),
            outputs=('yo',),
            states=('(1+b1s+b2ss)/(1+a1s+a2ss)__x1', '(1+b1s+b2ss)/(1+a1s+a2ss)__x2'),
            params=('a1', 'a2', 'b1', 'b2'),
            unsupported_lines=(),
            module_name='typ_192__1_b1s_b2ss_1_a1s_a2ss',
            module_filename='typ_192__1_b1s_b2ss_1_a1s_a2ss.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_st3_1_st1_sst1t2_bypass',
            typ_id='193',
            blkdef_name='(1+sT3)/(1+sT1+ssT1T2) _bypass',
            sample_display_name='(1+sT3)/(1+sT1+ssT1T2) _bypass',
            display_label='(1+sT3)/(1+sT1+ssT1T2) (bypass)',
            category_path=('Native', 'Continuous', 'Transfer Functions and Filters'),
            inputs=('yi',),
            outputs=('yo',),
            states=('(1+sT3)/(1+sT1+ssT1T2) _bypass__x1', '(1+sT3)/(1+sT1+ssT1T2) _bypass__x2'),
            params=('T1', 'T2', 'T3'),
            unsupported_lines=(),
            module_name='typ_193__1_st3_1_st1_sst1t2_bypass',
            module_filename='typ_193__1_st3_1_st1_sst1t2_bypass.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_st3_sst4_1_st1_sst2',
            typ_id='194',
            blkdef_name='(1+sT3+ssT4)/(1+sT1+ssT2)',
            sample_display_name='(1+sT3+ssT4)/(1+sT1+ssT2)',
            display_label='(1+sT3+ssT4)/(1+sT1+ssT2)',
            category_path=('Native', 'Continuous', 'Transfer Functions and Filters'),
            inputs=('yi',),
            outputs=('yo',),
            states=('(1+sT3+ssT4)/(1+sT1+ssT2)__x1', '(1+sT3+ssT4)/(1+sT1+ssT2)__x2'),
            params=('T1', 'T2', 'T3', 'T4'),
            unsupported_lines=(),
            module_name='typ_194__1_st3_sst4_1_st1_sst2',
            module_filename='typ_194__1_st3_sst4_1_st1_sst2.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_stb_sta_2_1_sta_4',
            typ_id='195',
            blkdef_name='(1+sTb)(sTa)^2/(1+sTa)^4',
            sample_display_name='(1+sTb)(sTa)^2/(1+sTa)^4',
            display_label='(1+sTb)(sTa)^2/(1+sTa)^4',
            category_path=('Native', 'Continuous', 'Transfer Functions and Filters'),
            inputs=('yi',),
            outputs=('yo',),
            states=('(1+sTb)(sTa)^2/(1+sTa)^4__x1', '(1+sTb)(sTa)^2/(1+sTa)^4__x2', '(1+sTb)(sTa)^2/(1+sTa)^4__x3', '(1+sTb)(sTa)^2/(1+sTa)^4__x4'),
            params=('Tb', 'Ta'),
            unsupported_lines=(),
            module_name='typ_195__1_stb_sta_2_1_sta_4',
            module_filename='typ_195__1_stb_sta_2_1_sta_4.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_sst3_1_st1_sst2_bypass',
            typ_id='196',
            blkdef_name='(1+ssT3)/(1+sT1+ssT2) _bypass',
            sample_display_name='(1+ssT3)/(1+sT1+ssT2) _bypass',
            display_label='(1+ssT3)/(1+sT1+ssT2) (bypass)',
            category_path=('Native', 'Continuous', 'Transfer Functions and Filters'),
            inputs=('yi',),
            outputs=('yo',),
            states=('(1+ssT3)/(1+sT1+ssT2) _bypass__x1', '(1+ssT3)/(1+sT1+ssT2) _bypass__x2'),
            params=('T1', 'T2', 'T3'),
            unsupported_lines=(),
            module_name='typ_196__1_sst3_1_st1_sst2_bypass',
            module_filename='typ_196__1_sst3_1_st1_sst2_bypass.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='a0_sa1_ssa2_b0_sb1_ssb2_bypass',
            typ_id='197',
            blkdef_name='(A0+sA1+ssA2)/(B0+sB1+ssB2) _bypass',
            sample_display_name='(A0+sA1+ssA2)/(B0+sB1+ssB2) _bypass',
            display_label='(A0+sA1+ssA2)/(B0+sB1+ssB2) (bypass)',
            category_path=('Native', 'Continuous', 'Transfer Functions and Filters'),
            inputs=('yi',),
            outputs=('yo',),
            states=('(A0+sA1+ssA2)/(B0+sB1+ssB2) _bypass__x1', '(A0+sA1+ssA2)/(B0+sB1+ssB2) _bypass__x2'),
            params=('B0', 'B1', 'B2', 'A0', 'A1', 'A2'),
            unsupported_lines=(),
            module_name='typ_197__a0_sa1_ssa2_b0_sb1_ssb2_bypass',
            module_filename='typ_197__a0_sa1_ssa2_b0_sb1_ssb2_bypass.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='ss_ass_bs_1_bypass',
            typ_id='198',
            blkdef_name='(ss)/(Ass+Bs+1) _bypass',
            sample_display_name='(ss)/(Ass+Bs+1) _bypass',
            display_label='(ss)/(Ass+Bs+1) (bypass)',
            category_path=('Native', 'Continuous', 'Transfer Functions and Filters'),
            inputs=('yi',),
            outputs=('yo',),
            states=('(ss)/(Ass+Bs+1) _bypass__x1', '(ss)/(Ass+Bs+1) _bypass__x2'),
            params=('A', 'B'),
            unsupported_lines=(),
            module_name='typ_198__ss_ass_bs_1_bypass',
            module_filename='typ_198__ss_ass_bs_1_bypass.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='ss_ww_ss_sb_ww_bypass',
            typ_id='199',
            blkdef_name='(ss+ww)/(ss+sB+ww) _bypass',
            sample_display_name='(ss+ww)/(ss+sB+ww) _bypass',
            display_label='(ss+ww)/(ss+sB+ww) (bypass)',
            category_path=('Native', 'Continuous', 'Transfer Functions and Filters'),
            inputs=('yi',),
            outputs=('yo',),
            states=('(ss+ww)/(ss+sB+ww) _bypass__x1', '(ss+ww)/(ss+sB+ww) _bypass__x2'),
            params=('B', 'w'),
            unsupported_lines=(),
            module_name='typ_199__ss_ww_ss_sb_ww_bypass',
            module_filename='typ_199__ss_ww_ss_sb_ww_bypass.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_1_s_2_x_zeta_wc_ss_wc_x_wc',
            typ_id='200',
            blkdef_name='1/(1+s(2 x zeta)/wc+ ss/(wc x wc))',
            sample_display_name='1/(1+s(2 x zeta)/wc+ ss/(wc x wc))',
            display_label='1/(1+s(2 x zeta)/wc+ ss/(wc x wc))',
            category_path=('Native', 'Continuous', 'Transfer Functions and Filters'),
            inputs=('yi',),
            outputs=('yo',),
            states=('1/(1+s(2 x zeta)/wc+ ss/(wc x wc))__x1', '1/(1+s(2 x zeta)/wc+ ss/(wc x wc))__x2'),
            params=('wc', 'zeta'),
            unsupported_lines=(),
            module_name='typ_200__1_1_s_2_x_zeta_wc_ss_wc_x_wc',
            module_filename='typ_200__1_1_s_2_x_zeta_wc_ss_wc_x_wc.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_1_st1_sst2_bypass',
            typ_id='201',
            blkdef_name='1/(1+sT1+ssT2) _bypass',
            sample_display_name='1/(1+sT1+ssT2) _bypass',
            display_label='1/(1+sT1+ssT2) (bypass)',
            category_path=('Native', 'Continuous', 'Transfer Functions and Filters'),
            inputs=('yi',),
            outputs=('yo',),
            states=('1/(1+sT1+ssT2) _bypass__x1', '1/(1+sT1+ssT2) _bypass__x2'),
            params=('T1', 'T2'),
            unsupported_lines=(),
            module_name='typ_201__1_1_st1_sst2_bypass',
            module_filename='typ_201__1_1_st1_sst2_bypass.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='k_1_st1_1_st2_s_1_st3_p',
            typ_id='202',
            blkdef_name='K(1+sT1)(1+sT2)/(s(1+sT3)) [(p',
            sample_display_name='K(1+sT1)(1+sT2)/(s(1+sT3)) [(p',
            display_label='K(1+sT1)(1+sT2)/(s(1+sT3)) (parameter input)',
            category_path=('Native', 'Control and Measurement', 'Controllers'),
            inputs=('yi',),
            outputs=('yo',),
            states=('K(1+sT1)(1+sT2)/(s(1+sT3)) [(p__x1', 'K(1+sT1)(1+sT2)/(s(1+sT3)) [(p__x2'),
            params=('K', 'T1', 'T2', 'T3', 'y_max', 'y_min'),
            unsupported_lines=(),
            module_name='typ_202__k_1_st1_1_st2_s_1_st3_p',
            module_filename='typ_202__k_1_st1_1_st2_s_1_st3_p.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='k_1_std_1_sta_1_stb_s_p',
            typ_id='203',
            blkdef_name='K(1+sTd)/((1+sTa)(1+sTb)s) (p',
            sample_display_name='K(1+sTd)/((1+sTa)(1+sTb)s) (p',
            display_label='K(1+sTd)/((1+sTa)(1+sTb)s) (parameter input)',
            category_path=('Native', 'Control and Measurement', 'Controllers'),
            inputs=('yi',),
            outputs=('yo',),
            states=('K(1+sTd)/((1+sTa)(1+sTb)s) (p__xa', 'K(1+sTd)/((1+sTa)(1+sTb)s) (p__xb', 'K(1+sTd)/((1+sTa)(1+sTb)s) (p__xc'),
            params=('K', 'Td', 'Ta', 'Tb', 'y_max', 'y_min'),
            unsupported_lines=(),
            module_name='typ_203__k_1_std_1_sta_1_stb_s_p',
            module_filename='typ_203__k_1_std_1_sta_1_stb_s_p.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='e_std_1_st1_1_st1',
            typ_id='204',
            blkdef_name='e(-sTd)/((1+sT1)(1+sT1))',
            sample_display_name='e(-sTd)/((1+sT1)(1+sT1))',
            display_label='e(-sTd)/((1+sT1)(1+sT1))',
            category_path=('Native', 'Continuous', 'Transfer Functions and Filters'),
            inputs=('yi',),
            outputs=('yo',),
            states=('e(-sTd)/((1+sT1)(1+sT1))__x1', 'e(-sTd)/((1+sT1)(1+sT1))__x2'),
            params=('T1', 'T2', 'Td'),
            unsupported_lines=(),
            module_name='typ_204__e_std_1_st1_1_st1',
            module_filename='typ_204__e_std_1_st1_1_st1.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='s_2k_1_st_2',
            typ_id='205',
            blkdef_name='s^2K/(1+sT)^2',
            sample_display_name='s^2K/(1+sT)^2',
            display_label='s^2K/(1+sT)^2',
            category_path=('Native', 'Control and Measurement', 'Controllers'),
            inputs=('yi',),
            outputs=('yo',),
            states=('s^2K/(1+sT)^2__x1', 's^2K/(1+sT)^2__x2'),
            params=('K', 'T'),
            unsupported_lines=(),
            module_name='typ_205__s_2k_1_st_2',
            module_filename='typ_205__s_2k_1_st_2.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_s_p_form_a',
            typ_id='206',
            blkdef_name='1/s (p',
            sample_display_name='1/s (p',
            display_label='1/s (parameter input) [1 input; param: y_max/y_min; 1 state]',
            category_path=('Native', 'Continuous', 'Integrators and Derivatives'),
            inputs=('yi',),
            outputs=('yo',),
            states=('1/s (p__x',),
            params=('y_max', 'y_min'),
            unsupported_lines=(),
            module_name='typ_206__1_s_p',
            module_filename='typ_206__1_s_p.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_s_s_form_a',
            typ_id='207',
            blkdef_name='1/s (s',
            sample_display_name='1/s (s',
            display_label='1/s (signal input) [signal: hold/y_max/y_min; 1 state]',
            category_path=('Native', 'Continuous', 'Integrators and Derivatives'),
            inputs=('yi', 'hold', 'y_max', 'y_min'),
            outputs=('yo',),
            states=('1/s (s__x',),
            params=(),
            unsupported_lines=(),
            module_name='typ_207__1_s_s',
            module_filename='typ_207__1_s_s.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_s_p_form_b',
            typ_id='208',
            blkdef_name='1/s [p',
            sample_display_name='1/s [p',
            display_label='1/s (parameter) [1 input; param: y_max/y_min; 1 state]',
            category_path=('Native', 'Continuous', 'Integrators and Derivatives'),
            inputs=('yi',),
            outputs=('yo',),
            states=('1/s [p__x',),
            params=('y_max', 'y_min'),
            unsupported_lines=(),
            module_name='typ_208__1_s_p',
            module_filename='typ_208__1_s_p.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_s_p_form_c',
            typ_id='209',
            blkdef_name='1/s [p]',
            sample_display_name='1/s [p]',
            display_label='1/s (parameter) [1 input; param: y_max; 1 state]',
            category_path=('Native', 'Continuous', 'Integrators and Derivatives'),
            inputs=('yi',),
            outputs=('yo',),
            states=('1/s [p]__x',),
            params=('y_max',),
            unsupported_lines=(),
            module_name='typ_209__1_s_p',
            module_filename='typ_209__1_s_p.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_s_s_form_b',
            typ_id='210',
            blkdef_name='1/s [s',
            sample_display_name='1/s [s',
            display_label='1/s (signal) [signal: y_max/y_min; 1 state]',
            category_path=('Native', 'Continuous', 'Integrators and Derivatives'),
            inputs=('yi', 'y_max', 'y_min'),
            outputs=('yo',),
            states=('1/s [s__x',),
            params=(),
            unsupported_lines=(),
            module_name='typ_210__1_s_s',
            module_filename='typ_210__1_s_s.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_s_s_form_c',
            typ_id='211',
            blkdef_name='1/s [s]',
            sample_display_name='1/s [s]',
            display_label='1/s (signal) [signal: y_max; 1 state]',
            category_path=('Native', 'Continuous', 'Integrators and Derivatives'),
            inputs=('yi', 'y_max'),
            outputs=('yo',),
            states=('1/s [s]__x',),
            params=(),
            unsupported_lines=(),
            module_name='typ_211__1_s_s',
            module_filename='typ_211__1_s_s.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_s_enable',
            typ_id='212',
            blkdef_name='1/s _enable',
            sample_display_name='1/s _enable',
            display_label='1/s (enable)',
            category_path=('Native', 'Logic and Events', 'Timers and Enables'),
            inputs=('yi', 'hold'),
            outputs=('yo',),
            states=('1/s _enable__x',),
            params=(),
            unsupported_lines=(),
            module_name='typ_212__1_s_enable',
            module_filename='typ_212__1_s_enable.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_s_incfreeze',
            typ_id='213',
            blkdef_name='1/s _incfreeze',
            sample_display_name='1/s _incfreeze',
            display_label='1/s (freeze)',
            category_path=('Native', 'Continuous', 'Integrators and Derivatives'),
            inputs=('yi',),
            outputs=('yo',),
            states=('1/s _incfreeze__x',),
            params=('Tincfreeze',),
            unsupported_lines=(),
            module_name='typ_213__1_s_incfreeze',
            module_filename='typ_213__1_s_incfreeze.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_s',
            typ_id='214',
            blkdef_name='1/s',
            sample_display_name='1/s',
            display_label='1/s',
            category_path=('Native', 'Continuous', 'Integrators and Derivatives'),
            inputs=('yi',),
            outputs=('yo',),
            states=('1/s__x',),
            params=(),
            unsupported_lines=(),
            module_name='typ_214__1_s',
            module_filename='typ_214__1_s.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_st_p_fb',
            typ_id='215',
            blkdef_name='1/sT (p) _fb',
            sample_display_name='1/sT (p) _fb',
            display_label='1/sT (parameter) (feedback)',
            category_path=('Native', 'Continuous', 'Integrators and Derivatives'),
            inputs=('yi',),
            outputs=('yo',),
            states=('1/sT (p) _fb__x',),
            params=('T', 'y_max'),
            unsupported_lines=(),
            module_name='typ_215__1_st_p_fb',
            module_filename='typ_215__1_st_p_fb.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_st_p_form_a',
            typ_id='216',
            blkdef_name='1/sT (p)',
            sample_display_name='1/sT (p)',
            display_label='1/sT (parameter) [1 input; param: T/y_max; 1 state]',
            category_path=('Native', 'Continuous', 'Integrators and Derivatives'),
            inputs=('yi',),
            outputs=('yo',),
            states=('1/sT (p)__x',),
            params=('T', 'y_max'),
            unsupported_lines=(),
            module_name='typ_216__1_st_p',
            module_filename='typ_216__1_st_p.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_st_p_form_b',
            typ_id='217',
            blkdef_name='1/sT (p',
            sample_display_name='1/sT (p',
            display_label='1/sT (parameter input) [1 input; param: T/y_min; 1 state; form A]',
            category_path=('Native', 'Continuous', 'Integrators and Derivatives'),
            inputs=('yi',),
            outputs=('yo',),
            states=('1/sT (p__x',),
            params=('T', 'y_min'),
            unsupported_lines=(),
            module_name='typ_217__1_st_p',
            module_filename='typ_217__1_st_p.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_st_p_form_c',
            typ_id='218',
            blkdef_name='1/sT (p',
            sample_display_name='1/sT (p',
            display_label='1/sT (parameter input) [1 input; param: T/y_min; 1 state; form B]',
            category_path=('Native', 'Continuous', 'Integrators and Derivatives'),
            inputs=('yi',),
            outputs=('yo',),
            states=('1/sT (p__x',),
            params=('T', 'y_min'),
            unsupported_lines=(),
            module_name='typ_218__1_st_p',
            module_filename='typ_218__1_st_p.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_st_p_form_d',
            typ_id='219',
            blkdef_name='1/sT (p',
            sample_display_name='1/sT (p',
            display_label='1/sT (parameter input) [1 input; param: T/y_max/y_min; 1 state]',
            category_path=('Native', 'Continuous', 'Integrators and Derivatives'),
            inputs=('yi',),
            outputs=('yo',),
            states=('1/sT (p__x',),
            params=('T', 'y_max', 'y_min'),
            unsupported_lines=(),
            module_name='typ_219__1_st_p',
            module_filename='typ_219__1_st_p.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_st_p_form_e',
            typ_id='220',
            blkdef_name='1/sT (p',
            sample_display_name='1/sT (p',
            display_label='1/sT (parameter input) [signal: y_max; param: T/y_min; 1 state]',
            category_path=('Native', 'Continuous', 'Integrators and Derivatives'),
            inputs=('yi', 'y_max'),
            outputs=('yo',),
            states=('1/sT (p__x',),
            params=('T', 'y_min'),
            unsupported_lines=(),
            module_name='typ_220__1_st_p',
            module_filename='typ_220__1_st_p.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_st_pp_form_a',
            typ_id='221',
            blkdef_name='1/sT (pp',
            sample_display_name='1/sT (pp',
            display_label='1/sT (2 parameter inputs) [1 input; param: T/K/y_max+1; 1 state]',
            category_path=('Native', 'Continuous', 'Integrators and Derivatives'),
            inputs=('yi',),
            outputs=('yo',),
            states=('1/sT (pp__x',),
            params=('T', 'K', 'y_max', 'y_min'),
            unsupported_lines=(),
            module_name='typ_221__1_st_pp',
            module_filename='typ_221__1_st_pp.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_st_s_form_a',
            typ_id='222',
            blkdef_name='1/sT (s',
            sample_display_name='1/sT (s',
            display_label='1/sT (signal input) [signal: y_min; param: T/y_max; 1 state]',
            category_path=('Native', 'Continuous', 'Integrators and Derivatives'),
            inputs=('yi', 'y_min'),
            outputs=('yo',),
            states=('1/sT (s__x',),
            params=('T', 'y_max'),
            unsupported_lines=(),
            module_name='typ_222__1_st_s',
            module_filename='typ_222__1_st_s.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_st_s_form_b',
            typ_id='223',
            blkdef_name='1/sT (s',
            sample_display_name='1/sT (s',
            display_label='1/sT (signal input) [signal: y_max/y_min; param: T; 1 state]',
            category_path=('Native', 'Continuous', 'Integrators and Derivatives'),
            inputs=('yi', 'y_max', 'y_min'),
            outputs=('yo',),
            states=('1/sT (s__x',),
            params=('T',),
            unsupported_lines=(),
            module_name='typ_223__1_st_s',
            module_filename='typ_223__1_st_s.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_st_form_a',
            typ_id='224',
            blkdef_name='1/sT',
            sample_display_name='1/sT',
            display_label='1/sT [1 input; param: T/y_max; 1 state; form A]',
            category_path=('Native', 'Continuous', 'Integrators and Derivatives'),
            inputs=('yi',),
            outputs=('yo',),
            states=('1/sT__x',),
            params=('T', 'y_max'),
            unsupported_lines=(),
            module_name='typ_224__1_st',
            module_filename='typ_224__1_st.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_st_form_b',
            typ_id='225',
            blkdef_name='1/sT',
            sample_display_name='1/sT',
            display_label='1/sT [1 input; param: T/y_max; 1 state; form B]',
            category_path=('Native', 'Continuous', 'Integrators and Derivatives'),
            inputs=('yi',),
            outputs=('yo',),
            states=('1/sT__x',),
            params=('T', 'y_max'),
            unsupported_lines=(),
            module_name='typ_225__1_st',
            module_filename='typ_225__1_st.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_st_form_c',
            typ_id='226',
            blkdef_name='1/sT',
            sample_display_name='1/sT',
            display_label='1/sT [1 input; param: T/y_max; 1 state; form C]',
            category_path=('Native', 'Continuous', 'Integrators and Derivatives'),
            inputs=('yi',),
            outputs=('yo',),
            states=('1/sT__x',),
            params=('T', 'y_max'),
            unsupported_lines=(),
            module_name='typ_226__1_st',
            module_filename='typ_226__1_st.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_st_form_d',
            typ_id='227',
            blkdef_name='1/sT',
            sample_display_name='1/sT',
            display_label='1/sT [1 input; param: T/y_max; 1 state; form D]',
            category_path=('Native', 'Continuous', 'Integrators and Derivatives'),
            inputs=('yi',),
            outputs=('yo',),
            states=('1/sT__x',),
            params=('T', 'y_max'),
            unsupported_lines=(),
            module_name='typ_227__1_st',
            module_filename='typ_227__1_st.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_st_p_form_f',
            typ_id='228',
            blkdef_name='1/sT [p',
            sample_display_name='1/sT [p',
            display_label='1/sT (parameter) [1 input; param: T/y_min; 1 state; form A]',
            category_path=('Native', 'Continuous', 'Integrators and Derivatives'),
            inputs=('yi',),
            outputs=('yo',),
            states=('1/sT [p__x',),
            params=('T', 'y_min'),
            unsupported_lines=(),
            module_name='typ_228__1_st_p',
            module_filename='typ_228__1_st_p.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_st_p_form_g',
            typ_id='229',
            blkdef_name='1/sT [p',
            sample_display_name='1/sT [p',
            display_label='1/sT (parameter) [1 input; param: T/y_min; 1 state; form B]',
            category_path=('Native', 'Continuous', 'Integrators and Derivatives'),
            inputs=('yi',),
            outputs=('yo',),
            states=('1/sT [p__x',),
            params=('T', 'y_min'),
            unsupported_lines=(),
            module_name='typ_229__1_st_p',
            module_filename='typ_229__1_st_p.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_st_bypass_incfreeze',
            typ_id='230',
            blkdef_name='1/sT _bypass_incfreeze',
            sample_display_name='1/sT _bypass_incfreeze',
            display_label='1/sT (bypass) incfreeze',
            category_path=('Native', 'Continuous', 'Integrators and Derivatives'),
            inputs=('yi',),
            outputs=('yo',),
            states=('1/sT _bypass_incfreeze__x',),
            params=('T', 'Tincfreeze'),
            unsupported_lines=(),
            module_name='typ_230__1_st_bypass_incfreeze',
            module_filename='typ_230__1_st_bypass_incfreeze.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_st_fb',
            typ_id='231',
            blkdef_name='1/sT _fb',
            sample_display_name='1/sT _fb',
            display_label='1/sT (feedback)',
            category_path=('Native', 'Continuous', 'Integrators and Derivatives'),
            inputs=('yi',),
            outputs=('yo',),
            states=('1/sT _fb__x',),
            params=('T',),
            unsupported_lines=(),
            module_name='typ_231__1_st_fb',
            module_filename='typ_231__1_st_fb.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_st_incfreeze',
            typ_id='232',
            blkdef_name='1/sT _incfreeze',
            sample_display_name='1/sT _incfreeze',
            display_label='1/sT (freeze)',
            category_path=('Native', 'Continuous', 'Integrators and Derivatives'),
            inputs=('yi',),
            outputs=('yo',),
            states=('1/sT _incfreeze__x',),
            params=('T', 'Tincfreeze'),
            unsupported_lines=(),
            module_name='typ_232__1_st_incfreeze',
            module_filename='typ_232__1_st_incfreeze.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_st_form_e',
            typ_id='233',
            blkdef_name='1/sT',
            sample_display_name='1/sT',
            display_label='1/sT [1 input; param: T; 1 state]',
            category_path=('Native', 'Continuous', 'Integrators and Derivatives'),
            inputs=('yi',),
            outputs=('yo',),
            states=('1/sT__x',),
            params=('T',),
            unsupported_lines=(),
            module_name='typ_233__1_st',
            module_filename='typ_233__1_st.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='k_s_p',
            typ_id='234',
            blkdef_name='K/s (p',
            sample_display_name='K/s (p',
            display_label='K/s (parameter input)',
            category_path=('Native', 'Control and Measurement', 'Controllers'),
            inputs=('yi',),
            outputs=('yo',),
            states=('K/s (p__x',),
            params=('K', 'y_max', 'y_min'),
            unsupported_lines=(),
            module_name='typ_234__k_s_p',
            module_filename='typ_234__k_s_p.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='k_s_s',
            typ_id='235',
            blkdef_name='K/s [(s',
            sample_display_name='K/s [(s',
            display_label='K/s [(s',
            category_path=('Native', 'Control and Measurement', 'Controllers'),
            inputs=('yi', 'y_max', 'y_min'),
            outputs=('yo',),
            states=('K/s [(s__x',),
            params=('K',),
            unsupported_lines=(),
            module_name='typ_235__k_s_s',
            module_filename='typ_235__k_s_s.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='k_s',
            typ_id='236',
            blkdef_name='K/s',
            sample_display_name='K/s',
            display_label='K/s',
            category_path=('Native', 'Control and Measurement', 'Controllers'),
            inputs=('yi',),
            outputs=('yo',),
            states=('K/s__x',),
            params=('K',),
            unsupported_lines=(),
            module_name='typ_236__k_s',
            module_filename='typ_236__k_s.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_s_p_form_d',
            typ_id='237',
            blkdef_name='1/s (p',
            sample_display_name='1/s (p',
            display_label='1/s (parameter input) [signal: rst; param: y_max/y_min; 1 state]',
            category_path=('Native', 'Continuous', 'Integrators and Derivatives'),
            inputs=('yi', 'rst'),
            outputs=('yo',),
            states=('1/s (p__x',),
            params=('y_max', 'y_min'),
            unsupported_lines=(),
            module_name='typ_237__1_s_p',
            module_filename='typ_237__1_s_p.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_s_s_form_d',
            typ_id='238',
            blkdef_name='1/s (s',
            sample_display_name='1/s (s',
            display_label='1/s (signal input) [signal: hold/rst/y_max+1; 1 state]',
            category_path=('Native', 'Continuous', 'Integrators and Derivatives'),
            inputs=('yi', 'hold', 'rst', 'y_max', 'y_min'),
            outputs=('yo',),
            states=('1/s (s__x',),
            params=(),
            unsupported_lines=(),
            module_name='typ_238__1_s_s',
            module_filename='typ_238__1_s_s.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_s_p_form_e',
            typ_id='239',
            blkdef_name='1/s [p',
            sample_display_name='1/s [p',
            display_label='1/s (parameter) [signal: rst; param: y_max/y_min; 1 state]',
            category_path=('Native', 'Continuous', 'Integrators and Derivatives'),
            inputs=('yi', 'rst'),
            outputs=('yo',),
            states=('1/s [p__x',),
            params=('y_max', 'y_min'),
            unsupported_lines=(),
            module_name='typ_239__1_s_p',
            module_filename='typ_239__1_s_p.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_s_p_reset',
            typ_id='240',
            blkdef_name='1/s [p]  _reset',
            sample_display_name='1/s [p]  _reset',
            display_label='1/s (parameter) (reset)',
            category_path=('Native', 'Continuous', 'Integrators and Derivatives'),
            inputs=('yi', 'rst'),
            outputs=('yo',),
            states=('1/s [p]  _reset__x',),
            params=('y_max',),
            unsupported_lines=(),
            module_name='typ_240__1_s_p_reset',
            module_filename='typ_240__1_s_p_reset.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_s_s_form_e',
            typ_id='241',
            blkdef_name='1/s [s',
            sample_display_name='1/s [s',
            display_label='1/s (signal) [signal: rst/y_max/y_min; 1 state]',
            category_path=('Native', 'Continuous', 'Integrators and Derivatives'),
            inputs=('yi', 'rst', 'y_max', 'y_min'),
            outputs=('yo',),
            states=('1/s [s__x',),
            params=(),
            unsupported_lines=(),
            module_name='typ_241__1_s_s',
            module_filename='typ_241__1_s_s.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_s_s_reset',
            typ_id='242',
            blkdef_name='1/s [s]  _reset',
            sample_display_name='1/s [s]  _reset',
            display_label='1/s (signal) (reset)',
            category_path=('Native', 'Continuous', 'Integrators and Derivatives'),
            inputs=('yi', 'rst', 'y_max'),
            outputs=('yo',),
            states=('1/s [s]  _reset__x',),
            params=(),
            unsupported_lines=(),
            module_name='typ_242__1_s_s_reset',
            module_filename='typ_242__1_s_s_reset.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_s_enable_reset',
            typ_id='243',
            blkdef_name='1/s _enable_reset',
            sample_display_name='1/s _enable_reset',
            display_label='1/s (enable) reset',
            category_path=('Native', 'Logic and Events', 'Timers and Enables'),
            inputs=('yi', 'hold', 'rst'),
            outputs=('yo',),
            states=('1/s _enable_reset__x',),
            params=(),
            unsupported_lines=(),
            module_name='typ_243__1_s_enable_reset',
            module_filename='typ_243__1_s_enable_reset.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_s_incfreeze_reset',
            typ_id='244',
            blkdef_name='1/s _incfreeze _reset',
            sample_display_name='1/s _incfreeze _reset',
            display_label='1/s (freeze) (reset)',
            category_path=('Native', 'Continuous', 'Integrators and Derivatives'),
            inputs=('yi', 'rst'),
            outputs=('yo',),
            states=('1/s _incfreeze _reset__x',),
            params=('Tincfreeze',),
            unsupported_lines=(),
            module_name='typ_244__1_s_incfreeze_reset',
            module_filename='typ_244__1_s_incfreeze_reset.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_s_reset',
            typ_id='245',
            blkdef_name='1/s _reset',
            sample_display_name='1/s _reset',
            display_label='1/s (reset)',
            category_path=('Native', 'Continuous', 'Integrators and Derivatives'),
            inputs=('yi', 'rst'),
            outputs=('yo',),
            states=('1/s _reset__x',),
            params=(),
            unsupported_lines=(),
            module_name='typ_245__1_s_reset',
            module_filename='typ_245__1_s_reset.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_st_reset',
            typ_id='246',
            blkdef_name='1/sT  _reset',
            sample_display_name='1/sT  _reset',
            display_label='1/sT (reset)',
            category_path=('Native', 'Continuous', 'Integrators and Derivatives'),
            inputs=('yi', 'rst'),
            outputs=('yo',),
            states=('1/sT  _reset__x',),
            params=('T',),
            unsupported_lines=(),
            module_name='typ_246__1_st_reset',
            module_filename='typ_246__1_st_reset.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_st_p_reset',
            typ_id='247',
            blkdef_name='1/sT (p)  _reset',
            sample_display_name='1/sT (p)  _reset',
            display_label='1/sT (parameter) (reset)',
            category_path=('Native', 'Continuous', 'Integrators and Derivatives'),
            inputs=('yi', 'rst'),
            outputs=('yo',),
            states=('1/sT (p)  _reset__x',),
            params=('T', 'y_max'),
            unsupported_lines=(),
            module_name='typ_247__1_st_p_reset',
            module_filename='typ_247__1_st_p_reset.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_st_p_fb_reset',
            typ_id='248',
            blkdef_name='1/sT (p) _fb_reset',
            sample_display_name='1/sT (p) _fb_reset',
            display_label='1/sT (parameter) (feedback) reset',
            category_path=('Native', 'Continuous', 'Integrators and Derivatives'),
            inputs=('yi', 'rst'),
            outputs=('yo',),
            states=('1/sT (p) _fb_reset__x',),
            params=('T', 'y_max'),
            unsupported_lines=(),
            module_name='typ_248__1_st_p_fb_reset',
            module_filename='typ_248__1_st_p_fb_reset.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_st_p_form_h',
            typ_id='249',
            blkdef_name='1/sT (p',
            sample_display_name='1/sT (p',
            display_label='1/sT (parameter input) [signal: rst; param: T/y_min; 1 state; form A]',
            category_path=('Native', 'Continuous', 'Integrators and Derivatives'),
            inputs=('yi', 'rst'),
            outputs=('yo',),
            states=('1/sT (p__x',),
            params=('T', 'y_min'),
            unsupported_lines=(),
            module_name='typ_249__1_st_p',
            module_filename='typ_249__1_st_p.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_st_p_form_i',
            typ_id='250',
            blkdef_name='1/sT (p',
            sample_display_name='1/sT (p',
            display_label='1/sT (parameter input) [signal: rst; param: T/y_min; 1 state; form B]',
            category_path=('Native', 'Continuous', 'Integrators and Derivatives'),
            inputs=('yi', 'rst'),
            outputs=('yo',),
            states=('1/sT (p__x',),
            params=('T', 'y_min'),
            unsupported_lines=(),
            module_name='typ_250__1_st_p',
            module_filename='typ_250__1_st_p.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_st_p_form_j',
            typ_id='251',
            blkdef_name='1/sT (p',
            sample_display_name='1/sT (p',
            display_label='1/sT (parameter input) [signal: rst; param: T/y_max/y_min; 1 state]',
            category_path=('Native', 'Continuous', 'Integrators and Derivatives'),
            inputs=('yi', 'rst'),
            outputs=('yo',),
            states=('1/sT (p__x',),
            params=('T', 'y_max', 'y_min'),
            unsupported_lines=(),
            module_name='typ_251__1_st_p',
            module_filename='typ_251__1_st_p.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_st_p_form_k',
            typ_id='252',
            blkdef_name='1/sT (p',
            sample_display_name='1/sT (p',
            display_label='1/sT (parameter input) [signal: rst/y_max; param: T/y_min; 1 state]',
            category_path=('Native', 'Continuous', 'Integrators and Derivatives'),
            inputs=('yi', 'rst', 'y_max'),
            outputs=('yo',),
            states=('1/sT (p__x',),
            params=('T', 'y_min'),
            unsupported_lines=(),
            module_name='typ_252__1_st_p',
            module_filename='typ_252__1_st_p.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_st_pp_form_b',
            typ_id='253',
            blkdef_name='1/sT (pp',
            sample_display_name='1/sT (pp',
            display_label='1/sT (2 parameter inputs) [signal: rst; param: T/K/y_max+1; 1 state]',
            category_path=('Native', 'Continuous', 'Integrators and Derivatives'),
            inputs=('yi', 'rst'),
            outputs=('yo',),
            states=('1/sT (pp__x',),
            params=('T', 'K', 'y_max', 'y_min'),
            unsupported_lines=(),
            module_name='typ_253__1_st_pp',
            module_filename='typ_253__1_st_pp.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_st_s_form_c',
            typ_id='254',
            blkdef_name='1/sT (s',
            sample_display_name='1/sT (s',
            display_label='1/sT (signal input) [signal: rst/y_min; param: T/y_max; 1 state]',
            category_path=('Native', 'Continuous', 'Integrators and Derivatives'),
            inputs=('yi', 'rst', 'y_min'),
            outputs=('yo',),
            states=('1/sT (s__x',),
            params=('T', 'y_max'),
            unsupported_lines=(),
            module_name='typ_254__1_st_s',
            module_filename='typ_254__1_st_s.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_st_s_form_d',
            typ_id='255',
            blkdef_name='1/sT (s',
            sample_display_name='1/sT (s',
            display_label='1/sT (signal input) [signal: rst/y_max/y_min; param: T; 1 state]',
            category_path=('Native', 'Continuous', 'Integrators and Derivatives'),
            inputs=('yi', 'rst', 'y_max', 'y_min'),
            outputs=('yo',),
            states=('1/sT (s__x',),
            params=('T',),
            unsupported_lines=(),
            module_name='typ_255__1_st_s',
            module_filename='typ_255__1_st_s.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_st_form_f',
            typ_id='256',
            blkdef_name='1/sT',
            sample_display_name='1/sT',
            display_label='1/sT [signal: rst; param: T/y_max; 1 state; form A]',
            category_path=('Native', 'Continuous', 'Integrators and Derivatives'),
            inputs=('yi', 'rst'),
            outputs=('yo',),
            states=('1/sT__x',),
            params=('T', 'y_max'),
            unsupported_lines=(),
            module_name='typ_256__1_st',
            module_filename='typ_256__1_st.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_st_form_g',
            typ_id='257',
            blkdef_name='1/sT',
            sample_display_name='1/sT',
            display_label='1/sT [signal: rst; param: T/y_max; 1 state; form B]',
            category_path=('Native', 'Continuous', 'Integrators and Derivatives'),
            inputs=('yi', 'rst'),
            outputs=('yo',),
            states=('1/sT__x',),
            params=('T', 'y_max'),
            unsupported_lines=(),
            module_name='typ_257__1_st',
            module_filename='typ_257__1_st.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_st_form_h',
            typ_id='258',
            blkdef_name='1/sT',
            sample_display_name='1/sT',
            display_label='1/sT [signal: rst; param: T/y_max; 1 state; form C]',
            category_path=('Native', 'Continuous', 'Integrators and Derivatives'),
            inputs=('yi', 'rst'),
            outputs=('yo',),
            states=('1/sT__x',),
            params=('T', 'y_max'),
            unsupported_lines=(),
            module_name='typ_258__1_st',
            module_filename='typ_258__1_st.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_st_form_i',
            typ_id='259',
            blkdef_name='1/sT',
            sample_display_name='1/sT',
            display_label='1/sT [signal: rst; param: T/y_max; 1 state; form D]',
            category_path=('Native', 'Continuous', 'Integrators and Derivatives'),
            inputs=('yi', 'rst'),
            outputs=('yo',),
            states=('1/sT__x',),
            params=('T', 'y_max'),
            unsupported_lines=(),
            module_name='typ_259__1_st',
            module_filename='typ_259__1_st.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_st_p_form_l',
            typ_id='260',
            blkdef_name='1/sT [p',
            sample_display_name='1/sT [p',
            display_label='1/sT (parameter) [signal: rst; param: T/y_min; 1 state; form A]',
            category_path=('Native', 'Continuous', 'Integrators and Derivatives'),
            inputs=('yi', 'rst'),
            outputs=('yo',),
            states=('1/sT [p__x',),
            params=('T', 'y_min'),
            unsupported_lines=(),
            module_name='typ_260__1_st_p',
            module_filename='typ_260__1_st_p.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_st_p_form_m',
            typ_id='261',
            blkdef_name='1/sT [p',
            sample_display_name='1/sT [p',
            display_label='1/sT (parameter) [signal: rst; param: T/y_min; 1 state; form B]',
            category_path=('Native', 'Continuous', 'Integrators and Derivatives'),
            inputs=('yi', 'rst'),
            outputs=('yo',),
            states=('1/sT [p__x',),
            params=('T', 'y_min'),
            unsupported_lines=(),
            module_name='typ_261__1_st_p',
            module_filename='typ_261__1_st_p.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_st_bypass_incfreeze_reset',
            typ_id='262',
            blkdef_name='1/sT _bypass_incfreeze_reset',
            sample_display_name='1/sT _bypass_incfreeze_reset',
            display_label='1/sT (bypass) incfreeze reset',
            category_path=('Native', 'Continuous', 'Integrators and Derivatives'),
            inputs=('yi', 'rst'),
            outputs=('yo',),
            states=('1/sT _bypass_incfreeze_reset__x',),
            params=('T', 'Tincfreeze'),
            unsupported_lines=(),
            module_name='typ_262__1_st_bypass_incfreeze_reset',
            module_filename='typ_262__1_st_bypass_incfreeze_reset.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_st_fb_reset',
            typ_id='263',
            blkdef_name='1/sT _fb_reset',
            sample_display_name='1/sT _fb_reset',
            display_label='1/sT (feedback) reset',
            category_path=('Native', 'Continuous', 'Integrators and Derivatives'),
            inputs=('yi', 'rst'),
            outputs=('yo',),
            states=('1/sT _fb_reset__x',),
            params=('T',),
            unsupported_lines=(),
            module_name='typ_263__1_st_fb_reset',
            module_filename='typ_263__1_st_fb_reset.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_st_incfreeze_reset',
            typ_id='264',
            blkdef_name='1/sT _incfreeze_reset',
            sample_display_name='1/sT _incfreeze_reset',
            display_label='1/sT (freeze) reset',
            category_path=('Native', 'Continuous', 'Integrators and Derivatives'),
            inputs=('yi', 'rst'),
            outputs=('yo',),
            states=('1/sT _incfreeze_reset__x',),
            params=('T', 'Tincfreeze'),
            unsupported_lines=(),
            module_name='typ_264__1_st_incfreeze_reset',
            module_filename='typ_264__1_st_incfreeze_reset.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_s_p_form_f',
            typ_id='265',
            blkdef_name='1/s (p',
            sample_display_name='1/s (p',
            display_label='1/s (parameter input) [signal: xrst/rst; param: y_max/y_min; 1 state]',
            category_path=('Native', 'Continuous', 'Integrators and Derivatives'),
            inputs=('yi', 'xrst', 'rst'),
            outputs=('yo',),
            states=('1/s (p__x',),
            params=('y_max', 'y_min'),
            unsupported_lines=(),
            module_name='typ_265__1_s_p',
            module_filename='typ_265__1_s_p.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_s_s_form_f',
            typ_id='266',
            blkdef_name='1/s (s',
            sample_display_name='1/s (s',
            display_label='1/s (signal input) [signal: hold/xrst/rst+2; 1 state]',
            category_path=('Native', 'Continuous', 'Integrators and Derivatives'),
            inputs=('yi', 'hold', 'xrst', 'rst', 'y_max', 'y_min'),
            outputs=('yo',),
            states=('1/s (s__x',),
            params=(),
            unsupported_lines=(),
            module_name='typ_266__1_s_s',
            module_filename='typ_266__1_s_s.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_s_p_form_g',
            typ_id='267',
            blkdef_name='1/s [p',
            sample_display_name='1/s [p',
            display_label='1/s (parameter) [signal: xrst/rst; param: y_max/y_min; 1 state]',
            category_path=('Native', 'Continuous', 'Integrators and Derivatives'),
            inputs=('yi', 'xrst', 'rst'),
            outputs=('yo',),
            states=('1/s [p__x',),
            params=('y_max', 'y_min'),
            unsupported_lines=(),
            module_name='typ_267__1_s_p',
            module_filename='typ_267__1_s_p.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_s_p_reset_sig',
            typ_id='268',
            blkdef_name='1/s [p]  _reset_sig',
            sample_display_name='1/s [p]  _reset_sig',
            display_label='1/s (parameter) (reset signal)',
            category_path=('Native', 'Continuous', 'Integrators and Derivatives'),
            inputs=('yi', 'xrst', 'rst'),
            outputs=('yo',),
            states=('1/s [p]  _reset_sig__x',),
            params=('y_max',),
            unsupported_lines=(),
            module_name='typ_268__1_s_p_reset_sig',
            module_filename='typ_268__1_s_p_reset_sig.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_s_s_form_g',
            typ_id='269',
            blkdef_name='1/s [s',
            sample_display_name='1/s [s',
            display_label='1/s (signal) [signal: xrst/rst/y_max+1; 1 state]',
            category_path=('Native', 'Continuous', 'Integrators and Derivatives'),
            inputs=('yi', 'xrst', 'rst', 'y_max', 'y_min'),
            outputs=('yo',),
            states=('1/s [s__x',),
            params=(),
            unsupported_lines=(),
            module_name='typ_269__1_s_s',
            module_filename='typ_269__1_s_s.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_s_s_reset_sig',
            typ_id='270',
            blkdef_name='1/s [s]  _reset_sig',
            sample_display_name='1/s [s]  _reset_sig',
            display_label='1/s (signal) (reset signal)',
            category_path=('Native', 'Continuous', 'Integrators and Derivatives'),
            inputs=('yi', 'xrst', 'rst', 'y_max'),
            outputs=('yo',),
            states=('1/s [s]  _reset_sig__x',),
            params=(),
            unsupported_lines=(),
            module_name='typ_270__1_s_s_reset_sig',
            module_filename='typ_270__1_s_s_reset_sig.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_s_enable_reset_sig',
            typ_id='271',
            blkdef_name='1/s _enable_reset_sig',
            sample_display_name='1/s _enable_reset_sig',
            display_label='1/s (enable) reset sig',
            category_path=('Native', 'Logic and Events', 'Timers and Enables'),
            inputs=('yi', 'hold', 'xrst', 'rst'),
            outputs=('yo',),
            states=('1/s _enable_reset_sig__x',),
            params=(),
            unsupported_lines=(),
            module_name='typ_271__1_s_enable_reset_sig',
            module_filename='typ_271__1_s_enable_reset_sig.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_s_incfreeze_reset_sig',
            typ_id='272',
            blkdef_name='1/s _incfreeze _reset_sig',
            sample_display_name='1/s _incfreeze _reset_sig',
            display_label='1/s (freeze) (reset signal)',
            category_path=('Native', 'Continuous', 'Integrators and Derivatives'),
            inputs=('yi', 'xrst', 'rst'),
            outputs=('yo',),
            states=('1/s _incfreeze _reset_sig__x',),
            params=('Tincfreeze',),
            unsupported_lines=(),
            module_name='typ_272__1_s_incfreeze_reset_sig',
            module_filename='typ_272__1_s_incfreeze_reset_sig.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_s_reset_sig',
            typ_id='273',
            blkdef_name='1/s _reset_sig',
            sample_display_name='1/s _reset_sig',
            display_label='1/s (reset signal)',
            category_path=('Native', 'Continuous', 'Integrators and Derivatives'),
            inputs=('yi', 'xrst', 'rst'),
            outputs=('yo',),
            states=('1/s _reset_sig__x',),
            params=(),
            unsupported_lines=(),
            module_name='typ_273__1_s_reset_sig',
            module_filename='typ_273__1_s_reset_sig.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_st_reset_sig',
            typ_id='274',
            blkdef_name='1/sT  _reset_sig',
            sample_display_name='1/sT  _reset_sig',
            display_label='1/sT (reset signal)',
            category_path=('Native', 'Continuous', 'Integrators and Derivatives'),
            inputs=('yi', 'xrst', 'rst'),
            outputs=('yo',),
            states=('1/sT  _reset_sig__x',),
            params=('T',),
            unsupported_lines=(),
            module_name='typ_274__1_st_reset_sig',
            module_filename='typ_274__1_st_reset_sig.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_st_p_reset_sig',
            typ_id='275',
            blkdef_name='1/sT (p)  _reset_sig',
            sample_display_name='1/sT (p)  _reset_sig',
            display_label='1/sT (parameter) (reset signal)',
            category_path=('Native', 'Continuous', 'Integrators and Derivatives'),
            inputs=('yi', 'xrst', 'rst'),
            outputs=('yo',),
            states=('1/sT (p)  _reset_sig__x',),
            params=('T', 'y_max'),
            unsupported_lines=(),
            module_name='typ_275__1_st_p_reset_sig',
            module_filename='typ_275__1_st_p_reset_sig.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_st_p_fb_reset_sig',
            typ_id='276',
            blkdef_name='1/sT (p) _fb _reset_sig',
            sample_display_name='1/sT (p) _fb _reset_sig',
            display_label='1/sT (parameter) (feedback) (reset signal)',
            category_path=('Native', 'Continuous', 'Integrators and Derivatives'),
            inputs=('yi', 'xrst', 'rst'),
            outputs=('yo',),
            states=('1/sT (p) _fb _reset_sig__x',),
            params=('T', 'y_max'),
            unsupported_lines=(),
            module_name='typ_276__1_st_p_fb_reset_sig',
            module_filename='typ_276__1_st_p_fb_reset_sig.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_st_p_form_n',
            typ_id='277',
            blkdef_name='1/sT (p',
            sample_display_name='1/sT (p',
            display_label='1/sT (parameter input) [signal: xrst/rst; param: T/y_min; 1 state; form A]',
            category_path=('Native', 'Continuous', 'Integrators and Derivatives'),
            inputs=('yi', 'xrst', 'rst'),
            outputs=('yo',),
            states=('1/sT (p__x',),
            params=('T', 'y_min'),
            unsupported_lines=(),
            module_name='typ_277__1_st_p',
            module_filename='typ_277__1_st_p.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_st_p_form_o',
            typ_id='278',
            blkdef_name='1/sT (p',
            sample_display_name='1/sT (p',
            display_label='1/sT (parameter input) [signal: xrst/rst; param: T/y_min; 1 state; form B]',
            category_path=('Native', 'Continuous', 'Integrators and Derivatives'),
            inputs=('yi', 'xrst', 'rst'),
            outputs=('yo',),
            states=('1/sT (p__x',),
            params=('T', 'y_min'),
            unsupported_lines=(),
            module_name='typ_278__1_st_p',
            module_filename='typ_278__1_st_p.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_st_p_form_p',
            typ_id='279',
            blkdef_name='1/sT (p',
            sample_display_name='1/sT (p',
            display_label='1/sT (parameter input) [signal: xrst/rst; param: T/y_max/y_min; 1 state]',
            category_path=('Native', 'Continuous', 'Integrators and Derivatives'),
            inputs=('yi', 'xrst', 'rst'),
            outputs=('yo',),
            states=('1/sT (p__x',),
            params=('T', 'y_max', 'y_min'),
            unsupported_lines=(),
            module_name='typ_279__1_st_p',
            module_filename='typ_279__1_st_p.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_st_p_form_q',
            typ_id='280',
            blkdef_name='1/sT (p',
            sample_display_name='1/sT (p',
            display_label='1/sT (parameter input) [signal: xrst/rst/y_max; param: T/y_min; 1 state]',
            category_path=('Native', 'Continuous', 'Integrators and Derivatives'),
            inputs=('yi', 'xrst', 'rst', 'y_max'),
            outputs=('yo',),
            states=('1/sT (p__x',),
            params=('T', 'y_min'),
            unsupported_lines=(),
            module_name='typ_280__1_st_p',
            module_filename='typ_280__1_st_p.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_st_pp_form_c',
            typ_id='281',
            blkdef_name='1/sT (pp',
            sample_display_name='1/sT (pp',
            display_label='1/sT (2 parameter inputs) [signal: xrst/rst; param: T/K/y_max+1; 1 state]',
            category_path=('Native', 'Continuous', 'Integrators and Derivatives'),
            inputs=('yi', 'xrst', 'rst'),
            outputs=('yo',),
            states=('1/sT (pp__x',),
            params=('T', 'K', 'y_max', 'y_min'),
            unsupported_lines=(),
            module_name='typ_281__1_st_pp',
            module_filename='typ_281__1_st_pp.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_st_s_form_e',
            typ_id='282',
            blkdef_name='1/sT (s',
            sample_display_name='1/sT (s',
            display_label='1/sT (signal input) [signal: xrst/rst/y_min; param: T/y_max; 1 state]',
            category_path=('Native', 'Continuous', 'Integrators and Derivatives'),
            inputs=('yi', 'xrst', 'rst', 'y_min'),
            outputs=('yo',),
            states=('1/sT (s__x',),
            params=('T', 'y_max'),
            unsupported_lines=(),
            module_name='typ_282__1_st_s',
            module_filename='typ_282__1_st_s.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_st_s_form_f',
            typ_id='283',
            blkdef_name='1/sT (s',
            sample_display_name='1/sT (s',
            display_label='1/sT (signal input) [signal: xrst/rst/y_max+1; param: T; 1 state]',
            category_path=('Native', 'Continuous', 'Integrators and Derivatives'),
            inputs=('yi', 'xrst', 'rst', 'y_max', 'y_min'),
            outputs=('yo',),
            states=('1/sT (s__x',),
            params=('T',),
            unsupported_lines=(),
            module_name='typ_283__1_st_s',
            module_filename='typ_283__1_st_s.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_st_form_j',
            typ_id='284',
            blkdef_name='1/sT',
            sample_display_name='1/sT',
            display_label='1/sT [signal: xrst/rst; param: T/y_max; 1 state; form A]',
            category_path=('Native', 'Continuous', 'Integrators and Derivatives'),
            inputs=('yi', 'xrst', 'rst'),
            outputs=('yo',),
            states=('1/sT__x',),
            params=('T', 'y_max'),
            unsupported_lines=(),
            module_name='typ_284__1_st',
            module_filename='typ_284__1_st.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_st_form_k',
            typ_id='285',
            blkdef_name='1/sT',
            sample_display_name='1/sT',
            display_label='1/sT [signal: xrst/rst; param: T/y_max; 1 state; form B]',
            category_path=('Native', 'Continuous', 'Integrators and Derivatives'),
            inputs=('yi', 'xrst', 'rst'),
            outputs=('yo',),
            states=('1/sT__x',),
            params=('T', 'y_max'),
            unsupported_lines=(),
            module_name='typ_285__1_st',
            module_filename='typ_285__1_st.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_st_form_l',
            typ_id='286',
            blkdef_name='1/sT',
            sample_display_name='1/sT',
            display_label='1/sT [signal: xrst/rst; param: T/y_max; 1 state; form C]',
            category_path=('Native', 'Continuous', 'Integrators and Derivatives'),
            inputs=('yi', 'xrst', 'rst'),
            outputs=('yo',),
            states=('1/sT__x',),
            params=('T', 'y_max'),
            unsupported_lines=(),
            module_name='typ_286__1_st',
            module_filename='typ_286__1_st.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_st_form_m',
            typ_id='287',
            blkdef_name='1/sT',
            sample_display_name='1/sT',
            display_label='1/sT [signal: xrst/rst; param: T/y_max; 1 state; form D]',
            category_path=('Native', 'Continuous', 'Integrators and Derivatives'),
            inputs=('yi', 'xrst', 'rst'),
            outputs=('yo',),
            states=('1/sT__x',),
            params=('T', 'y_max'),
            unsupported_lines=(),
            module_name='typ_287__1_st',
            module_filename='typ_287__1_st.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_st_p_form_r',
            typ_id='288',
            blkdef_name='1/sT [p',
            sample_display_name='1/sT [p',
            display_label='1/sT (parameter) [signal: xrst/rst; param: T/y_min; 1 state; form A]',
            category_path=('Native', 'Continuous', 'Integrators and Derivatives'),
            inputs=('yi', 'xrst', 'rst'),
            outputs=('yo',),
            states=('1/sT [p__x',),
            params=('T', 'y_min'),
            unsupported_lines=(),
            module_name='typ_288__1_st_p',
            module_filename='typ_288__1_st_p.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_st_p_form_s',
            typ_id='289',
            blkdef_name='1/sT [p',
            sample_display_name='1/sT [p',
            display_label='1/sT (parameter) [signal: xrst/rst; param: T/y_min; 1 state; form B]',
            category_path=('Native', 'Continuous', 'Integrators and Derivatives'),
            inputs=('yi', 'xrst', 'rst'),
            outputs=('yo',),
            states=('1/sT [p__x',),
            params=('T', 'y_min'),
            unsupported_lines=(),
            module_name='typ_289__1_st_p',
            module_filename='typ_289__1_st_p.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_st_bypass_incfreeze_reset_sig',
            typ_id='290',
            blkdef_name='1/sT _bypass_incfreeze_reset_sig',
            sample_display_name='1/sT _bypass_incfreeze_reset_sig',
            display_label='1/sT (bypass) incfreeze reset sig',
            category_path=('Native', 'Continuous', 'Integrators and Derivatives'),
            inputs=('yi', 'xrst', 'rst'),
            outputs=('yo',),
            states=('1/sT _bypass_incfreeze_reset_sig__x',),
            params=('T', 'Tincfreeze'),
            unsupported_lines=(),
            module_name='typ_290__1_st_bypass_incfreeze_reset_sig',
            module_filename='typ_290__1_st_bypass_incfreeze_reset_sig.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_st_fb_reset_sig',
            typ_id='291',
            blkdef_name='1/sT _fb_reset_sig',
            sample_display_name='1/sT _fb_reset_sig',
            display_label='1/sT (feedback) reset sig',
            category_path=('Native', 'Continuous', 'Integrators and Derivatives'),
            inputs=('yi', 'xrst', 'rst'),
            outputs=('yo',),
            states=('1/sT _fb_reset_sig__x',),
            params=('T',),
            unsupported_lines=(),
            module_name='typ_291__1_st_fb_reset_sig',
            module_filename='typ_291__1_st_fb_reset_sig.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_st_incfreeze_reset_sig',
            typ_id='292',
            blkdef_name='1/sT _incfreeze_reset_sig',
            sample_display_name='1/sT _incfreeze_reset_sig',
            display_label='1/sT (freeze) reset sig',
            category_path=('Native', 'Continuous', 'Integrators and Derivatives'),
            inputs=('yi', 'xrst', 'rst'),
            outputs=('yo',),
            states=('1/sT _incfreeze_reset_sig__x',),
            params=('T', 'Tincfreeze'),
            unsupported_lines=(),
            module_name='typ_292__1_st_incfreeze_reset_sig',
            module_filename='typ_292__1_st_incfreeze_reset_sig.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_ats_1_bts',
            typ_id='293',
            blkdef_name='(1+ATs)/(1+BTs)',
            sample_display_name='(1+ATs)/(1+BTs)',
            display_label='(1+ATs)/(1+BTs)',
            category_path=('Native', 'Continuous', 'Transfer Functions and Filters'),
            inputs=('yi',),
            outputs=('yo',),
            states=('(1+ATs)/(1+BTs)__x',),
            params=('A', 'B', 'T'),
            unsupported_lines=(),
            module_name='typ_293__1_ats_1_bts',
            module_filename='typ_293__1_ats_1_bts.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_stb_1_sta_p_form_a',
            typ_id='294',
            blkdef_name='(1+sTb)/(1+sTa) [(p',
            sample_display_name='(1+sTb)/(1+sTa) [(p',
            display_label='(1+sTb)/(1+sTa) (parameter input) [param: Tb/Ta/y_max+1; 1 state; form A]',
            category_path=('Native', 'Continuous', 'Transfer Functions and Filters'),
            inputs=('yi',),
            outputs=('yo',),
            states=('(1+sTb)/(1+sTa) [(p__x',),
            params=('Tb', 'Ta', 'y_max', 'y_min'),
            unsupported_lines=(),
            module_name='typ_294__1_stb_1_sta_p',
            module_filename='typ_294__1_stb_1_sta_p.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_stb_1_sta_p_form_b',
            typ_id='295',
            blkdef_name='(1+sTb)/(1+sTa) [(p',
            sample_display_name='(1+sTb)/(1+sTa) [(p',
            display_label='(1+sTb)/(1+sTa) (parameter input) [param: Tb/Ta/y_max+1; 1 state; form B]',
            category_path=('Native', 'Continuous', 'Transfer Functions and Filters'),
            inputs=('yi',),
            outputs=('yo',),
            states=('(1+sTb)/(1+sTa) [(p__x',),
            params=('Tb', 'Ta', 'y_max', 'y_min'),
            unsupported_lines=(),
            module_name='typ_295__1_stb_1_sta_p',
            module_filename='typ_295__1_stb_1_sta_p.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_stb_1_sta_pp',
            typ_id='296',
            blkdef_name='(1+sTb)/(1+sTa) [(pp',
            sample_display_name='(1+sTb)/(1+sTa) [(pp',
            display_label='(1+sTb)/(1+sTa) (2 parameter inputs)',
            category_path=('Native', 'Continuous', 'Transfer Functions and Filters'),
            inputs=('yi',),
            outputs=('yo',),
            states=('(1+sTb)/(1+sTa) [(pp__x',),
            params=('Tb', 'Ta', 'K', 'y_max', 'y_min'),
            unsupported_lines=(),
            module_name='typ_296__1_stb_1_sta_pp',
            module_filename='typ_296__1_stb_1_sta_pp.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_stb_1_sta_bypass',
            typ_id='297',
            blkdef_name='(1+sTb)/(1+sTa) _bypass',
            sample_display_name='(1+sTb)/(1+sTa) _bypass',
            display_label='(1+sTb)/(1+sTa) (bypass)',
            category_path=('Native', 'Continuous', 'Transfer Functions and Filters'),
            inputs=('yi',),
            outputs=('yo',),
            states=('(1+sTb)/(1+sTa) _bypass__x',),
            params=('Tb', 'Ta'),
            unsupported_lines=(),
            module_name='typ_297__1_stb_1_sta_bypass',
            module_filename='typ_297__1_stb_1_sta_bypass.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_stb_1_sta',
            typ_id='298',
            blkdef_name='(1+sTb)/(1+sTa)',
            sample_display_name='(1+sTb)/(1+sTa)',
            display_label='(1+sTb)/(1+sTa)',
            category_path=('Native', 'Continuous', 'Transfer Functions and Filters'),
            inputs=('yi',),
            outputs=('yo',),
            states=('(1+sTb)/(1+sTa)__x',),
            params=('Tb', 'Ta'),
            unsupported_lines=(),
            module_name='typ_298__1_stb_1_sta',
            module_filename='typ_298__1_stb_1_sta.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_stld_1_stlg_and_sx',
            typ_id='299',
            blkdef_name='(1+sTld)/(1+sTlg) and sx',
            sample_display_name='(1+sTld)/(1+sTlg) and sx',
            display_label='(1+sTld)/(1+sTlg) and sx',
            category_path=('Native', 'Continuous', 'Transfer Functions and Filters'),
            inputs=('yi',),
            outputs=('yo',),
            states=('(1+sTld)/(1+sTlg) and sx__x',),
            params=('Tld', 'Tlg'),
            unsupported_lines=(),
            module_name='typ_299__1_stld_1_stlg_and_sx',
            module_filename='typ_299__1_stld_1_stlg_and_sx.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_ats_1_sat_2',
            typ_id='300',
            blkdef_name='(1-ATs)/(1+sAT/2)',
            sample_display_name='(1-ATs)/(1+sAT/2)',
            display_label='(1-ATs)/(1+sAT/2)',
            category_path=('Native', 'Continuous', 'Transfer Functions and Filters'),
            inputs=('yi',),
            outputs=('yo',),
            states=('(1-ATs)/(1+sAT/2)__x',),
            params=('A', 'T'),
            unsupported_lines=(),
            module_name='typ_300__1_ats_1_sat_2',
            module_filename='typ_300__1_ats_1_sat_2.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_st_1_st_2_bypass',
            typ_id='301',
            blkdef_name='(1-sT)/(1+sT/2) _bypass',
            sample_display_name='(1-sT)/(1+sT/2) _bypass',
            display_label='(1-sT)/(1+sT/2) (bypass)',
            category_path=('Native', 'Continuous', 'Transfer Functions and Filters'),
            inputs=('yi',),
            outputs=('yo',),
            states=('(1-sT)/(1+sT/2) _bypass__x',),
            params=('T',),
            unsupported_lines=(),
            module_name='typ_301__1_st_1_st_2_bypass',
            module_filename='typ_301__1_st_1_st_2_bypass.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='k_stb_1_sta',
            typ_id='302',
            blkdef_name='(K+sTb)/(1+sTa)',
            sample_display_name='(K+sTb)/(1+sTa)',
            display_label='(K+sTb)/(1+sTa)',
            category_path=('Native', 'Continuous', 'Transfer Functions and Filters'),
            inputs=('yi',),
            outputs=('yo',),
            states=('(K+sTb)/(1+sTa)__x',),
            params=('K', 'Tb', 'Ta'),
            unsupported_lines=(),
            module_name='typ_302__k_stb_1_sta',
            module_filename='typ_302__k_stb_1_sta.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='a_sbt_1_st_bypass',
            typ_id='303',
            blkdef_name='(a+sbT)/(1+sT) _bypass',
            sample_display_name='(a+sbT)/(1+sT) _bypass',
            display_label='(a+sbT)/(1+sT) (bypass)',
            category_path=('Native', 'Continuous', 'Transfer Functions and Filters'),
            inputs=('yi',),
            outputs=('yo',),
            states=('(a+sbT)/(1+sT) _bypass__x',),
            params=('a', 'b', 'T'),
            unsupported_lines=(),
            module_name='typ_303__a_sbt_1_st_bypass',
            module_filename='typ_303__a_sbt_1_st_bypass.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='k_1_stb_1_sta',
            typ_id='304',
            blkdef_name='K(1+sTb)/(1+sTa)',
            sample_display_name='K(1+sTb)/(1+sTa)',
            display_label='K(1+sTb)/(1+sTa)',
            category_path=('Native', 'Control and Measurement', 'Controllers'),
            inputs=('yi',),
            outputs=('yo',),
            states=('K(1+sTb)/(1+sTa)__x',),
            params=('K', 'Tb', 'Ta'),
            unsupported_lines=(),
            module_name='typ_304__k_1_stb_1_sta',
            module_filename='typ_304__k_1_stb_1_sta.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='k_1_stld_1_stlg_fb',
            typ_id='305',
            blkdef_name='K(1+sTld)/(1+sTlg) _fb',
            sample_display_name='K(1+sTld)/(1+sTlg) _fb',
            display_label='K(1+sTld)/(1+sTlg) (feedback)',
            category_path=('Native', 'Control and Measurement', 'Controllers'),
            inputs=('yi',),
            outputs=('yo',),
            states=('K(1+sTld)/(1+sTlg) _fb__x',),
            params=('K', 'Tld', 'Tlg'),
            unsupported_lines=(),
            module_name='typ_305__k_1_stld_1_stlg_fb',
            module_filename='typ_305__k_1_stld_1_stlg_fb.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='k_a1_st1_a2_st2_p',
            typ_id='306',
            blkdef_name='K(A1+sT1)/(A2+sT2) [(p',
            sample_display_name='K(A1+sT1)/(A2+sT2) [(p',
            display_label='K(A1+sT1)/(A2+sT2) (parameter input)',
            category_path=('Native', 'Control and Measurement', 'Controllers'),
            inputs=('yi',),
            outputs=('yo',),
            states=('K(A1+sT1)/(A2+sT2) [(p__x',),
            params=('K', 'A1', 'T1', 'A2', 'T2', 'y_max', 'y_min'),
            unsupported_lines=(),
            module_name='typ_306__k_a1_st1_a2_st2_p',
            module_filename='typ_306__k_a1_st1_a2_st2_p.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='k_a1_st1_a2_st2_fb',
            typ_id='307',
            blkdef_name='K(A1+sT1)/(A2+sT2) _fb',
            sample_display_name='K(A1+sT1)/(A2+sT2) _fb',
            display_label='K(A1+sT1)/(A2+sT2) (feedback)',
            category_path=('Native', 'Control and Measurement', 'Controllers'),
            inputs=('yi',),
            outputs=('yo',),
            states=('K(A1+sT1)/(A2+sT2) _fb__x',),
            params=('K', 'A1', 'T1', 'A2', 'T2'),
            unsupported_lines=(),
            module_name='typ_307__k_a1_st1_a2_st2_fb',
            module_filename='typ_307__k_a1_st1_a2_st2_fb.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='k_a1_st1_a2_st2',
            typ_id='308',
            blkdef_name='K(A1+sT1)/(A2+sT2)',
            sample_display_name='K(A1+sT1)/(A2+sT2)',
            display_label='K(A1+sT1)/(A2+sT2)',
            category_path=('Native', 'Control and Measurement', 'Controllers'),
            inputs=('yi',),
            outputs=('yo',),
            states=('K(A1+sT1)/(A2+sT2)__x',),
            params=('K', 'A1', 'T1', 'A2', 'T2'),
            unsupported_lines=(),
            module_name='typ_308__k_a1_st1_a2_st2',
            module_filename='typ_308__k_a1_st1_a2_st2.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='a23_1_a11_a13a21_a23_stw_1_a11stw',
            typ_id='309',
            blkdef_name='a23(1+(a11-a13a21/a23)sTw)/(1+a11sTw)',
            sample_display_name='a23(1+(a11-a13a21/a23)sTw)/(1+a11sTw)',
            display_label='a23(1+(a11-a13a21/a23)sTw)/(1+a11sTw)',
            category_path=('Native', 'Continuous', 'Transfer Functions and Filters'),
            inputs=('yi',),
            outputs=('yo',),
            states=('a23(1+(a11-a13a21/a23)sTw)/(1+a11sTw)__x',),
            params=('a11', 'a13', 'a21', 'a23', 'Tw'),
            unsupported_lines=(),
            module_name='typ_309__a23_1_a11_a13a21_a23_stw_1_a11stw',
            module_filename='typ_309__a23_1_a11_a13a21_a23_stw_1_a11stw.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='limit',
            typ_id='310',
            blkdef_name='Limit',
            sample_display_name='Limit',
            display_label='Limit',
            category_path=('Native', 'Limits and Nonlinearities', 'Limiters'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=('eps', 'y_max'),
            unsupported_lines=(),
            module_name='typ_310__limit',
            module_filename='typ_310__limit.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='limit_p_form_a',
            typ_id='311',
            blkdef_name='Limit [p',
            sample_display_name='Limit [p',
            display_label='Limit (parameter) [param: eps/y_min]',
            category_path=('Native', 'Limits and Nonlinearities', 'Limiters'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=('eps', 'y_min'),
            unsupported_lines=(),
            module_name='typ_311__limit_p',
            module_filename='typ_311__limit_p.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='limit_p_form_b',
            typ_id='312',
            blkdef_name='Limit [p',
            sample_display_name='Limit [p',
            display_label='Limit (parameter) [param: eps/y_max/y_min]',
            category_path=('Native', 'Limits and Nonlinearities', 'Limiters'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=('eps', 'y_max', 'y_min'),
            unsupported_lines=(),
            module_name='typ_312__limit_p',
            module_filename='typ_312__limit_p.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='limit_p_form_c',
            typ_id='313',
            blkdef_name='Limit [p',
            sample_display_name='Limit [p',
            display_label='Limit (parameter) [param: y_max/y_min]',
            category_path=('Native', 'Limits and Nonlinearities', 'Limiters'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=('y_max', 'y_min'),
            unsupported_lines=(),
            module_name='typ_313__limit_p',
            module_filename='typ_313__limit_p.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='limit_p_complex',
            typ_id='314',
            blkdef_name='Limit [p] (complex)',
            sample_display_name='Limit [p] (complex)',
            display_label='Limit (parameter) (complex)',
            category_path=('Native', 'Complex', 'Operations'),
            inputs=('d', 'q'),
            outputs=('yo_d', 'yo_q'),
            states=(),
            params=('MAG_MAX',),
            unsupported_lines=(),
            module_name='typ_314__limit_p_complex',
            module_filename='typ_314__limit_p_complex.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='limit_p_using_min_max',
            typ_id='315',
            blkdef_name='Limit [p] (using min/max)',
            sample_display_name='Limit [p] (using min/max)',
            display_label='Limit (parameter) (using min/max)',
            category_path=('Native', 'Limits and Nonlinearities', 'Limiters'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=('y_lim',),
            unsupported_lines=(),
            module_name='typ_315__limit_p_using_min_max',
            module_filename='typ_315__limit_p_using_min_max.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='limit_p_eps',
            typ_id='316',
            blkdef_name='Limit [p] _eps',
            sample_display_name='Limit [p] _eps',
            display_label='Limit (parameter) eps',
            category_path=('Native', 'Limits and Nonlinearities', 'Limiters'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=('eps', 'y_lim'),
            unsupported_lines=(),
            module_name='typ_316__limit_p_eps',
            module_filename='typ_316__limit_p_eps.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='limit_p_form_d',
            typ_id='317',
            blkdef_name='Limit [p]',
            sample_display_name='Limit [p]',
            display_label='Limit (parameter) [param: y_lim]',
            category_path=('Native', 'Limits and Nonlinearities', 'Limiters'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=('y_lim',),
            unsupported_lines=(),
            module_name='typ_317__limit_p',
            module_filename='typ_317__limit_p.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='limit_ppp',
            typ_id='318',
            blkdef_name='Limit [ppp',
            sample_display_name='Limit [ppp',
            display_label='Limit (3 parameter inputs)',
            category_path=('Native', 'Limits and Nonlinearities', 'Limiters'),
            inputs=('d', 'q', 'PRIORITISE_AXIS'),
            outputs=('yo_d', 'yo_q'),
            states=(),
            params=('D_MAX', 'Q_MAX', 'MAG_MAX', 'D_MIN', 'Q_MIN'),
            unsupported_lines=(),
            module_name='typ_318__limit_ppp',
            module_filename='typ_318__limit_ppp.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='limit_ppp_complex_with_prio',
            typ_id='319',
            blkdef_name='Limit [ppp] (complex with prio)',
            sample_display_name='Limit [ppp] (complex with prio)',
            display_label='Limit (3 parameter inputs)] (complex with prio)',
            category_path=('Native', 'Complex', 'Operations'),
            inputs=('d', 'q', 'PRIORITISE_AXIS'),
            outputs=('yo_d', 'yo_q'),
            states=(),
            params=('D_MAX', 'Q_MAX', 'MAG_MAX'),
            unsupported_lines=(),
            module_name='typ_319__limit_ppp_complex_with_prio',
            module_filename='typ_319__limit_ppp_complex_with_prio.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='limit_s_form_a',
            typ_id='320',
            blkdef_name='Limit [s',
            sample_display_name='Limit [s',
            display_label='Limit (signal) [signal: y_max/y_min; param: eps]',
            category_path=('Native', 'Limits and Nonlinearities', 'Limiters'),
            inputs=('yi', 'y_max', 'y_min'),
            outputs=('yo',),
            states=(),
            params=('eps',),
            unsupported_lines=(),
            module_name='typ_320__limit_s',
            module_filename='typ_320__limit_s.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='limit_s_form_b',
            typ_id='321',
            blkdef_name='Limit [s',
            sample_display_name='Limit [s',
            display_label='Limit (signal) [signal: y_max/y_min]',
            category_path=('Native', 'Limits and Nonlinearities', 'Limiters'),
            inputs=('yi', 'y_max', 'y_min'),
            outputs=('yo',),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_321__limit_s',
            module_filename='typ_321__limit_s.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='limit_sp',
            typ_id='322',
            blkdef_name='Limit [sp',
            sample_display_name='Limit [sp',
            display_label='Limit (signal + parameter input)',
            category_path=('Native', 'Limits and Nonlinearities', 'Limiters'),
            inputs=('yi', 'yi_max', 'yi_min'),
            outputs=('yo',),
            states=(),
            params=('y_max', 'y_min'),
            unsupported_lines=(),
            module_name='typ_322__limit_sp',
            module_filename='typ_322__limit_sp.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='limit_lower_p',
            typ_id='323',
            blkdef_name='Limit lower [p',
            sample_display_name='Limit lower [p',
            display_label='Limit lower (parameter)',
            category_path=('Native', 'Limits and Nonlinearities', 'Limiters'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=('y_min',),
            unsupported_lines=(),
            module_name='typ_323__limit_lower_p',
            module_filename='typ_323__limit_lower_p.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='limit_upper',
            typ_id='324',
            blkdef_name='Limit upper',
            sample_display_name='Limit upper',
            display_label='Limit upper',
            category_path=('Native', 'Limits and Nonlinearities', 'Limiters'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=('y_max',),
            unsupported_lines=(),
            module_name='typ_324__limit_upper',
            module_filename='typ_324__limit_upper.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='rate_limiter',
            typ_id='325',
            blkdef_name='Rate limiter',
            sample_display_name='Rate limiter',
            display_label='Rate limiter',
            category_path=('Native', 'Limits and Nonlinearities', 'Limiters'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=('grd_up',),
            unsupported_lines=(),
            module_name='typ_325__rate_limiter',
            module_filename='typ_325__rate_limiter.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='rate_limiter_base',
            typ_id='326',
            blkdef_name='Rate limiter base',
            sample_display_name='Rate limiter base',
            display_label='Rate limiter base',
            category_path=('Native', 'Limits and Nonlinearities', 'Limiters'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=('base', 'grd_up'),
            unsupported_lines=(),
            module_name='typ_326__rate_limiter_base',
            module_filename='typ_326__rate_limiter_base.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='rate_limiter_base_p_form_a',
            typ_id='327',
            blkdef_name='Rate limiter base {p',
            sample_display_name='Rate limiter base {p',
            display_label='Rate limiter base (parameter) [param: base/grd_down]',
            category_path=('Native', 'Limits and Nonlinearities', 'Limiters'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=('base', 'grd_down'),
            unsupported_lines=(),
            module_name='typ_327__rate_limiter_base_p',
            module_filename='typ_327__rate_limiter_base_p.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='rate_limiter_base_p_form_b',
            typ_id='328',
            blkdef_name='Rate limiter base {p',
            sample_display_name='Rate limiter base {p',
            display_label='Rate limiter base (parameter) [param: base/grd_up/grd_down]',
            category_path=('Native', 'Limits and Nonlinearities', 'Limiters'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=('base', 'grd_up', 'grd_down'),
            unsupported_lines=(),
            module_name='typ_328__rate_limiter_base_p',
            module_filename='typ_328__rate_limiter_base_p.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='rate_limiter_base_p_form_c',
            typ_id='329',
            blkdef_name='Rate limiter base {p}',
            sample_display_name='Rate limiter base {p}',
            display_label='Rate limiter base (parameter) [param: base/grd]',
            category_path=('Native', 'Limits and Nonlinearities', 'Limiters'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=('base', 'grd'),
            unsupported_lines=(),
            module_name='typ_329__rate_limiter_base_p',
            module_filename='typ_329__rate_limiter_base_p.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='rate_limiter_p_form_a',
            typ_id='330',
            blkdef_name='Rate limiter {p',
            sample_display_name='Rate limiter {p',
            display_label='Rate limiter (parameter) [param: grd_down]',
            category_path=('Native', 'Limits and Nonlinearities', 'Limiters'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=('grd_down',),
            unsupported_lines=(),
            module_name='typ_330__rate_limiter_p',
            module_filename='typ_330__rate_limiter_p.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='rate_limiter_p_form_b',
            typ_id='331',
            blkdef_name='Rate limiter {p',
            sample_display_name='Rate limiter {p',
            display_label='Rate limiter (parameter) [param: grd_up/grd_down]',
            category_path=('Native', 'Limits and Nonlinearities', 'Limiters'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=('grd_up', 'grd_down'),
            unsupported_lines=(),
            module_name='typ_331__rate_limiter_p',
            module_filename='typ_331__rate_limiter_p.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='rate_limiter_p_form_c',
            typ_id='332',
            blkdef_name='Rate limiter {p}',
            sample_display_name='Rate limiter {p}',
            display_label='Rate limiter (parameter) [param: grd]',
            category_path=('Native', 'Limits and Nonlinearities', 'Limiters'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=('grd',),
            unsupported_lines=(),
            module_name='typ_332__rate_limiter_p',
            module_filename='typ_332__rate_limiter_p.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='rate_limiter_s',
            typ_id='333',
            blkdef_name='Rate limiter {s',
            sample_display_name='Rate limiter {s',
            display_label='Rate limiter (signal)',
            category_path=('Native', 'Limits and Nonlinearities', 'Limiters'),
            inputs=('yi', 'grd_up', 'grd_down'),
            outputs=('yo',),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_333__rate_limiter_s',
            module_filename='typ_333__rate_limiter_s.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='and2',
            typ_id='334',
            blkdef_name='AND2',
            sample_display_name='AND2',
            display_label='AND (2 inputs)',
            category_path=('Native', 'Logic and Events', 'Gates and Memory'),
            inputs=('yi1', 'yi2'),
            outputs=('yo',),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_334__and2',
            module_filename='typ_334__and2.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='and3',
            typ_id='335',
            blkdef_name='AND3',
            sample_display_name='AND3',
            display_label='AND (3 inputs)',
            category_path=('Native', 'Logic and Events', 'Gates and Memory'),
            inputs=('yi1', 'yi2', 'yi3'),
            outputs=('yo',),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_335__and3',
            module_filename='typ_335__and3.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='and4',
            typ_id='336',
            blkdef_name='AND4',
            sample_display_name='AND4',
            display_label='AND (4 inputs)',
            category_path=('Native', 'Logic and Events', 'Gates and Memory'),
            inputs=('yi1', 'yi2', 'yi3', 'yi4'),
            outputs=('yo',),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_336__and4',
            module_filename='typ_336__and4.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='eor',
            typ_id='337',
            blkdef_name='EOR',
            sample_display_name='EOR',
            display_label='XOR',
            category_path=('Native', 'Logic and Events', 'Gates and Memory'),
            inputs=('yi1', 'yi2'),
            outputs=('yo',),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_337__eor',
            module_filename='typ_337__eor.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='equal',
            typ_id='338',
            blkdef_name='EQUAL',
            sample_display_name='EQUAL',
            display_label='EQUAL',
            category_path=('Native', 'Math and Functions', 'Elementary Functions'),
            inputs=('yi1', 'yi2'),
            outputs=('yo',),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_338__equal',
            module_filename='typ_338__equal.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='nor',
            typ_id='339',
            blkdef_name='NOR',
            sample_display_name='NOR',
            display_label='NOR',
            category_path=('Native', 'Logic and Events', 'Gates and Memory'),
            inputs=('yi1', 'yi2'),
            outputs=('yo',),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_339__nor',
            module_filename='typ_339__nor.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='not',
            typ_id='340',
            blkdef_name='NOT',
            sample_display_name='NOT',
            display_label='NOT',
            category_path=('Native', 'Logic and Events', 'Gates and Memory'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_340__not',
            module_filename='typ_340__not.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='or2',
            typ_id='341',
            blkdef_name='OR2',
            sample_display_name='OR2',
            display_label='OR (2 inputs)',
            category_path=('Native', 'Logic and Events', 'Gates and Memory'),
            inputs=('yi1', 'yi2'),
            outputs=('yo',),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_341__or2',
            module_filename='typ_341__or2.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='or3',
            typ_id='342',
            blkdef_name='OR3',
            sample_display_name='OR3',
            display_label='OR (3 inputs)',
            category_path=('Native', 'Logic and Events', 'Gates and Memory'),
            inputs=('yi1', 'yi2', 'yi3'),
            outputs=('yo',),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_342__or3',
            module_filename='typ_342__or3.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='or4',
            typ_id='343',
            blkdef_name='OR4',
            sample_display_name='OR4',
            display_label='OR (4 inputs)',
            category_path=('Native', 'Logic and Events', 'Gates and Memory'),
            inputs=('yi1', 'yi2', 'yi3', 'yi4'),
            outputs=('yo',),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_343__or4',
            module_filename='typ_343__or4.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='2_out_of_3_ip',
            typ_id='344',
            blkdef_name='2_out_of_3 _ip',
            sample_display_name='2_out_of_3 _ip',
            display_label='2-out-of-3 (pulse)',
            category_path=('Native', 'Waveforms and Time', 'Signal Generators'),
            inputs=('yi1', 'yi2', 'yi3'),
            outputs=('yo',),
            states=(),
            params=('Tpick', 'Tdrop'),
            unsupported_lines=(),
            module_name='typ_344__2_out_of_3_ip',
            module_filename='typ_344__2_out_of_3_ip.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='and2_ip',
            typ_id='345',
            blkdef_name='AND2 _ip',
            sample_display_name='AND2 _ip',
            display_label='AND (2 inputs, pulse)',
            category_path=('Native', 'Waveforms and Time', 'Signal Generators'),
            inputs=('yi1', 'yi2'),
            outputs=('yo',),
            states=(),
            params=('Tpick', 'Tdrop'),
            unsupported_lines=(),
            module_name='typ_345__and2_ip',
            module_filename='typ_345__and2_ip.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='and3_ip',
            typ_id='346',
            blkdef_name='AND3 _ip',
            sample_display_name='AND3 _ip',
            display_label='AND (3 inputs, pulse)',
            category_path=('Native', 'Waveforms and Time', 'Signal Generators'),
            inputs=('yi1', 'yi2', 'yi3'),
            outputs=('yo',),
            states=(),
            params=('Tpick', 'Tdrop'),
            unsupported_lines=(),
            module_name='typ_346__and3_ip',
            module_filename='typ_346__and3_ip.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='invert_logic_ip',
            typ_id='347',
            blkdef_name='Invert Logic _ip',
            sample_display_name='Invert Logic _ip',
            display_label='Invert Logic (pulse)',
            category_path=('Native', 'Waveforms and Time', 'Signal Generators'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=('Tpick', 'Tdrop'),
            unsupported_lines=(),
            module_name='typ_347__invert_logic_ip',
            module_filename='typ_347__invert_logic_ip.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='not_ip',
            typ_id='348',
            blkdef_name='NOT _ip',
            sample_display_name='NOT _ip',
            display_label='NOT (pulse)',
            category_path=('Native', 'Waveforms and Time', 'Signal Generators'),
            inputs=('yi1',),
            outputs=('yo',),
            states=(),
            params=('Tpick', 'Tdrop'),
            unsupported_lines=(),
            module_name='typ_348__not_ip',
            module_filename='typ_348__not_ip.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='or2_ip',
            typ_id='349',
            blkdef_name='OR2 _ip',
            sample_display_name='OR2 _ip',
            display_label='OR (2 inputs, pulse)',
            category_path=('Native', 'Waveforms and Time', 'Signal Generators'),
            inputs=('yi1', 'yi2'),
            outputs=('yo',),
            states=(),
            params=('Tpick', 'Tdrop'),
            unsupported_lines=(),
            module_name='typ_349__or2_ip',
            module_filename='typ_349__or2_ip.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='or3_ip',
            typ_id='350',
            blkdef_name='OR3 _ip',
            sample_display_name='OR3 _ip',
            display_label='OR (3 inputs, pulse)',
            category_path=('Native', 'Waveforms and Time', 'Signal Generators'),
            inputs=('yi1', 'yi2', 'yi3'),
            outputs=('yo',),
            states=(),
            params=('Tpick', 'Tdrop'),
            unsupported_lines=(),
            module_name='typ_350__or3_ip',
            module_filename='typ_350__or3_ip.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='bistable',
            typ_id='351',
            blkdef_name='Bistable',
            sample_display_name='Bistable',
            display_label='Bistable',
            category_path=('Native', 'Logic and Events', 'Gates and Memory'),
            inputs=('S', 'R'),
            outputs=('Q', 'not_Q'),
            states=(),
            params=('PRIO_SET',),
            unsupported_lines=(),
            module_name='typ_351__bistable',
            module_filename='typ_351__bistable.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='edge_detector',
            typ_id='352',
            blkdef_name='Edge detector',
            sample_display_name='Edge detector',
            display_label='Edge detector',
            category_path=('Native', 'Logic and Events', 'Gates and Memory'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=('ACTIVATE_ON_RISE', 'ACTIVATE_ON_FALL', 'THRESHOLD'),
            unsupported_lines=(),
            module_name='typ_352__edge_detector',
            module_filename='typ_352__edge_detector.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='monostable',
            typ_id='353',
            blkdef_name='Monostable',
            sample_display_name='Monostable',
            display_label='Monostable',
            category_path=('Native', 'Logic and Events', 'Gates and Memory'),
            inputs=('yi',),
            outputs=('yo',),
            states=('Monostable__x',),
            params=('T',),
            unsupported_lines=(),
            module_name='typ_353__monostable',
            module_filename='typ_353__monostable.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='abs',
            typ_id='354',
            blkdef_name='ABS',
            sample_display_name='ABS',
            display_label='ABS',
            category_path=('Native', 'Math and Functions', 'Elementary Functions'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_354__abs',
            module_filename='typ_354__abs.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='ceil',
            typ_id='355',
            blkdef_name='CEIL',
            sample_display_name='CEIL',
            display_label='CEIL',
            category_path=('Native', 'Math and Functions', 'Elementary Functions'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_355__ceil',
            module_filename='typ_355__ceil.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='exp',
            typ_id='356',
            blkdef_name='EXP',
            sample_display_name='EXP',
            display_label='EXP',
            category_path=('Native', 'Math and Functions', 'Elementary Functions'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_356__exp',
            module_filename='typ_356__exp.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='floor',
            typ_id='357',
            blkdef_name='FLOOR',
            sample_display_name='FLOOR',
            display_label='FLOOR',
            category_path=('Native', 'Math and Functions', 'Elementary Functions'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_357__floor',
            module_filename='typ_357__floor.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='frac',
            typ_id='358',
            blkdef_name='FRAC',
            sample_display_name='FRAC',
            display_label='FRAC',
            category_path=('Native', 'Math and Functions', 'Elementary Functions'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_358__frac',
            module_filename='typ_358__frac.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='ln',
            typ_id='359',
            blkdef_name='LN',
            sample_display_name='LN',
            display_label='LN',
            category_path=('Native', 'Math and Functions', 'Elementary Functions'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_359__ln',
            module_filename='typ_359__ln.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='log',
            typ_id='360',
            blkdef_name='LOG',
            sample_display_name='LOG',
            display_label='LOG',
            category_path=('Native', 'Math and Functions', 'Elementary Functions'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_360__log',
            module_filename='typ_360__log.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='max2',
            typ_id='361',
            blkdef_name='MAX2',
            sample_display_name='MAX2',
            display_label='MAX (2 inputs)',
            category_path=('Native', 'Continuous', 'Transfer Functions and Filters'),
            inputs=('yi1', 'yi2'),
            outputs=('yo',),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_361__max2',
            module_filename='typ_361__max2.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='max3',
            typ_id='362',
            blkdef_name='MAX3',
            sample_display_name='MAX3',
            display_label='MAX (3 inputs)',
            category_path=('Native', 'Continuous', 'Transfer Functions and Filters'),
            inputs=('yi1', 'yi2', 'yi3'),
            outputs=('yo',),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_362__max3',
            module_filename='typ_362__max3.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='max4',
            typ_id='363',
            blkdef_name='MAX4',
            sample_display_name='MAX4',
            display_label='MAX (4 inputs)',
            category_path=('Native', 'Continuous', 'Transfer Functions and Filters'),
            inputs=('yi1', 'yi2', 'yi3', 'yi4'),
            outputs=('yo',),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_363__max4',
            module_filename='typ_363__max4.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='min2',
            typ_id='364',
            blkdef_name='MIN2',
            sample_display_name='MIN2',
            display_label='MIN (2 inputs)',
            category_path=('Native', 'Continuous', 'Transfer Functions and Filters'),
            inputs=('yi1', 'yi2'),
            outputs=('yo',),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_364__min2',
            module_filename='typ_364__min2.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='min3',
            typ_id='365',
            blkdef_name='MIN3',
            sample_display_name='MIN3',
            display_label='MIN (3 inputs)',
            category_path=('Native', 'Continuous', 'Transfer Functions and Filters'),
            inputs=('yi1', 'yi2', 'yi3'),
            outputs=('yo',),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_365__min3',
            module_filename='typ_365__min3.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='min4',
            typ_id='366',
            blkdef_name='MIN4',
            sample_display_name='MIN4',
            display_label='MIN (4 inputs)',
            category_path=('Native', 'Continuous', 'Transfer Functions and Filters'),
            inputs=('yi1', 'yi2', 'yi3', 'yi4'),
            outputs=('yo',),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_366__min4',
            module_filename='typ_366__min4.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='modulo',
            typ_id='367',
            blkdef_name='MODULO',
            sample_display_name='MODULO',
            display_label='MODULO',
            category_path=('Native', 'Math and Functions', 'Elementary Functions'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=('n',),
            unsupported_lines=(),
            module_name='typ_367__modulo',
            module_filename='typ_367__modulo.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='reciprocal_fb',
            typ_id='368',
            blkdef_name='RECIPROCAL _fb',
            sample_display_name='RECIPROCAL _fb',
            display_label='Reciprocal (feedback)',
            category_path=('Native', 'Math and Functions', 'Elementary Functions'),
            inputs=('u',),
            outputs=('yo',),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_368__reciprocal_fb',
            module_filename='typ_368__reciprocal_fb.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='reciprocal',
            typ_id='369',
            blkdef_name='RECIPROCAL',
            sample_display_name='RECIPROCAL',
            display_label='Reciprocal',
            category_path=('Native', 'Math and Functions', 'Elementary Functions'),
            inputs=('u',),
            outputs=('yo',),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_369__reciprocal',
            module_filename='typ_369__reciprocal.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='round',
            typ_id='370',
            blkdef_name='ROUND',
            sample_display_name='ROUND',
            display_label='ROUND',
            category_path=('Native', 'Math and Functions', 'Elementary Functions'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_370__round',
            module_filename='typ_370__round.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='sign',
            typ_id='371',
            blkdef_name='SIGN',
            sample_display_name='SIGN',
            display_label='SIGN',
            category_path=('Native', 'Math and Functions', 'Elementary Functions'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_371__sign',
            module_filename='typ_371__sign.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='sqrt',
            typ_id='372',
            blkdef_name='SQRT',
            sample_display_name='SQRT',
            display_label='SQRT',
            category_path=('Native', 'Math and Functions', 'Elementary Functions'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_372__sqrt',
            module_filename='typ_372__sqrt.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='x_2',
            typ_id='373',
            blkdef_name='x^2',
            sample_display_name='x^2',
            display_label='x^2',
            category_path=('Native', 'Math and Functions', 'Elementary Functions'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_373__x_2',
            module_filename='typ_373__x_2.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='x_p',
            typ_id='374',
            blkdef_name='x^p',
            sample_display_name='x^p',
            display_label='x^p',
            category_path=('Native', 'Math and Functions', 'Elementary Functions'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=('p',),
            unsupported_lines=(),
            module_name='typ_374__x_p',
            module_filename='typ_374__x_p.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='add_complex',
            typ_id='375',
            blkdef_name='ADD COMPLEX',
            sample_display_name='ADD COMPLEX',
            display_label='ADD COMPLEX',
            category_path=('Native', 'Complex', 'Operations'),
            inputs=('re1', 'im1', 're2', 'im2'),
            outputs=('re', 'im'),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_375__add_complex',
            module_filename='typ_375__add_complex.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='conj_complex',
            typ_id='376',
            blkdef_name='CONJ COMPLEX',
            sample_display_name='CONJ COMPLEX',
            display_label='CONJ COMPLEX',
            category_path=('Native', 'Complex', 'Operations'),
            inputs=('re1', 'im1'),
            outputs=('re', 'im'),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_376__conj_complex',
            module_filename='typ_376__conj_complex.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='div_complex',
            typ_id='377',
            blkdef_name='DIV COMPLEX',
            sample_display_name='DIV COMPLEX',
            display_label='DIV COMPLEX',
            category_path=('Native', 'Complex', 'Operations'),
            inputs=('re1', 'im1', 're2', 'im2'),
            outputs=('re', 'im'),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_377__div_complex',
            module_filename='typ_377__div_complex.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='mag_complex',
            typ_id='378',
            blkdef_name='MAG COMPLEX',
            sample_display_name='MAG COMPLEX',
            display_label='MAG COMPLEX',
            category_path=('Native', 'Complex', 'Operations'),
            inputs=('re', 'im'),
            outputs=('mag',),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_378__mag_complex',
            module_filename='typ_378__mag_complex.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='mul_complex',
            typ_id='379',
            blkdef_name='MUL COMPLEX',
            sample_display_name='MUL COMPLEX',
            display_label='MUL COMPLEX',
            category_path=('Native', 'Complex', 'Operations'),
            inputs=('re1', 'im1', 're2', 'im2'),
            outputs=('re', 'im'),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_379__mul_complex',
            module_filename='typ_379__mul_complex.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='sub_complex',
            typ_id='380',
            blkdef_name='SUB COMPLEX',
            sample_display_name='SUB COMPLEX',
            display_label='SUB COMPLEX',
            category_path=('Native', 'Complex', 'Operations'),
            inputs=('re1', 'im1', 're2', 'im2'),
            outputs=('re', 'im'),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_380__sub_complex',
            module_filename='typ_380__sub_complex.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='to_polar_complex',
            typ_id='381',
            blkdef_name='TO POLAR COMPLEX',
            sample_display_name='TO POLAR COMPLEX',
            display_label='TO POLAR COMPLEX',
            category_path=('Native', 'Complex', 'Operations'),
            inputs=('re', 'im'),
            outputs=('mag', 'phi'),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_381__to_polar_complex',
            module_filename='typ_381__to_polar_complex.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='to_rectangular_complex',
            typ_id='382',
            blkdef_name='TO RECTANGULAR COMPLEX',
            sample_display_name='TO RECTANGULAR COMPLEX',
            display_label='TO RECTANGULAR COMPLEX',
            category_path=('Native', 'Complex', 'Operations'),
            inputs=('mag', 'phi'),
            outputs=('re', 'im'),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_382__to_rectangular_complex',
            module_filename='typ_382__to_rectangular_complex.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='acos',
            typ_id='383',
            blkdef_name='ACOS',
            sample_display_name='ACOS',
            display_label='ACOS',
            category_path=('Native', 'Math and Functions', 'Elementary Functions'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_383__acos',
            module_filename='typ_383__acos.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='asin',
            typ_id='384',
            blkdef_name='ASIN',
            sample_display_name='ASIN',
            display_label='ASIN',
            category_path=('Native', 'Math and Functions', 'Elementary Functions'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_384__asin',
            module_filename='typ_384__asin.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='atan',
            typ_id='385',
            blkdef_name='ATAN',
            sample_display_name='ATAN',
            display_label='ATAN',
            category_path=('Native', 'Math and Functions', 'Elementary Functions'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_385__atan',
            module_filename='typ_385__atan.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='atan2',
            typ_id='386',
            blkdef_name='ATAN2',
            sample_display_name='ATAN2',
            display_label='ATAN2',
            category_path=('Native', 'Math and Functions', 'Elementary Functions'),
            inputs=('re', 'im'),
            outputs=('yo',),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_386__atan2',
            module_filename='typ_386__atan2.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='atan2d',
            typ_id='387',
            blkdef_name='ATAN2D',
            sample_display_name='ATAN2D',
            display_label='ATAN2D',
            category_path=('Native', 'Math and Functions', 'Elementary Functions'),
            inputs=('re', 'im'),
            outputs=('yo',),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_387__atan2d',
            module_filename='typ_387__atan2d.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='atand',
            typ_id='388',
            blkdef_name='ATAND',
            sample_display_name='ATAND',
            display_label='ATAND',
            category_path=('Native', 'Math and Functions', 'Elementary Functions'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_388__atand',
            module_filename='typ_388__atand.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='cos',
            typ_id='389',
            blkdef_name='COS',
            sample_display_name='COS',
            display_label='COS',
            category_path=('Native', 'Math and Functions', 'Elementary Functions'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_389__cos',
            module_filename='typ_389__cos.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='cosd',
            typ_id='390',
            blkdef_name='COSD',
            sample_display_name='COSD',
            display_label='COSD',
            category_path=('Native', 'Math and Functions', 'Elementary Functions'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_390__cosd',
            module_filename='typ_390__cosd.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='cosh',
            typ_id='391',
            blkdef_name='COSH',
            sample_display_name='COSH',
            display_label='COSH',
            category_path=('Native', 'Math and Functions', 'Elementary Functions'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_391__cosh',
            module_filename='typ_391__cosh.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='coshd',
            typ_id='392',
            blkdef_name='COSHD',
            sample_display_name='COSHD',
            display_label='COSHD',
            category_path=('Native', 'Math and Functions', 'Elementary Functions'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_392__coshd',
            module_filename='typ_392__coshd.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='sin',
            typ_id='393',
            blkdef_name='SIN',
            sample_display_name='SIN',
            display_label='SIN',
            category_path=('Native', 'Math and Functions', 'Elementary Functions'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_393__sin',
            module_filename='typ_393__sin.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='sind',
            typ_id='394',
            blkdef_name='SIND',
            sample_display_name='SIND',
            display_label='SIND',
            category_path=('Native', 'Math and Functions', 'Elementary Functions'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_394__sind',
            module_filename='typ_394__sind.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='sinh',
            typ_id='395',
            blkdef_name='SINH',
            sample_display_name='SINH',
            display_label='SINH',
            category_path=('Native', 'Math and Functions', 'Elementary Functions'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_395__sinh',
            module_filename='typ_395__sinh.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='sinhd',
            typ_id='396',
            blkdef_name='SINHD',
            sample_display_name='SINHD',
            display_label='SINHD',
            category_path=('Native', 'Math and Functions', 'Elementary Functions'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_396__sinhd',
            module_filename='typ_396__sinhd.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='tan',
            typ_id='397',
            blkdef_name='TAN',
            sample_display_name='TAN',
            display_label='TAN',
            category_path=('Native', 'Math and Functions', 'Elementary Functions'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_397__tan',
            module_filename='typ_397__tan.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='tand',
            typ_id='398',
            blkdef_name='TAND',
            sample_display_name='TAND',
            display_label='TAND',
            category_path=('Native', 'Math and Functions', 'Elementary Functions'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_398__tand',
            module_filename='typ_398__tand.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='tanh',
            typ_id='399',
            blkdef_name='TANH',
            sample_display_name='TANH',
            display_label='TANH',
            category_path=('Native', 'Math and Functions', 'Elementary Functions'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_399__tanh',
            module_filename='typ_399__tanh.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='tanhd',
            typ_id='400',
            blkdef_name='TANHD',
            sample_display_name='TANHD',
            display_label='TANHD',
            category_path=('Native', 'Math and Functions', 'Elementary Functions'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_400__tanhd',
            module_filename='typ_400__tanhd.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_2hs',
            typ_id='401',
            blkdef_name='1/(2Hs)',
            sample_display_name='1/(2Hs)',
            display_label='1/(2Hs)',
            category_path=('Native', 'Continuous', 'Transfer Functions and Filters'),
            inputs=('yi',),
            outputs=('yo',),
            states=('1/(2Hs)__x',),
            params=('H',),
            unsupported_lines=(),
            module_name='typ_401__1_2hs',
            module_filename='typ_401__1_2hs.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='accelerating_power_simple',
            typ_id='402',
            blkdef_name='Accelerating Power (simple)',
            sample_display_name='Accelerating Power (simple)',
            display_label='Accelerating Power (simple)',
            category_path=('Native', 'Control and Measurement', 'Measurements and Units'),
            inputs=('speed', 'xmt', 'xme'),
            outputs=('yo',),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_402__accelerating_power_simple',
            module_filename='typ_402__accelerating_power_simple.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='accelerating_power_ipb',
            typ_id='403',
            blkdef_name='Accelerating Power IPB',
            sample_display_name='Accelerating Power IPB',
            display_label='Accelerating Power IPB',
            category_path=('Native', 'Control and Measurement', 'Measurements and Units'),
            inputs=('cosn', 'speed', 'xmt', 'xme'),
            outputs=('Pa',),
            states=(),
            params=('IPB',),
            unsupported_lines=(),
            module_name='typ_403__accelerating_power_ipb',
            module_filename='typ_403__accelerating_power_ipb.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='gear_box',
            typ_id='404',
            blkdef_name='Gear Box',
            sample_display_name='Gear Box',
            display_label='Gear Box',
            category_path=('Native', 'Mechanical', 'Drive Train'),
            inputs=('speed',),
            outputs=('omega',),
            states=(),
            params=('Nratio', 'RPM_syn'),
            unsupported_lines=(),
            module_name='typ_404__gear_box',
            module_filename='typ_404__gear_box.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='mass_j',
            typ_id='405',
            blkdef_name='Mass_J',
            sample_display_name='Mass_J',
            display_label='Mass J',
            category_path=('Native', 'Mechanical', 'Drive Train'),
            inputs=('M1', 'M2'),
            outputs=('omega',),
            states=('Mass_J__xomega',),
            params=('J',),
            unsupported_lines=(),
            module_name='typ_405__mass_j',
            module_filename='typ_405__mass_j.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='p_omg_torque',
            typ_id='406',
            blkdef_name='P/omg -> Torque',
            sample_display_name='P/omg -> Torque',
            display_label='P/omg -> Torque',
            category_path=('Native', 'Mechanical', 'Drive Train'),
            inputs=('Power', 'omega'),
            outputs=('Torque',),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_406__p_omg_torque',
            module_filename='typ_406__p_omg_torque.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='pt_pturb',
            typ_id='407',
            blkdef_name='Pt/Pturb',
            sample_display_name='Pt/Pturb',
            display_label='Pt/Pturb',
            category_path=('Native', 'Mechanical', 'Drive Train'),
            inputs=('pturb', 'sgnn', 'cosn'),
            outputs=('pt',),
            states=(),
            params=('PN',),
            unsupported_lines=(),
            module_name='typ_407__pt_pturb',
            module_filename='typ_407__pt_pturb.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='shaft_j_k_and_pin',
            typ_id='408',
            blkdef_name='Shaft J-k and Pin',
            sample_display_name='Shaft J-k and Pin',
            display_label='Shaft J-k and Pin',
            category_path=('Native', 'Mechanical', 'Drive Train'),
            inputs=('omega_k', 'Pin'),
            outputs=('omega_j', 'torque_jk'),
            states=(),
            params=('K_jk', 'D_jk', 'D_jj', 'H_j', 'fnom'),
            unsupported_lines=(),
            module_name='typ_408__shaft_j_k_and_pin',
            module_filename='typ_408__shaft_j_k_and_pin.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='2pi_form_b',
            typ_id='411',
            blkdef_name='2PI',
            sample_display_name='2PI',
            display_label='2PI [form B]',
            category_path=('Native', 'Math and Functions', 'Constants and Scaling'),
            inputs=(),
            outputs=('yo',),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_411__2pi',
            module_filename='typ_411__2pi.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='c_form_c',
            typ_id='412',
            blkdef_name='C',
            sample_display_name='C',
            display_label='C [param: C; form B]',
            category_path=('Native', 'Math and Functions', 'Constants and Scaling'),
            inputs=(),
            outputs=('yo',),
            states=(),
            params=('C',),
            unsupported_lines=(),
            module_name='typ_412__c',
            module_filename='typ_412__c.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='shaft_i_j_k_and_pin',
            typ_id='414',
            blkdef_name='Shaft i-J-k and Pin',
            sample_display_name='Shaft i-J-k and Pin',
            display_label='Shaft i-J-k and Pin',
            category_path=('Native', 'Mechanical', 'Drive Train'),
            inputs=('omega_k', 'omega_i', 'torque_ij', 'Pin'),
            outputs=('omega_j', 'torque_jk'),
            states=(),
            params=('K_jk', 'D_jk', 'D_ij', 'D_jj', 'H_j', 'fnom'),
            unsupported_lines=(),
            module_name='typ_414__shaft_i_j_k_and_pin',
            module_filename='typ_414__shaft_i_j_k_and_pin.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='2pi_form_c',
            typ_id='417',
            blkdef_name='2PI',
            sample_display_name='2PI',
            display_label='2PI [form C]',
            category_path=('Native', 'Math and Functions', 'Constants and Scaling'),
            inputs=(),
            outputs=('yo',),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_417__2pi',
            module_filename='typ_417__2pi.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='c_form_d',
            typ_id='418',
            blkdef_name='C',
            sample_display_name='C',
            display_label='C [param: C; form C]',
            category_path=('Native', 'Math and Functions', 'Constants and Scaling'),
            inputs=(),
            outputs=('yo',),
            states=(),
            params=('C',),
            unsupported_lines=(),
            module_name='typ_418__c',
            module_filename='typ_418__c.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='shaft_i_j_k',
            typ_id='420',
            blkdef_name='Shaft i-J-k',
            sample_display_name='Shaft i-J-k',
            display_label='Shaft i-J-k',
            category_path=('Native', 'Mechanical', 'Drive Train'),
            inputs=('omega_k', 'omega_i', 'torque_ij'),
            outputs=('omega_j', 'torque_jk'),
            states=(),
            params=('K_jk', 'D_jk', 'D_ij', 'D_jj', 'H_j', 'fnom'),
            unsupported_lines=(),
            module_name='typ_420__shaft_i_j_k',
            module_filename='typ_420__shaft_i_j_k.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='2pi_form_d',
            typ_id='423',
            blkdef_name='2PI',
            sample_display_name='2PI',
            display_label='2PI [form D]',
            category_path=('Native', 'Math and Functions', 'Constants and Scaling'),
            inputs=(),
            outputs=('yo',),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_423__2pi',
            module_filename='typ_423__2pi.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='c_form_e',
            typ_id='424',
            blkdef_name='C',
            sample_display_name='C',
            display_label='C [param: C; form D]',
            category_path=('Native', 'Math and Functions', 'Constants and Scaling'),
            inputs=(),
            outputs=('yo',),
            states=(),
            params=('C',),
            unsupported_lines=(),
            module_name='typ_424__c',
            module_filename='typ_424__c.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='shaft_i_j',
            typ_id='426',
            blkdef_name='Shaft i-J',
            sample_display_name='Shaft i-J',
            display_label='Shaft i-J',
            category_path=('Native', 'Mechanical', 'Drive Train'),
            inputs=('omega_i',),
            outputs=('torque_ji',),
            states=(),
            params=('K_ji', 'D_ji', 'D_jj', 'H_j', 'fnom'),
            unsupported_lines=(),
            module_name='typ_426__shaft_i_j',
            module_filename='typ_426__shaft_i_j.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='2pi_form_e',
            typ_id='429',
            blkdef_name='2PI',
            sample_display_name='2PI',
            display_label='2PI [form E]',
            category_path=('Native', 'Math and Functions', 'Constants and Scaling'),
            inputs=(),
            outputs=('yo',),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_429__2pi',
            module_filename='typ_429__2pi.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='c_form_f',
            typ_id='430',
            blkdef_name='C',
            sample_display_name='C',
            display_label='C [param: C; form E]',
            category_path=('Native', 'Math and Functions', 'Constants and Scaling'),
            inputs=(),
            outputs=('yo',),
            states=(),
            params=('C',),
            unsupported_lines=(),
            module_name='typ_430__c',
            module_filename='typ_430__c.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='spring',
            typ_id='432',
            blkdef_name='Spring',
            sample_display_name='Spring',
            display_label='Spring',
            category_path=('Native', 'Mechanical', 'Drive Train'),
            inputs=('omega1', 'omega2'),
            outputs=('M',),
            states=('Spring__xphi',),
            params=('K', 'D'),
            unsupported_lines=(),
            module_name='typ_432__spring',
            module_filename='typ_432__spring.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_st_kst_p',
            typ_id='433',
            blkdef_name='(1+sT)/KsT [(p',
            sample_display_name='(1+sT)/KsT [(p',
            display_label='(1+sT)/KsT (parameter input)',
            category_path=('Native', 'Continuous', 'Transfer Functions and Filters'),
            inputs=('yi',),
            outputs=('yo',),
            states=('(1+sT)/KsT [(p__x',),
            params=('K', 'T', 'y_max', 'y_min'),
            unsupported_lines=(),
            module_name='typ_433__1_st_kst_p',
            module_filename='typ_433__1_st_kst_p.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_st_kst_p_p',
            typ_id='434',
            blkdef_name='(1+sT)/KsT {p}[(p',
            sample_display_name='(1+sT)/KsT {p}[(p',
            display_label='(1+sT)/KsT (parameter) (parameter input)',
            category_path=('Native', 'Continuous', 'Transfer Functions and Filters'),
            inputs=('yi',),
            outputs=('yo',),
            states=('(1+sT)/KsT {p}[(p__x',),
            params=('K', 'T', 'ylim', 'y_max', 'y_min'),
            unsupported_lines=(),
            module_name='typ_434__1_st_kst_p_p',
            module_filename='typ_434__1_st_kst_p_p.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_stb_sta',
            typ_id='435',
            blkdef_name='(1+sTb)/sTa',
            sample_display_name='(1+sTb)/sTa',
            display_label='(1+sTb)/sTa',
            category_path=('Native', 'Continuous', 'Transfer Functions and Filters'),
            inputs=('yi',),
            outputs=('yo',),
            states=('(1+sTb)/sTa__x',),
            params=('Tb', 'Ta'),
            unsupported_lines=(),
            module_name='typ_435__1_stb_sta',
            module_filename='typ_435__1_stb_sta.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_stp_sti',
            typ_id='436',
            blkdef_name='(1+sTp)/sTi',
            sample_display_name='(1+sTp)/sTi',
            display_label='(1+sTp)/sTi',
            category_path=('Native', 'Continuous', 'Transfer Functions and Filters'),
            inputs=('yi',),
            outputs=('yo',),
            states=('(1+sTp)/sTi__x',),
            params=('Ti', 'Tp', 'y_max'),
            unsupported_lines=(),
            module_name='typ_436__1_stp_sti',
            module_filename='typ_436__1_stp_sti.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='1_k_st_form_b',
            typ_id='437',
            blkdef_name='1+K/sT',
            sample_display_name='1+K/sT',
            display_label='1+K/sT',
            category_path=('Native', 'Control and Measurement', 'Controllers'),
            inputs=('yi',),
            outputs=('yo',),
            states=('1+K/sT__x',),
            params=('K', 'T'),
            unsupported_lines=(),
            module_name='typ_437__1_k_st',
            module_filename='typ_437__1_k_st.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='kc_1_sti_p_form_a',
            typ_id='438',
            blkdef_name='Kc+1/sTi [(p',
            sample_display_name='Kc+1/sTi [(p',
            display_label='Kc+1/sTi (parameter input) [1 input; param: K_p/T_p/theta_p+3; 1 state]',
            category_path=('Native', 'Control and Measurement', 'Controllers'),
            inputs=('yi',),
            outputs=('yo',),
            states=('Kc+1/sTi [(p__x',),
            params=('K_p', 'T_p', 'theta_p', 'ControlTuning', 'y_max', 'y_min'),
            unsupported_lines=(),
            module_name='typ_438__kc_1_sti_p',
            module_filename='typ_438__kc_1_sti_p.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='kc_1_sti_p_form_b',
            typ_id='439',
            blkdef_name='Kc+1/sTi [(p',
            sample_display_name='Kc+1/sTi [(p',
            display_label='Kc+1/sTi (parameter input) [1 input; param: K_p/T_rise/theta_p+3; 1 state]',
            category_path=('Native', 'Control and Measurement', 'Controllers'),
            inputs=('yi',),
            outputs=('yo',),
            states=('Kc+1/sTi [(p__x',),
            params=('K_p', 'T_rise', 'theta_p', 'ControlTuning', 'y_max', 'y_min'),
            unsupported_lines=(),
            module_name='typ_439__kc_1_sti_p',
            module_filename='typ_439__kc_1_sti_p.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='kp_1_ti_s_s_s',
            typ_id='440',
            blkdef_name='Kp(1/Ti+s)/s (s)',
            sample_display_name='Kp(1/Ti+s)/s (s)',
            display_label='Kp(1/Ti+s)/s (signal)',
            category_path=('Native', 'Control and Measurement', 'Controllers'),
            inputs=('yi', 'yo_lim'),
            outputs=('yo',),
            states=('Kp(1/Ti+s)/s (s)__x',),
            params=('Kp', 'Ti', 'Tt'),
            unsupported_lines=(),
            module_name='typ_440__kp_1_ti_s_s_s',
            module_filename='typ_440__kp_1_ti_s_s_s.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='kp_1_ti_s_s',
            typ_id='441',
            blkdef_name='Kp(1/Ti+s)/s',
            sample_display_name='Kp(1/Ti+s)/s',
            display_label='Kp(1/Ti+s)/s',
            category_path=('Native', 'Control and Measurement', 'Controllers'),
            inputs=('yi',),
            outputs=('yo',),
            states=('Kp(1/Ti+s)/s__x',),
            params=('Kp', 'Ti'),
            unsupported_lines=(),
            module_name='typ_441__kp_1_ti_s_s',
            module_filename='typ_441__kp_1_ti_s_s.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='kp_1_sti_p_form_a',
            typ_id='442',
            blkdef_name='Kp+1/sTi [(p',
            sample_display_name='Kp+1/sTi [(p',
            display_label='Kp+1/sTi (parameter input) [1 input; param: Kp/Ti/y_max+1; 1 state]',
            category_path=('Native', 'Control and Measurement', 'Controllers'),
            inputs=('yi',),
            outputs=('yo',),
            states=('Kp+1/sTi [(p__x',),
            params=('Kp', 'Ti', 'y_max', 'y_min'),
            unsupported_lines=(),
            module_name='typ_442__kp_1_sti_p',
            module_filename='typ_442__kp_1_sti_p.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='kp_1_sti',
            typ_id='443',
            blkdef_name='Kp+1/sTi',
            sample_display_name='Kp+1/sTi',
            display_label='Kp+1/sTi',
            category_path=('Native', 'Control and Measurement', 'Controllers'),
            inputs=('yi',),
            outputs=('yo',),
            states=('Kp+1/sTi__x',),
            params=('Kp', 'Ti'),
            unsupported_lines=(),
            module_name='typ_443__kp_1_sti',
            module_filename='typ_443__kp_1_sti.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='kp_ki_s_s_form_a',
            typ_id='444',
            blkdef_name='Kp+Ki/s (s)',
            sample_display_name='Kp+Ki/s (s)',
            display_label='Kp+Ki/s (signal) [signal: yo_lim; param: Kp/Ki/Tt; 1 state]',
            category_path=('Native', 'Control and Measurement', 'Controllers'),
            inputs=('yi', 'yo_lim'),
            outputs=('yo',),
            states=('Kp+Ki/s (s)__x',),
            params=('Kp', 'Ki', 'Tt'),
            unsupported_lines=(),
            module_name='typ_444__kp_ki_s_s',
            module_filename='typ_444__kp_ki_s_s.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='kp_ki_s_p_form_a',
            typ_id='445',
            blkdef_name='Kp+Ki/s [(p',
            sample_display_name='Kp+Ki/s [(p',
            display_label='Kp+Ki/s (parameter input) [1 input; param: Kp/Ki/y_max+1; 1 state]',
            category_path=('Native', 'Control and Measurement', 'Controllers'),
            inputs=('yi',),
            outputs=('yo',),
            states=('Kp+Ki/s [(p__x',),
            params=('Kp', 'Ki', 'y_max', 'y_min'),
            unsupported_lines=(),
            module_name='typ_445__kp_ki_s_p',
            module_filename='typ_445__kp_ki_s_p.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='kp_ki_s_p_form_b',
            typ_id='446',
            blkdef_name='Kp+Ki/s [p',
            sample_display_name='Kp+Ki/s [p',
            display_label='Kp+Ki/s (parameter) [1 input; param: Kp/Ki/ymax+1; 1 state]',
            category_path=('Native', 'Control and Measurement', 'Controllers'),
            inputs=('yi',),
            outputs=('yo',),
            states=('Kp+Ki/s [p__x',),
            params=('Kp', 'Ki', 'ymax', 'ymin'),
            unsupported_lines=(),
            module_name='typ_446__kp_ki_s_p',
            module_filename='typ_446__kp_ki_s_p.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='kp_ki_s_s_form_b',
            typ_id='447',
            blkdef_name='Kp+Ki/s [s',
            sample_display_name='Kp+Ki/s [s',
            display_label='Kp+Ki/s (signal) [signal: ymax/ymin; param: Kp/Ki; 1 state]',
            category_path=('Native', 'Control and Measurement', 'Controllers'),
            inputs=('yi', 'ymax', 'ymin'),
            outputs=('yo',),
            states=('Kp+Ki/s [s__x',),
            params=('Kp', 'Ki'),
            unsupported_lines=(),
            module_name='typ_447__kp_ki_s_s',
            module_filename='typ_447__kp_ki_s_s.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='kp_ki_s_skd_1_std_p_form_a',
            typ_id='448',
            blkdef_name='Kp+Ki/s+sKd/(1+sTd) [(p',
            sample_display_name='Kp+Ki/s+sKd/(1+sTd) [(p',
            display_label='Kp+Ki/s+sKd/(1+sTd) (parameter input) [1 input; param: Kp/Ki/Kd+3; 2 states]',
            category_path=('Native', 'Control and Measurement', 'Controllers'),
            inputs=('yi',),
            outputs=('yo',),
            states=('Kp+Ki/s+sKd/(1+sTd) [(p__x1', 'Kp+Ki/s+sKd/(1+sTd) [(p__x2'),
            params=('Kp', 'Ki', 'Kd', 'Td', 'y_max', 'y_min'),
            unsupported_lines=(),
            module_name='typ_448__kp_ki_s_skd_1_std_p',
            module_filename='typ_448__kp_ki_s_skd_1_std_p.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='kp_ki_s',
            typ_id='449',
            blkdef_name='Kp+Ki/s',
            sample_display_name='Kp+Ki/s',
            display_label='Kp+Ki/s',
            category_path=('Native', 'Control and Measurement', 'Controllers'),
            inputs=('yi',),
            outputs=('yo',),
            states=('Kp+Ki/s__x',),
            params=('Kp', 'Ki'),
            unsupported_lines=(),
            module_name='typ_449__kp_ki_s',
            module_filename='typ_449__kp_ki_s.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='kc_1_sti_p_form_c',
            typ_id='450',
            blkdef_name='Kc+1/sTi [(p',
            sample_display_name='Kc+1/sTi [(p',
            display_label='Kc+1/sTi (parameter input) [signal: hold/rst; param: K_p/T_p/theta_p+3; 1 state]',
            category_path=('Native', 'Control and Measurement', 'Controllers'),
            inputs=('yi', 'hold', 'rst'),
            outputs=('yo',),
            states=('Kc+1/sTi [(p__x',),
            params=('K_p', 'T_p', 'theta_p', 'ControlTuning', 'y_max', 'y_min'),
            unsupported_lines=(),
            module_name='typ_450__kc_1_sti_p',
            module_filename='typ_450__kc_1_sti_p.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='kc_1_sti_p_form_d',
            typ_id='451',
            blkdef_name='Kc+1/sTi [(p',
            sample_display_name='Kc+1/sTi [(p',
            display_label='Kc+1/sTi (parameter input) [signal: hold/rst; param: K_p/T_rise/theta_p+3; 1 state]',
            category_path=('Native', 'Control and Measurement', 'Controllers'),
            inputs=('yi', 'hold', 'rst'),
            outputs=('yo',),
            states=('Kc+1/sTi [(p__x',),
            params=('K_p', 'T_rise', 'theta_p', 'ControlTuning', 'y_max', 'y_min'),
            unsupported_lines=(),
            module_name='typ_451__kc_1_sti_p',
            module_filename='typ_451__kc_1_sti_p.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='kp_1_ti_s_s_s_rst_variant',
            typ_id='452',
            blkdef_name='Kp(1/Ti+s)/s (s) _rst (variant)',
            sample_display_name='Kp(1/Ti+s)/s (s) _rst (variant)',
            display_label='Kp(1/Ti+s)/s (signal) rst (variant)',
            category_path=('Native', 'Control and Measurement', 'Controllers'),
            inputs=('yi', 'rst'),
            outputs=('yo',),
            states=('Kp(1/Ti+s)/s (s) _rst (variant)__x',),
            params=('Kp', 'Ti', 'Kaw', 'y_max', 'y_min'),
            unsupported_lines=(),
            module_name='typ_452__kp_1_ti_s_s_s_rst_variant',
            module_filename='typ_452__kp_1_ti_s_s_s_rst_variant.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='kp_1_ti_s_s_s_rst_hold',
            typ_id='453',
            blkdef_name='Kp(1/Ti+s)/s (s) _rst_hold',
            sample_display_name='Kp(1/Ti+s)/s (s) _rst_hold',
            display_label='Kp(1/Ti+s)/s (signal) (reset hold)',
            category_path=('Native', 'Control and Measurement', 'Controllers'),
            inputs=('yi', 'hold', 'yo_lim', 'rst'),
            outputs=('yo',),
            states=('Kp(1/Ti+s)/s (s) _rst_hold__x',),
            params=('Kp', 'Ti', 'Tt'),
            unsupported_lines=(),
            module_name='typ_453__kp_1_ti_s_s_s_rst_hold',
            module_filename='typ_453__kp_1_ti_s_s_s_rst_hold.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='kp_1_ti_s_s_rst_hold',
            typ_id='454',
            blkdef_name='Kp(1/Ti+s)/s _rst_hold',
            sample_display_name='Kp(1/Ti+s)/s _rst_hold',
            display_label='Kp(1/Ti+s)/s (reset hold)',
            category_path=('Native', 'Control and Measurement', 'Controllers'),
            inputs=('yi', 'hold', 'rst'),
            outputs=('yo',),
            states=('Kp(1/Ti+s)/s _rst_hold__x',),
            params=('Kp', 'Ti'),
            unsupported_lines=(),
            module_name='typ_454__kp_1_ti_s_s_rst_hold',
            module_filename='typ_454__kp_1_ti_s_s_rst_hold.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='kp_1_sti_p_form_b',
            typ_id='455',
            blkdef_name='Kp+1/sTi [(p',
            sample_display_name='Kp+1/sTi [(p',
            display_label='Kp+1/sTi (parameter input) [signal: hold/rst; param: Kp/Ti/y_max+1; 1 state]',
            category_path=('Native', 'Control and Measurement', 'Controllers'),
            inputs=('yi', 'hold', 'rst'),
            outputs=('yo',),
            states=('Kp+1/sTi [(p__x',),
            params=('Kp', 'Ti', 'y_max', 'y_min'),
            unsupported_lines=(),
            module_name='typ_455__kp_1_sti_p',
            module_filename='typ_455__kp_1_sti_p.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='kp_1_sti_rst_hold',
            typ_id='456',
            blkdef_name='Kp+1/sTi _rst_hold',
            sample_display_name='Kp+1/sTi _rst_hold',
            display_label='Kp+1/sTi (reset hold)',
            category_path=('Native', 'Control and Measurement', 'Controllers'),
            inputs=('yi', 'hold', 'rst'),
            outputs=('yo',),
            states=('Kp+1/sTi _rst_hold__x',),
            params=('Kp', 'Ti'),
            unsupported_lines=(),
            module_name='typ_456__kp_1_sti_rst_hold',
            module_filename='typ_456__kp_1_sti_rst_hold.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='kp_ki_s_s_rst_hold',
            typ_id='457',
            blkdef_name='Kp+Ki/s (s) _rst_hold',
            sample_display_name='Kp+Ki/s (s) _rst_hold',
            display_label='Kp+Ki/s (signal) (reset hold)',
            category_path=('Native', 'Control and Measurement', 'Controllers'),
            inputs=('yi', 'hold', 'yo_lim', 'rst'),
            outputs=('yo',),
            states=('Kp+Ki/s (s) _rst_hold__x',),
            params=('Kp', 'Ki', 'Tt'),
            unsupported_lines=(),
            module_name='typ_457__kp_ki_s_s_rst_hold',
            module_filename='typ_457__kp_ki_s_s_rst_hold.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='kp_ki_s_p_form_c',
            typ_id='458',
            blkdef_name='Kp+Ki/s [(p',
            sample_display_name='Kp+Ki/s [(p',
            display_label='Kp+Ki/s (parameter input) [signal: hold/rst; param: Kp/Ki/y_max+1; 1 state]',
            category_path=('Native', 'Control and Measurement', 'Controllers'),
            inputs=('yi', 'hold', 'rst'),
            outputs=('yo',),
            states=('Kp+Ki/s [(p__x',),
            params=('Kp', 'Ki', 'y_max', 'y_min'),
            unsupported_lines=(),
            module_name='typ_458__kp_ki_s_p',
            module_filename='typ_458__kp_ki_s_p.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='kp_ki_s_p_form_d',
            typ_id='459',
            blkdef_name='Kp+Ki/s [p',
            sample_display_name='Kp+Ki/s [p',
            display_label='Kp+Ki/s (parameter) [signal: hold/rst; param: Kp/Ki/y_max+1; 1 state]',
            category_path=('Native', 'Control and Measurement', 'Controllers'),
            inputs=('yi', 'hold', 'rst'),
            outputs=('yo',),
            states=('Kp+Ki/s [p__x',),
            params=('Kp', 'Ki', 'y_max', 'y_min'),
            unsupported_lines=(),
            module_name='typ_459__kp_ki_s_p',
            module_filename='typ_459__kp_ki_s_p.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='kp_ki_s_s_form_c',
            typ_id='460',
            blkdef_name='Kp+Ki/s [s',
            sample_display_name='Kp+Ki/s [s',
            display_label='Kp+Ki/s (signal) [signal: hold/ymax/rst+1; param: Kp/Ki; 1 state]',
            category_path=('Native', 'Control and Measurement', 'Controllers'),
            inputs=('yi', 'hold', 'ymax', 'rst', 'ymin'),
            outputs=('yo',),
            states=('Kp+Ki/s [s__x',),
            params=('Kp', 'Ki'),
            unsupported_lines=(),
            module_name='typ_460__kp_ki_s_s',
            module_filename='typ_460__kp_ki_s_s.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='kp_ki_s_rst_hold',
            typ_id='461',
            blkdef_name='Kp+Ki/s _rst_hold',
            sample_display_name='Kp+Ki/s _rst_hold',
            display_label='Kp+Ki/s (reset hold)',
            category_path=('Native', 'Control and Measurement', 'Controllers'),
            inputs=('yi', 'hold', 'rst'),
            outputs=('yo',),
            states=('Kp+Ki/s _rst_hold__x',),
            params=('Kp', 'Ki'),
            unsupported_lines=(),
            module_name='typ_461__kp_ki_s_rst_hold',
            module_filename='typ_461__kp_ki_s_rst_hold.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='kp_ki_s_skd_1_std_p_form_b',
            typ_id='462',
            blkdef_name='Kp+Ki/s+sKd/(1+sTd) [(p',
            sample_display_name='Kp+Ki/s+sKd/(1+sTd) [(p',
            display_label='Kp+Ki/s+sKd/(1+sTd) (parameter input) [signal: hold/rst; param: Kp/Ki/Kd+3; 2 states]',
            category_path=('Native', 'Control and Measurement', 'Controllers'),
            inputs=('yi', 'hold', 'rst'),
            outputs=('yo',),
            states=('Kp+Ki/s+sKd/(1+sTd) [(p__x1', 'Kp+Ki/s+sKd/(1+sTd) [(p__x2'),
            params=('Kp', 'Ki', 'Kd', 'Td', 'y_max', 'y_min'),
            unsupported_lines=(),
            module_name='typ_462__kp_ki_s_skd_1_std_p',
            module_filename='typ_462__kp_ki_s_skd_1_std_p.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='kc_1_sti_p_form_e',
            typ_id='463',
            blkdef_name='Kc+1/sTi [(p',
            sample_display_name='Kc+1/sTi [(p',
            display_label='Kc+1/sTi (parameter input) [signal: hold/x_rst/rst; param: K_p/T_p/theta_p+3; 1 state]',
            category_path=('Native', 'Control and Measurement', 'Controllers'),
            inputs=('yi', 'hold', 'x_rst', 'rst'),
            outputs=('yo',),
            states=('Kc+1/sTi [(p__x',),
            params=('K_p', 'T_p', 'theta_p', 'ControlTuning', 'y_max', 'y_min'),
            unsupported_lines=(),
            module_name='typ_463__kc_1_sti_p',
            module_filename='typ_463__kc_1_sti_p.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='kc_1_sti_p_form_f',
            typ_id='464',
            blkdef_name='Kc+1/sTi [(p',
            sample_display_name='Kc+1/sTi [(p',
            display_label='Kc+1/sTi (parameter input) [signal: hold/x_rst/rst; param: K_p/T_rise/theta_p+3; 1 state]',
            category_path=('Native', 'Control and Measurement', 'Controllers'),
            inputs=('yi', 'hold', 'x_rst', 'rst'),
            outputs=('yo',),
            states=('Kc+1/sTi [(p__x',),
            params=('K_p', 'T_rise', 'theta_p', 'ControlTuning', 'y_max', 'y_min'),
            unsupported_lines=(),
            module_name='typ_464__kc_1_sti_p',
            module_filename='typ_464__kc_1_sti_p.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='kp_1_ti_s_s_s_rst_sig_hold',
            typ_id='465',
            blkdef_name='Kp(1/Ti+s)/s (s) _rst_sig_hold',
            sample_display_name='Kp(1/Ti+s)/s (s) _rst_sig_hold',
            display_label='Kp(1/Ti+s)/s (signal) (reset signal hold)',
            category_path=('Native', 'Control and Measurement', 'Controllers'),
            inputs=('yi', 'hold', 'x_rst', 'yo_lim', 'rst'),
            outputs=('yo',),
            states=('Kp(1/Ti+s)/s (s) _rst_sig_hold__x',),
            params=('Kp', 'Ti', 'Tt'),
            unsupported_lines=(),
            module_name='typ_465__kp_1_ti_s_s_s_rst_sig_hold',
            module_filename='typ_465__kp_1_ti_s_s_s_rst_sig_hold.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='kp_1_ti_s_s_rst_sig_hold',
            typ_id='466',
            blkdef_name='Kp(1/Ti+s)/s _rst_sig_hold',
            sample_display_name='Kp(1/Ti+s)/s _rst_sig_hold',
            display_label='Kp(1/Ti+s)/s (reset signal hold)',
            category_path=('Native', 'Control and Measurement', 'Controllers'),
            inputs=('yi', 'hold', 'x_rst', 'rst'),
            outputs=('yo',),
            states=('Kp(1/Ti+s)/s _rst_sig_hold__x',),
            params=('Kp', 'Ti'),
            unsupported_lines=(),
            module_name='typ_466__kp_1_ti_s_s_rst_sig_hold',
            module_filename='typ_466__kp_1_ti_s_s_rst_sig_hold.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='kp_1_sti_p_form_c',
            typ_id='467',
            blkdef_name='Kp+1/sTi [(p',
            sample_display_name='Kp+1/sTi [(p',
            display_label='Kp+1/sTi (parameter input) [signal: hold/x_rst/rst; param: Kp/Ti/y_max+1; 1 state]',
            category_path=('Native', 'Control and Measurement', 'Controllers'),
            inputs=('yi', 'hold', 'x_rst', 'rst'),
            outputs=('yo',),
            states=('Kp+1/sTi [(p__x',),
            params=('Kp', 'Ti', 'y_max', 'y_min'),
            unsupported_lines=(),
            module_name='typ_467__kp_1_sti_p',
            module_filename='typ_467__kp_1_sti_p.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='kp_1_sti_rst_sig_hold',
            typ_id='468',
            blkdef_name='Kp+1/sTi _rst_sig_hold',
            sample_display_name='Kp+1/sTi _rst_sig_hold',
            display_label='Kp+1/sTi (reset signal hold)',
            category_path=('Native', 'Control and Measurement', 'Controllers'),
            inputs=('yi', 'hold', 'x_rst', 'rst'),
            outputs=('yo',),
            states=('Kp+1/sTi _rst_sig_hold__x',),
            params=('Kp', 'Ti'),
            unsupported_lines=(),
            module_name='typ_468__kp_1_sti_rst_sig_hold',
            module_filename='typ_468__kp_1_sti_rst_sig_hold.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='kp_ki_s_s_rst_sig_hold',
            typ_id='469',
            blkdef_name='Kp+Ki/s (s) _rst_sig_hold',
            sample_display_name='Kp+Ki/s (s) _rst_sig_hold',
            display_label='Kp+Ki/s (signal) (reset signal hold)',
            category_path=('Native', 'Control and Measurement', 'Controllers'),
            inputs=('yi', 'hold', 'x_rst', 'yo_lim', 'rst'),
            outputs=('yo',),
            states=('Kp+Ki/s (s) _rst_sig_hold__x',),
            params=('Kp', 'Ki', 'Tt'),
            unsupported_lines=(),
            module_name='typ_469__kp_ki_s_s_rst_sig_hold',
            module_filename='typ_469__kp_ki_s_s_rst_sig_hold.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='kp_ki_s_p_form_e',
            typ_id='470',
            blkdef_name='Kp+Ki/s [(p',
            sample_display_name='Kp+Ki/s [(p',
            display_label='Kp+Ki/s (parameter input) [signal: hold/x_rst/rst; param: Kp/Ki/y_max+1; 1 state]',
            category_path=('Native', 'Control and Measurement', 'Controllers'),
            inputs=('yi', 'hold', 'x_rst', 'rst'),
            outputs=('yo',),
            states=('Kp+Ki/s [(p__x',),
            params=('Kp', 'Ki', 'y_max', 'y_min'),
            unsupported_lines=(),
            module_name='typ_470__kp_ki_s_p',
            module_filename='typ_470__kp_ki_s_p.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='kp_ki_s_p_form_f',
            typ_id='471',
            blkdef_name='Kp+Ki/s [p',
            sample_display_name='Kp+Ki/s [p',
            display_label='Kp+Ki/s (parameter) [signal: hold/x_rst/rst; param: Kp/Ki/y_max+1; 1 state]',
            category_path=('Native', 'Control and Measurement', 'Controllers'),
            inputs=('yi', 'hold', 'x_rst', 'rst'),
            outputs=('yo',),
            states=('Kp+Ki/s [p__x',),
            params=('Kp', 'Ki', 'y_max', 'y_min'),
            unsupported_lines=(),
            module_name='typ_471__kp_ki_s_p',
            module_filename='typ_471__kp_ki_s_p.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='kp_ki_s_s_form_d',
            typ_id='472',
            blkdef_name='Kp+Ki/s [s',
            sample_display_name='Kp+Ki/s [s',
            display_label='Kp+Ki/s (signal) [signal: hold/x_rst/ymax+2; param: Kp/Ki; 1 state]',
            category_path=('Native', 'Control and Measurement', 'Controllers'),
            inputs=('yi', 'hold', 'x_rst', 'ymax', 'rst', 'ymin'),
            outputs=('yo',),
            states=('Kp+Ki/s [s__x',),
            params=('Kp', 'Ki'),
            unsupported_lines=(),
            module_name='typ_472__kp_ki_s_s',
            module_filename='typ_472__kp_ki_s_s.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='kp_ki_s_rst_sig_hold',
            typ_id='473',
            blkdef_name='Kp+Ki/s _rst_sig_hold',
            sample_display_name='Kp+Ki/s _rst_sig_hold',
            display_label='Kp+Ki/s (reset signal hold)',
            category_path=('Native', 'Control and Measurement', 'Controllers'),
            inputs=('yi', 'hold', 'x_rst', 'rst'),
            outputs=('yo',),
            states=('Kp+Ki/s _rst_sig_hold__x',),
            params=('Kp', 'Ki'),
            unsupported_lines=(),
            module_name='typ_473__kp_ki_s_rst_sig_hold',
            module_filename='typ_473__kp_ki_s_rst_sig_hold.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='kp_ki_s_skd_1_std_p_form_c',
            typ_id='474',
            blkdef_name='Kp+Ki/s+sKd/(1+sTd) [(p',
            sample_display_name='Kp+Ki/s+sKd/(1+sTd) [(p',
            display_label='Kp+Ki/s+sKd/(1+sTd) (parameter input) [signal: hold/x1_rst/rst; param: Kp/Ki/Kd+3; 2 states]',
            category_path=('Native', 'Control and Measurement', 'Controllers'),
            inputs=('yi', 'hold', 'x1_rst', 'rst'),
            outputs=('yo',),
            states=('Kp+Ki/s+sKd/(1+sTd) [(p__x1', 'Kp+Ki/s+sKd/(1+sTd) [(p__x2'),
            params=('Kp', 'Ki', 'Kd', 'Td', 'y_max', 'y_min'),
            unsupported_lines=(),
            module_name='typ_474__kp_ki_s_skd_1_std_p',
            module_filename='typ_474__kp_ki_s_skd_1_std_p.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='clock_t_0_par',
            typ_id='475',
            blkdef_name='Clock (t>0) _par',
            sample_display_name='Clock (t>0) _par',
            display_label='Clock (t>0) (parameter)',
            category_path=('Native', 'Waveforms and Time', 'Time Sources and Timers'),
            inputs=(),
            outputs=('output',),
            states=('Clock (t>0) _par__x',),
            params=('cFreq',),
            unsupported_lines=(),
            module_name='typ_475__clock_t_0_par',
            module_filename='typ_475__clock_t_0_par.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='clock_t_0_sig',
            typ_id='476',
            blkdef_name='Clock (t>0) _sig',
            sample_display_name='Clock (t>0) _sig',
            display_label='Clock (t>0) (signal)',
            category_path=('Native', 'Waveforms and Time', 'Time Sources and Timers'),
            inputs=('extfrq',),
            outputs=('output',),
            states=('Clock (t>0) _sig__x',),
            params=(),
            unsupported_lines=(),
            module_name='typ_476__clock_t_0_sig',
            module_filename='typ_476__clock_t_0_sig.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='clock_t_t0_par',
            typ_id='477',
            blkdef_name='Clock (t>t0) _par',
            sample_display_name='Clock (t>t0) _par',
            display_label='Clock (t>t0) (parameter)',
            category_path=('Native', 'Waveforms and Time', 'Time Sources and Timers'),
            inputs=(),
            outputs=('output',),
            states=('Clock (t>t0) _par__x',),
            params=('cFreq',),
            unsupported_lines=(),
            module_name='typ_477__clock_t_t0_par',
            module_filename='typ_477__clock_t_t0_par.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='clock_t_t0_sig',
            typ_id='478',
            blkdef_name='Clock (t>t0) _sig',
            sample_display_name='Clock (t>t0) _sig',
            display_label='Clock (t>t0) (signal)',
            category_path=('Native', 'Waveforms and Time', 'Time Sources and Timers'),
            inputs=('extfrq',),
            outputs=('output',),
            states=('Clock (t>t0) _sig__x',),
            params=(),
            unsupported_lines=(),
            module_name='typ_478__clock_t_t0_sig',
            module_filename='typ_478__clock_t_t0_sig.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='clock_par',
            typ_id='479',
            blkdef_name='Clock _par',
            sample_display_name='Clock _par',
            display_label='Clock (parameter)',
            category_path=('Native', 'Waveforms and Time', 'Time Sources and Timers'),
            inputs=(),
            outputs=('output',),
            states=('Clock _par__x',),
            params=('cFreq',),
            unsupported_lines=(),
            module_name='typ_479__clock_par',
            module_filename='typ_479__clock_par.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='clock_sig',
            typ_id='480',
            blkdef_name='Clock _sig',
            sample_display_name='Clock _sig',
            display_label='Clock (signal)',
            category_path=('Native', 'Waveforms and Time', 'Time Sources and Timers'),
            inputs=('extfrq',),
            outputs=('output',),
            states=('Clock _sig__x',),
            params=(),
            unsupported_lines=(),
            module_name='typ_480__clock_sig',
            module_filename='typ_480__clock_sig.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='pulse',
            typ_id='481',
            blkdef_name='Pulse',
            sample_display_name='Pulse',
            display_label='Pulse',
            category_path=('Native', 'Waveforms and Time', 'Signal Generators'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=('K', 'T1'),
            unsupported_lines=(),
            module_name='typ_481__pulse',
            module_filename='typ_481__pulse.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='sawtooth_wave_generator_ip',
            typ_id='482',
            blkdef_name='Sawtooth Wave Generator _ip',
            sample_display_name='Sawtooth Wave Generator _ip',
            display_label='Sawtooth Wave Generator (pulse)',
            category_path=('Native', 'Waveforms and Time', 'Signal Generators'),
            inputs=(),
            outputs=('yo',),
            states=(),
            params=('f',),
            unsupported_lines=(),
            module_name='typ_482__sawtooth_wave_generator_ip',
            module_filename='typ_482__sawtooth_wave_generator_ip.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='sawtooth_wave_generator',
            typ_id='483',
            blkdef_name='Sawtooth Wave Generator',
            sample_display_name='Sawtooth Wave Generator',
            display_label='Sawtooth Wave Generator',
            category_path=('Native', 'Waveforms and Time', 'Signal Generators'),
            inputs=(),
            outputs=('yo',),
            states=(),
            params=('f',),
            unsupported_lines=(),
            module_name='typ_483__sawtooth_wave_generator',
            module_filename='typ_483__sawtooth_wave_generator.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='sine_wave_generator_t_t0',
            typ_id='484',
            blkdef_name='Sine Wave Generator (t>t0)',
            sample_display_name='Sine Wave Generator (t>t0)',
            display_label='Sine Wave Generator (t>t0)',
            category_path=('Native', 'Waveforms and Time', 'Signal Generators'),
            inputs=(),
            outputs=('yo',),
            states=(),
            params=('a', 'f', 'phi', 't0'),
            unsupported_lines=(),
            module_name='typ_484__sine_wave_generator_t_t0',
            module_filename='typ_484__sine_wave_generator_t_t0.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='sine_wave_generator',
            typ_id='485',
            blkdef_name='Sine Wave Generator',
            sample_display_name='Sine Wave Generator',
            display_label='Sine Wave Generator',
            category_path=('Native', 'Waveforms and Time', 'Signal Generators'),
            inputs=(),
            outputs=('yo',),
            states=(),
            params=('a', 'f', 'phi'),
            unsupported_lines=(),
            module_name='typ_485__sine_wave_generator',
            module_filename='typ_485__sine_wave_generator.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='square_wave_generator',
            typ_id='486',
            blkdef_name='Square Wave Generator',
            sample_display_name='Square Wave Generator',
            display_label='Square Wave Generator',
            category_path=('Native', 'Waveforms and Time', 'Signal Generators'),
            inputs=(),
            outputs=('yo',),
            states=(),
            params=('f',),
            unsupported_lines=(),
            module_name='typ_486__square_wave_generator',
            module_filename='typ_486__square_wave_generator.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='square_wave_generator_ip',
            typ_id='487',
            blkdef_name='Square Wave Generator_ip',
            sample_display_name='Square Wave Generator_ip',
            display_label='Square Wave Generator ip',
            category_path=('Native', 'Waveforms and Time', 'Signal Generators'),
            inputs=(),
            outputs=('yo',),
            states=(),
            params=('f',),
            unsupported_lines=(),
            module_name='typ_487__square_wave_generator_ip',
            module_filename='typ_487__square_wave_generator_ip.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='time_form_b',
            typ_id='488',
            blkdef_name='Time',
            sample_display_name='Time',
            display_label='Time',
            category_path=('Native', 'Waveforms and Time', 'Time Sources and Timers'),
            inputs=(),
            outputs=('t',),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_488__time',
            module_filename='typ_488__time.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='triangle_wave_generator',
            typ_id='489',
            blkdef_name='Triangle Wave Generator',
            sample_display_name='Triangle Wave Generator',
            display_label='Triangle Wave Generator',
            category_path=('Native', 'Waveforms and Time', 'Signal Generators'),
            inputs=(),
            outputs=('yo',),
            states=(),
            params=('f',),
            unsupported_lines=(),
            module_name='typ_489__triangle_wave_generator',
            module_filename='typ_489__triangle_wave_generator.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='triangle_wave_generator_ip',
            typ_id='490',
            blkdef_name='Triangle Wave Generator_ip',
            sample_display_name='Triangle Wave Generator_ip',
            display_label='Triangle Wave Generator ip',
            category_path=('Native', 'Waveforms and Time', 'Signal Generators'),
            inputs=(),
            outputs=('yo',),
            states=(),
            params=('f',),
            unsupported_lines=(),
            module_name='typ_490__triangle_wave_generator_ip',
            module_filename='typ_490__triangle_wave_generator_ip.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='enable_1_sig_hold',
            typ_id='491',
            blkdef_name='Enable 1 sig _hold',
            sample_display_name='Enable 1 sig _hold',
            display_label='Enable 1 sig (hold)',
            category_path=('Native', 'Logic and Events', 'Timers and Enables'),
            inputs=('yi', 'Enable'),
            outputs=('yo',),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_491__enable_1_sig_hold',
            module_filename='typ_491__enable_1_sig_hold.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='enable_1_sig',
            typ_id='492',
            blkdef_name='Enable 1 sig',
            sample_display_name='Enable 1 sig',
            display_label='Enable 1 sig',
            category_path=('Native', 'Logic and Events', 'Timers and Enables'),
            inputs=('yi', 'Enable'),
            outputs=('yo',),
            states=(),
            params=('yi_default',),
            unsupported_lines=(),
            module_name='typ_492__enable_1_sig',
            module_filename='typ_492__enable_1_sig.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='enable_2_sig_hold',
            typ_id='493',
            blkdef_name='Enable 2 sig _hold',
            sample_display_name='Enable 2 sig _hold',
            display_label='Enable 2 sig (hold)',
            category_path=('Native', 'Logic and Events', 'Timers and Enables'),
            inputs=('yi1', 'yi2', 'Enable'),
            outputs=('yo1', 'yo2'),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_493__enable_2_sig_hold',
            module_filename='typ_493__enable_2_sig_hold.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='enable_2_sig',
            typ_id='494',
            blkdef_name='Enable 2 sig',
            sample_display_name='Enable 2 sig',
            display_label='Enable 2 sig',
            category_path=('Native', 'Logic and Events', 'Timers and Enables'),
            inputs=('yi1', 'yi2', 'Enable'),
            outputs=('yo1', 'yo2'),
            states=(),
            params=('yi1_default', 'yi2_default'),
            unsupported_lines=(),
            module_name='typ_494__enable_2_sig',
            module_filename='typ_494__enable_2_sig.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='enable_3_sig_hold',
            typ_id='495',
            blkdef_name='Enable 3 sig _hold',
            sample_display_name='Enable 3 sig _hold',
            display_label='Enable 3 sig (hold)',
            category_path=('Native', 'Logic and Events', 'Timers and Enables'),
            inputs=('yi1', 'yi2', 'yi3', 'Enable'),
            outputs=('yo1', 'yo2', 'yo3'),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_495__enable_3_sig_hold',
            module_filename='typ_495__enable_3_sig_hold.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='enable_3_sig',
            typ_id='496',
            blkdef_name='Enable 3 sig',
            sample_display_name='Enable 3 sig',
            display_label='Enable 3 sig',
            category_path=('Native', 'Logic and Events', 'Timers and Enables'),
            inputs=('yi1', 'yi2', 'yi3', 'Enable'),
            outputs=('yo1', 'yo2', 'yo3'),
            states=(),
            params=('yi1_default', 'yi2_default', 'yi3_default'),
            unsupported_lines=(),
            module_name='typ_496__enable_3_sig',
            module_filename='typ_496__enable_3_sig.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='enable_4_sig_hold',
            typ_id='497',
            blkdef_name='Enable 4 sig _hold',
            sample_display_name='Enable 4 sig _hold',
            display_label='Enable 4 sig (hold)',
            category_path=('Native', 'Logic and Events', 'Timers and Enables'),
            inputs=('yi1', 'yi2', 'yi3', 'yi4', 'Enable'),
            outputs=('yo1', 'yo2', 'yo3', 'yo4'),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_497__enable_4_sig_hold',
            module_filename='typ_497__enable_4_sig_hold.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='enable_4_sig',
            typ_id='498',
            blkdef_name='Enable 4 sig',
            sample_display_name='Enable 4 sig',
            display_label='Enable 4 sig',
            category_path=('Native', 'Logic and Events', 'Timers and Enables'),
            inputs=('yi1', 'yi2', 'yi3', 'yi4', 'Enable'),
            outputs=('yo1', 'yo2', 'yo3', 'yo4'),
            states=(),
            params=('yi1_default', 'yi2_default', 'yi3_default', 'yi4_default'),
            unsupported_lines=(),
            module_name='typ_498__enable_4_sig',
            module_filename='typ_498__enable_4_sig.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='enable_5_sig_hold',
            typ_id='499',
            blkdef_name='Enable 5 sig _hold',
            sample_display_name='Enable 5 sig _hold',
            display_label='Enable 5 sig (hold)',
            category_path=('Native', 'Logic and Events', 'Timers and Enables'),
            inputs=('yi1', 'yi2', 'yi3', 'yi4', 'yi5', 'Enable'),
            outputs=('yo1', 'yo2', 'yo3', 'yo4', 'yo5'),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_499__enable_5_sig_hold',
            module_filename='typ_499__enable_5_sig_hold.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='enable_5_sig',
            typ_id='500',
            blkdef_name='Enable 5 sig',
            sample_display_name='Enable 5 sig',
            display_label='Enable 5 sig',
            category_path=('Native', 'Logic and Events', 'Timers and Enables'),
            inputs=('yi1', 'yi2', 'yi3', 'yi4', 'yi5', 'Enable'),
            outputs=('yo1', 'yo2', 'yo3', 'yo4', 'yo5'),
            states=(),
            params=('yi1_default', 'yi2_default', 'yi3_default', 'yi4_default', 'yi5_default'),
            unsupported_lines=(),
            module_name='typ_500__enable_5_sig',
            module_filename='typ_500__enable_5_sig.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='enable_6_sig_hold',
            typ_id='501',
            blkdef_name='Enable 6 sig _hold',
            sample_display_name='Enable 6 sig _hold',
            display_label='Enable 6 sig (hold)',
            category_path=('Native', 'Logic and Events', 'Timers and Enables'),
            inputs=('yi1', 'yi2', 'yi3', 'yi4', 'yi5', 'yi6', 'Enable'),
            outputs=('yo1', 'yo2', 'yo3', 'yo4', 'yo5', 'yo6'),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_501__enable_6_sig_hold',
            module_filename='typ_501__enable_6_sig_hold.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='enable_7_sig_hold',
            typ_id='502',
            blkdef_name='Enable 7 sig _hold',
            sample_display_name='Enable 7 sig _hold',
            display_label='Enable 7 sig (hold)',
            category_path=('Native', 'Logic and Events', 'Timers and Enables'),
            inputs=('yi1', 'yi2', 'yi3', 'yi4', 'yi5', 'yi6', 'yi7', 'Enable'),
            outputs=('yo1', 'yo2', 'yo3', 'yo4', 'yo5', 'yo6', 'yo7'),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_502__enable_7_sig_hold',
            module_filename='typ_502__enable_7_sig_hold.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='enable_8_sig_hold',
            typ_id='503',
            blkdef_name='Enable 8 sig _hold',
            sample_display_name='Enable 8 sig _hold',
            display_label='Enable 8 sig (hold)',
            category_path=('Native', 'Logic and Events', 'Timers and Enables'),
            inputs=('yi1', 'yi2', 'yi3', 'yi4', 'yi5', 'yi6', 'yi7', 'yi8', 'Enable'),
            outputs=('yo1', 'yo2', 'yo3', 'yo4', 'yo5', 'yo6', 'yo7', 'yo8'),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_503__enable_8_sig_hold',
            module_filename='typ_503__enable_8_sig_hold.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='enable_signal_fixed',
            typ_id='504',
            blkdef_name='Enable signal (fixed)',
            sample_display_name='Enable signal (fixed)',
            display_label='Enable signal (fixed)',
            category_path=('Native', 'Logic and Events', 'Timers and Enables'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=('Enable',),
            unsupported_lines=(),
            module_name='typ_504__enable_signal_fixed',
            module_filename='typ_504__enable_signal_fixed.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='enable_signal',
            typ_id='505',
            blkdef_name='Enable signal',
            sample_display_name='Enable signal',
            display_label='Enable signal',
            category_path=('Native', 'Logic and Events', 'Timers and Enables'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=('Enable',),
            unsupported_lines=(),
            module_name='typ_505__enable_signal',
            module_filename='typ_505__enable_signal.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='switch_par_1_1_by_par_fixed',
            typ_id='506',
            blkdef_name='Switch par 1->1 by par (fixed)',
            sample_display_name='Switch par 1->1 by par (fixed)',
            display_label='Switch par 1->1 by par (fixed)',
            category_path=('Native', 'Logic and Events', 'Switching and Selection'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=('Enable', 'p'),
            unsupported_lines=(),
            module_name='typ_506__switch_par_1_1_by_par_fixed',
            module_filename='typ_506__switch_par_1_1_by_par_fixed.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='switch_par_1_1_by_par',
            typ_id='507',
            blkdef_name='Switch par 1->1 by par',
            sample_display_name='Switch par 1->1 by par',
            display_label='Switch par 1->1 by par',
            category_path=('Native', 'Logic and Events', 'Switching and Selection'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=('Enable', 'p'),
            unsupported_lines=(),
            module_name='typ_507__switch_par_1_1_by_par',
            module_filename='typ_507__switch_par_1_1_by_par.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='switch_par_1_2_by_par',
            typ_id='508',
            blkdef_name='Switch par 1->2 by par',
            sample_display_name='Switch par 1->2 by par',
            display_label='Switch par 1->2 by par',
            category_path=('Native', 'Logic and Events', 'Switching and Selection'),
            inputs=(),
            outputs=('yo1', 'yo2'),
            states=(),
            params=('sw', 'K'),
            unsupported_lines=(),
            module_name='typ_508__switch_par_1_2_by_par',
            module_filename='typ_508__switch_par_1_2_by_par.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='switch_par_1_2_by_sig',
            typ_id='509',
            blkdef_name='Switch par 1->2 by sig',
            sample_display_name='Switch par 1->2 by sig',
            display_label='Switch par 1->2 by sig',
            category_path=('Native', 'Logic and Events', 'Switching and Selection'),
            inputs=('sw',),
            outputs=('yo1', 'yo2'),
            states=(),
            params=('K',),
            unsupported_lines=(),
            module_name='typ_509__switch_par_1_2_by_sig',
            module_filename='typ_509__switch_par_1_2_by_sig.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='switch_par_2_1_by_par',
            typ_id='510',
            blkdef_name='Switch par 2->1 by par',
            sample_display_name='Switch par 2->1 by par',
            display_label='Switch par 2->1 by par',
            category_path=('Native', 'Logic and Events', 'Switching and Selection'),
            inputs=(),
            outputs=('yo',),
            states=(),
            params=('sw', 'K1', 'K2'),
            unsupported_lines=(),
            module_name='typ_510__switch_par_2_1_by_par',
            module_filename='typ_510__switch_par_2_1_by_par.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='switch_par_2_1_by_sig',
            typ_id='511',
            blkdef_name='Switch par 2->1 by sig',
            sample_display_name='Switch par 2->1 by sig',
            display_label='Switch par 2->1 by sig',
            category_path=('Native', 'Logic and Events', 'Switching and Selection'),
            inputs=('sw',),
            outputs=('yo',),
            states=(),
            params=('K1', 'K2'),
            unsupported_lines=(),
            module_name='typ_511__switch_par_2_1_by_sig',
            module_filename='typ_511__switch_par_2_1_by_sig.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='switch_sig_1_1_by_sig_fixed',
            typ_id='512',
            blkdef_name='Switch sig 1->1 by sig (fixed)',
            sample_display_name='Switch sig 1->1 by sig (fixed)',
            display_label='Switch sig 1->1 by sig (fixed)',
            category_path=('Native', 'Logic and Events', 'Switching and Selection'),
            inputs=('yi', 'Enable'),
            outputs=('yo',),
            states=(),
            params=('p',),
            unsupported_lines=(),
            module_name='typ_512__switch_sig_1_1_by_sig_fixed',
            module_filename='typ_512__switch_sig_1_1_by_sig_fixed.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='switch_sig_1_1_by_sig',
            typ_id='513',
            blkdef_name='Switch sig 1->1 by sig',
            sample_display_name='Switch sig 1->1 by sig',
            display_label='Switch sig 1->1 by sig',
            category_path=('Native', 'Logic and Events', 'Switching and Selection'),
            inputs=('yi', 'Enable'),
            outputs=('yo',),
            states=(),
            params=('p',),
            unsupported_lines=(),
            module_name='typ_513__switch_sig_1_1_by_sig',
            module_filename='typ_513__switch_sig_1_1_by_sig.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='switch_sig_1_2_by_par_bool',
            typ_id='514',
            blkdef_name='Switch sig 1->2 by par (bool)',
            sample_display_name='Switch sig 1->2 by par (bool)',
            display_label='Switch sig 1->2 by par (bool)',
            category_path=('Native', 'Logic and Events', 'Switching and Selection'),
            inputs=('yi',),
            outputs=('yo1', 'yo2'),
            states=(),
            params=('sw',),
            unsupported_lines=(),
            module_name='typ_514__switch_sig_1_2_by_par_bool',
            module_filename='typ_514__switch_sig_1_2_by_par_bool.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='switch_sig_1_2_by_par',
            typ_id='515',
            blkdef_name='Switch sig 1->2 by par',
            sample_display_name='Switch sig 1->2 by par',
            display_label='Switch sig 1->2 by par',
            category_path=('Native', 'Logic and Events', 'Switching and Selection'),
            inputs=('yi',),
            outputs=('yo1', 'yo2'),
            states=(),
            params=('sw',),
            unsupported_lines=(),
            module_name='typ_515__switch_sig_1_2_by_par',
            module_filename='typ_515__switch_sig_1_2_by_par.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='switch_sig_1_2_by_sig',
            typ_id='516',
            blkdef_name='Switch sig 1->2 by sig',
            sample_display_name='Switch sig 1->2 by sig',
            display_label='Switch sig 1->2 by sig',
            category_path=('Native', 'Logic and Events', 'Switching and Selection'),
            inputs=('yi', 'sw'),
            outputs=('yo1', 'yo2'),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_516__switch_sig_1_2_by_sig',
            module_filename='typ_516__switch_sig_1_2_by_sig.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='switch_sig_2_1_not_eq_k_by_s_p',
            typ_id='517',
            blkdef_name='Switch sig 2->1 (NOT EQ K) by s/p',
            sample_display_name='Switch sig 2->1 (NOT EQ K) by s/p',
            display_label='Switch sig 2->1 (NOT EQ K) by s/p',
            category_path=('Native', 'Logic and Events', 'Gates and Memory'),
            inputs=('yi1', 'yi2', 'sw'),
            outputs=('yo',),
            states=(),
            params=('K',),
            unsupported_lines=(),
            module_name='typ_517__switch_sig_2_1_not_eq_k_by_s_p',
            module_filename='typ_517__switch_sig_2_1_not_eq_k_by_s_p.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='switch_sig_2_1_by_par_bool',
            typ_id='518',
            blkdef_name='Switch sig 2->1 by par (bool)',
            sample_display_name='Switch sig 2->1 by par (bool)',
            display_label='Switch sig 2->1 by par (bool)',
            category_path=('Native', 'Logic and Events', 'Switching and Selection'),
            inputs=('yi1', 'yi2'),
            outputs=('yo',),
            states=(),
            params=('sw',),
            unsupported_lines=(),
            module_name='typ_518__switch_sig_2_1_by_par_bool',
            module_filename='typ_518__switch_sig_2_1_by_par_bool.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='switch_sig_2_1_by_par',
            typ_id='519',
            blkdef_name='Switch sig 2->1 by par',
            sample_display_name='Switch sig 2->1 by par',
            display_label='Switch sig 2->1 by par',
            category_path=('Native', 'Logic and Events', 'Switching and Selection'),
            inputs=('yi1', 'yi2'),
            outputs=('yo',),
            states=(),
            params=('sw',),
            unsupported_lines=(),
            module_name='typ_519__switch_sig_2_1_by_par',
            module_filename='typ_519__switch_sig_2_1_by_par.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='switch_sig_2_1_by_sig_bool',
            typ_id='520',
            blkdef_name='Switch sig 2->1 by sig (bool)',
            sample_display_name='Switch sig 2->1 by sig (bool)',
            display_label='Switch sig 2->1 by sig (bool)',
            category_path=('Native', 'Logic and Events', 'Switching and Selection'),
            inputs=('yi1', 'yi2', 'sw'),
            outputs=('yo',),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_520__switch_sig_2_1_by_sig_bool',
            module_filename='typ_520__switch_sig_2_1_by_sig_bool.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='switch_sig_2_1_by_sig_fixed',
            typ_id='521',
            blkdef_name='Switch sig 2->1 by sig (fixed)',
            sample_display_name='Switch sig 2->1 by sig (fixed)',
            display_label='Switch sig 2->1 by sig (fixed)',
            category_path=('Native', 'Logic and Events', 'Switching and Selection'),
            inputs=('yi1', 'yi2', 'sw'),
            outputs=('yo',),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_521__switch_sig_2_1_by_sig_fixed',
            module_filename='typ_521__switch_sig_2_1_by_sig_fixed.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='switch_sig_2_1_by_sig',
            typ_id='522',
            blkdef_name='Switch sig 2->1 by sig',
            sample_display_name='Switch sig 2->1 by sig',
            display_label='Switch sig 2->1 by sig',
            category_path=('Native', 'Logic and Events', 'Switching and Selection'),
            inputs=('yi1', 'yi2', 'sw'),
            outputs=('yo',),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_522__switch_sig_2_1_by_sig',
            module_filename='typ_522__switch_sig_2_1_by_sig.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='switch_sig_3_1_by_sig',
            typ_id='523',
            blkdef_name='Switch sig 3->1 by sig',
            sample_display_name='Switch sig 3->1 by sig',
            display_label='Switch sig 3->1 by sig',
            category_path=('Native', 'Logic and Events', 'Switching and Selection'),
            inputs=('yi1', 'yi2', 'yi3', 'sw'),
            outputs=('yo',),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_523__switch_sig_3_1_by_sig',
            module_filename='typ_523__switch_sig_3_1_by_sig.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='switch_sig_4_1_by_sig',
            typ_id='524',
            blkdef_name='Switch sig 4->1 by sig',
            sample_display_name='Switch sig 4->1 by sig',
            display_label='Switch sig 4->1 by sig',
            category_path=('Native', 'Logic and Events', 'Switching and Selection'),
            inputs=('yi1', 'yi2', 'yi3', 'yi4', 'sw'),
            outputs=('yo',),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_524__switch_sig_4_1_by_sig',
            module_filename='typ_524__switch_sig_4_1_by_sig.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='switch_sw_equal_c_2s_1s',
            typ_id='525',
            blkdef_name='Switch sw equal C 2s->1s',
            sample_display_name='Switch sw equal C 2s->1s',
            display_label='Switch sw equal C 2s->1s',
            category_path=('Native', 'Logic and Events', 'Switching and Selection'),
            inputs=('yi1', 'sw', 'yi2'),
            outputs=('yo',),
            states=(),
            params=('C',),
            unsupported_lines=(),
            module_name='typ_525__switch_sw_equal_c_2s_1s',
            module_filename='typ_525__switch_sw_equal_c_2s_1s.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='switch_sw_greater_than_c_2s_1s',
            typ_id='526',
            blkdef_name='Switch sw greater than C 2s->1s',
            sample_display_name='Switch sw greater than C 2s->1s',
            display_label='Switch sw greater than C 2s->1s',
            category_path=('Native', 'Logic and Events', 'Switching and Selection'),
            inputs=('yi1', 'sw', 'yi2'),
            outputs=('yo',),
            states=(),
            params=('C',),
            unsupported_lines=(),
            module_name='typ_526__switch_sw_greater_than_c_2s_1s',
            module_filename='typ_526__switch_sw_greater_than_c_2s_1s.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='switch_sw_greater_than_or_equal_c_2s_1s',
            typ_id='527',
            blkdef_name='Switch sw greater than or equal C 2s->1s',
            sample_display_name='Switch sw greater than or equal C 2s->1s',
            display_label='Switch sw greater than or equal C 2s->1s',
            category_path=('Native', 'Logic and Events', 'Switching and Selection'),
            inputs=('yi1', 'sw', 'yi2'),
            outputs=('yo',),
            states=(),
            params=('C',),
            unsupported_lines=(),
            module_name='typ_527__switch_sw_greater_than_or_equal_c_2s_1s',
            module_filename='typ_527__switch_sw_greater_than_or_equal_c_2s_1s.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='switch_sw_not_equal_c_2s_1s',
            typ_id='528',
            blkdef_name='Switch sw not equal C 2s->1s',
            sample_display_name='Switch sw not equal C 2s->1s',
            display_label='Switch sw not equal C 2s->1s',
            category_path=('Native', 'Logic and Events', 'Gates and Memory'),
            inputs=('yi1', 'sw', 'yi2'),
            outputs=('yo',),
            states=(),
            params=('C',),
            unsupported_lines=(),
            module_name='typ_528__switch_sw_not_equal_c_2s_1s',
            module_filename='typ_528__switch_sw_not_equal_c_2s_1s.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='switch_sw_smaller_than_c_2s_1s',
            typ_id='529',
            blkdef_name='Switch sw smaller than C 2s->1s',
            sample_display_name='Switch sw smaller than C 2s->1s',
            display_label='Switch sw smaller than C 2s->1s',
            category_path=('Native', 'Logic and Events', 'Switching and Selection'),
            inputs=('yi1', 'sw', 'yi2'),
            outputs=('yo',),
            states=(),
            params=('C',),
            unsupported_lines=(),
            module_name='typ_529__switch_sw_smaller_than_c_2s_1s',
            module_filename='typ_529__switch_sw_smaller_than_c_2s_1s.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='switch_sw_smaller_than_or_equal_c_2s_1s',
            typ_id='530',
            blkdef_name='Switch sw smaller than or equal C 2s->1s',
            sample_display_name='Switch sw smaller than or equal C 2s->1s',
            display_label='Switch sw smaller than or equal C 2s->1s',
            category_path=('Native', 'Logic and Events', 'Switching and Selection'),
            inputs=('yi1', 'sw', 'yi2'),
            outputs=('yo',),
            states=(),
            params=('C',),
            unsupported_lines=(),
            module_name='typ_530__switch_sw_smaller_than_or_equal_c_2s_1s',
            module_filename='typ_530__switch_sw_smaller_than_or_equal_c_2s_1s.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='timer_reset',
            typ_id='531',
            blkdef_name='Timer  _reset',
            sample_display_name='Timer  _reset',
            display_label='Timer (reset)',
            category_path=('Native', 'Waveforms and Time', 'Time Sources and Timers'),
            inputs=('rst',),
            outputs=('yo',),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_531__timer_reset',
            module_filename='typ_531__timer_reset.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='timer_reset_hold_reset_t0_reset_incfw',
            typ_id='532',
            blkdef_name='Timer (reset/hold reset/t0) _reset_incfw',
            sample_display_name='Timer (reset/hold reset/t0) _reset_incfw',
            display_label='Timer (reset/hold reset/t0) (reset) incfw',
            category_path=('Native', 'Waveforms and Time', 'Time Sources and Timers'),
            inputs=('rst', 't0'),
            outputs=('yo',),
            states=('Timer (reset/hold reset/t0) _reset_incfw__x',),
            params=('flank', 't_start_delay'),
            unsupported_lines=(),
            module_name='typ_532__timer_reset_hold_reset_t0_reset_incfw',
            module_filename='typ_532__timer_reset_hold_reset_t0_reset_incfw.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='clarke_transform_power_invariant',
            typ_id='533',
            blkdef_name='Clarke transform (power invariant)',
            sample_display_name='Clarke transform (power invariant)',
            display_label='Clarke transform (power invariant)',
            category_path=('Native', 'Transforms', 'Clarke, Park and dq0'),
            inputs=('a', 'b', 'c'),
            outputs=('alpha', 'beta', 'gamma'),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_533__clarke_transform_power_invariant',
            module_filename='typ_533__clarke_transform_power_invariant.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='clarke_transform',
            typ_id='534',
            blkdef_name='Clarke transform',
            sample_display_name='Clarke transform',
            display_label='Clarke transform',
            category_path=('Native', 'Transforms', 'Clarke, Park and dq0'),
            inputs=('a', 'b', 'c'),
            outputs=('alpha', 'beta', 'gamma'),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_534__clarke_transform',
            module_filename='typ_534__clarke_transform.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='inverse_clarke_transform_pow_invariant',
            typ_id='535',
            blkdef_name='Inverse Clarke transform(pow. invariant)',
            sample_display_name='Inverse Clarke transform(pow. invariant)',
            display_label='Inverse Clarke transform(pow. invariant)',
            category_path=('Native', 'Transforms', 'Clarke, Park and dq0'),
            inputs=('alpha', 'beta', 'gamma'),
            outputs=('a', 'b', 'c'),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_535__inverse_clarke_transform_pow_invariant',
            module_filename='typ_535__inverse_clarke_transform_pow_invariant.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='inverse_clarke_transform',
            typ_id='536',
            blkdef_name='Inverse Clarke transform',
            sample_display_name='Inverse Clarke transform',
            display_label='Inverse Clarke transform',
            category_path=('Native', 'Transforms', 'Clarke, Park and dq0'),
            inputs=('alpha', 'beta', 'gamma'),
            outputs=('a', 'b', 'c'),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_536__inverse_clarke_transform',
            module_filename='typ_536__inverse_clarke_transform.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='inverse_park_transform_dq',
            typ_id='537',
            blkdef_name='Inverse Park transform (dq)',
            sample_display_name='Inverse Park transform (dq)',
            display_label='Inverse Park transform (dq)',
            category_path=('Native', 'Transforms', 'Clarke, Park and dq0'),
            inputs=('d', 'q', 'cosphi', 'sinphi'),
            outputs=('alpha', 'beta'),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_537__inverse_park_transform_dq',
            module_filename='typ_537__inverse_park_transform_dq.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='inverse_park_transform_dq0',
            typ_id='538',
            blkdef_name='Inverse Park transform (dq0)',
            sample_display_name='Inverse Park transform (dq0)',
            display_label='Inverse Park transform (dq0)',
            category_path=('Native', 'Transforms', 'Clarke, Park and dq0'),
            inputs=('d', 'q', 'zero', 'cosphi', 'sinphi'),
            outputs=('alpha', 'beta', 'gamma'),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_538__inverse_park_transform_dq0',
            module_filename='typ_538__inverse_park_transform_dq0.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='park_transform_dq',
            typ_id='539',
            blkdef_name='Park transform (dq)',
            sample_display_name='Park transform (dq)',
            display_label='Park transform (dq)',
            category_path=('Native', 'Transforms', 'Clarke, Park and dq0'),
            inputs=('alpha', 'beta', 'cosphi', 'sinphi'),
            outputs=('d', 'q'),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_539__park_transform_dq',
            module_filename='typ_539__park_transform_dq.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='park_transform_dq0',
            typ_id='540',
            blkdef_name='Park transform (dq0)',
            sample_display_name='Park transform (dq0)',
            display_label='Park transform (dq0)',
            category_path=('Native', 'Transforms', 'Clarke, Park and dq0'),
            inputs=('alpha', 'beta', 'gamma', 'cosphi', 'sinphi'),
            outputs=('d', 'q', 'zero'),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_540__park_transform_dq0',
            module_filename='typ_540__park_transform_dq0.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='rms_value_p_u',
            typ_id='541',
            blkdef_name='RMS value p.u.',
            sample_display_name='RMS value p.u.',
            display_label='RMS value p.u.',
            category_path=('Native', 'Transforms', 'RMS and Sequence'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=('fn',),
            unsupported_lines=(),
            module_name='typ_541__rms_value_p_u',
            module_filename='typ_541__rms_value_p_u.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='rms_value',
            typ_id='542',
            blkdef_name='RMS value',
            sample_display_name='RMS value',
            display_label='RMS value',
            category_path=('Native', 'Transforms', 'RMS and Sequence'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=('fn',),
            unsupported_lines=(),
            module_name='typ_542__rms_value',
            module_filename='typ_542__rms_value.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='u_seq_ab0_u_abc',
            typ_id='543',
            blkdef_name='U seq/ab0 -> U abc',
            sample_display_name='U seq/ab0 -> U abc',
            display_label='U seq/ab0 -> U abc',
            category_path=('Native', 'Transforms', 'RMS and Sequence'),
            inputs=('u1', 'u1r', 'u1i', 'u2r', 'u2i', 'u0r', 'u0i', 'u0'),
            outputs=('ua', 'ub', 'uc', 'uab', 'ubc', 'uca'),
            states=(),
            params=('fn',),
            unsupported_lines=(),
            module_name='typ_543__u_seq_ab0_u_abc',
            module_filename='typ_543__u_seq_ab0_u_abc.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='abc_dq0_power_invariant_align_a_d',
            typ_id='544',
            blkdef_name='abc->dq0 (power invariant -- align a->d)',
            sample_display_name='abc->dq0 (power invariant -- align a->d)',
            display_label='abc->dq0 (power invariant -- align a->d)',
            category_path=('Native', 'Transforms', 'Clarke, Park and dq0'),
            inputs=('a', 'b', 'c', 'theta'),
            outputs=('d', 'q', 'zero'),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_544__abc_dq0_power_invariant_align_a_d',
            module_filename='typ_544__abc_dq0_power_invariant_align_a_d.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='abc_dq0_power_invariant_align_a_q',
            typ_id='545',
            blkdef_name='abc->dq0 (power invariant -- align a->q)',
            sample_display_name='abc->dq0 (power invariant -- align a->q)',
            display_label='abc->dq0 (power invariant -- align a->q)',
            category_path=('Native', 'Transforms', 'Clarke, Park and dq0'),
            inputs=('a', 'b', 'c', 'theta'),
            outputs=('d', 'q', 'zero'),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_545__abc_dq0_power_invariant_align_a_q',
            module_filename='typ_545__abc_dq0_power_invariant_align_a_q.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='abc_dq0_power_variant_align_a_d',
            typ_id='546',
            blkdef_name='abc->dq0 (power variant -- align a->d)',
            sample_display_name='abc->dq0 (power variant -- align a->d)',
            display_label='abc->dq0 (power variant -- align a->d)',
            category_path=('Native', 'Transforms', 'Clarke, Park and dq0'),
            inputs=('a', 'b', 'c', 'theta'),
            outputs=('d', 'q', 'zero'),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_546__abc_dq0_power_variant_align_a_d',
            module_filename='typ_546__abc_dq0_power_variant_align_a_d.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='abc_dq0_power_variant_align_a_q',
            typ_id='547',
            blkdef_name='abc->dq0 (power variant -- align a->q)',
            sample_display_name='abc->dq0 (power variant -- align a->q)',
            display_label='abc->dq0 (power variant -- align a->q)',
            category_path=('Native', 'Transforms', 'Clarke, Park and dq0'),
            inputs=('a', 'b', 'c', 'theta'),
            outputs=('d', 'q', 'zero'),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_547__abc_dq0_power_variant_align_a_q',
            module_filename='typ_547__abc_dq0_power_variant_align_a_q.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='dq0_abc_power_invariant_align_a_d',
            typ_id='548',
            blkdef_name='dq0->abc (power invariant -- align a->d)',
            sample_display_name='dq0->abc (power invariant -- align a->d)',
            display_label='dq0->abc (power invariant -- align a->d)',
            category_path=('Native', 'Transforms', 'Clarke, Park and dq0'),
            inputs=('d', 'q', 'zero', 'theta'),
            outputs=('a', 'b', 'c'),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_548__dq0_abc_power_invariant_align_a_d',
            module_filename='typ_548__dq0_abc_power_invariant_align_a_d.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='dq0_abc_power_invariant_align_a_q',
            typ_id='549',
            blkdef_name='dq0->abc (power invariant -- align a->q)',
            sample_display_name='dq0->abc (power invariant -- align a->q)',
            display_label='dq0->abc (power invariant -- align a->q)',
            category_path=('Native', 'Transforms', 'Clarke, Park and dq0'),
            inputs=('d', 'q', 'zero', 'theta'),
            outputs=('a', 'b', 'c'),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_549__dq0_abc_power_invariant_align_a_q',
            module_filename='typ_549__dq0_abc_power_invariant_align_a_q.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='dq0_abc_power_variant_align_a_d',
            typ_id='550',
            blkdef_name='dq0->abc (power variant -- align a->d)',
            sample_display_name='dq0->abc (power variant -- align a->d)',
            display_label='dq0->abc (power variant -- align a->d)',
            category_path=('Native', 'Transforms', 'Clarke, Park and dq0'),
            inputs=('d', 'q', 'zero', 'theta'),
            outputs=('a', 'b', 'c'),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_550__dq0_abc_power_variant_align_a_d',
            module_filename='typ_550__dq0_abc_power_variant_align_a_d.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='dq0_abc_power_variant_align_a_q',
            typ_id='551',
            blkdef_name='dq0->abc (power variant -- align a->q)',
            sample_display_name='dq0->abc (power variant -- align a->q)',
            display_label='dq0->abc (power variant -- align a->q)',
            category_path=('Native', 'Transforms', 'Clarke, Park and dq0'),
            inputs=('d', 'q', 'zero', 'theta'),
            outputs=('a', 'b', 'c'),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_551__dq0_abc_power_variant_align_a_q',
            module_filename='typ_551__dq0_abc_power_variant_align_a_q.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='hz_p_u',
            typ_id='552',
            blkdef_name='Hz -> p.u.',
            sample_display_name='Hz -> p.u.',
            display_label='Hz -> p.u.',
            category_path=('Native', 'Control and Measurement', 'Measurements and Units'),
            inputs=('Freq',),
            outputs=('fpu',),
            states=(),
            params=('freqbase',),
            unsupported_lines=(),
            module_name='typ_552__hz_p_u',
            module_filename='typ_552__hz_p_u.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='nm_p_u',
            typ_id='553',
            blkdef_name='Nm -> p.u.',
            sample_display_name='Nm -> p.u.',
            display_label='Nm -> p.u.',
            category_path=('Native', 'Control and Measurement', 'Measurements and Units'),
            inputs=('M',),
            outputs=('m',),
            states=(),
            params=('freqbase', 'Zp', 'Pel_base'),
            unsupported_lines=(),
            module_name='typ_553__nm_p_u',
            module_filename='typ_553__nm_p_u.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='abs_p_u_par',
            typ_id='554',
            blkdef_name='abs -> p.u. (par)',
            sample_display_name='abs -> p.u. (par)',
            display_label='abs -> p.u. (par)',
            category_path=('Native', 'Control and Measurement', 'Measurements and Units'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=('base',),
            unsupported_lines=(),
            module_name='typ_554__abs_p_u_par',
            module_filename='typ_554__abs_p_u_par.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='abs_p_u_sig',
            typ_id='555',
            blkdef_name='abs -> p.u. (sig)',
            sample_display_name='abs -> p.u. (sig)',
            display_label='abs -> p.u. (sig)',
            category_path=('Native', 'Control and Measurement', 'Measurements and Units'),
            inputs=('yi', 'base'),
            outputs=('yo',),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_555__abs_p_u_sig',
            module_filename='typ_555__abs_p_u_sig.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='deg_rad',
            typ_id='556',
            blkdef_name='deg -> rad',
            sample_display_name='deg -> rad',
            display_label='deg -> rad',
            category_path=('Native', 'Control and Measurement', 'Measurements and Units'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_556__deg_rad',
            module_filename='typ_556__deg_rad.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='p_u_hz',
            typ_id='557',
            blkdef_name='p.u. -> Hz',
            sample_display_name='p.u. -> Hz',
            display_label='p.u. -> Hz',
            category_path=('Native', 'Control and Measurement', 'Measurements and Units'),
            inputs=('fpu',),
            outputs=('Freq',),
            states=(),
            params=('freqbase',),
            unsupported_lines=(),
            module_name='typ_557__p_u_hz',
            module_filename='typ_557__p_u_hz.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='p_u_abs_par',
            typ_id='558',
            blkdef_name='p.u. -> abs (par)',
            sample_display_name='p.u. -> abs (par)',
            display_label='p.u. -> abs (par)',
            category_path=('Native', 'Control and Measurement', 'Measurements and Units'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=('base',),
            unsupported_lines=(),
            module_name='typ_558__p_u_abs_par',
            module_filename='typ_558__p_u_abs_par.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='p_u_abs_sig',
            typ_id='559',
            blkdef_name='p.u. -> abs (sig)',
            sample_display_name='p.u. -> abs (sig)',
            display_label='p.u. -> abs (sig)',
            category_path=('Native', 'Control and Measurement', 'Measurements and Units'),
            inputs=('yi', 'base'),
            outputs=('yo',),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_559__p_u_abs_sig',
            module_filename='typ_559__p_u_abs_sig.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='p_u_rpm',
            typ_id='560',
            blkdef_name='p.u. -> rpm',
            sample_display_name='p.u. -> rpm',
            display_label='p.u. -> rpm',
            category_path=('Native', 'Control and Measurement', 'Measurements and Units'),
            inputs=('speed',),
            outputs=('n',),
            states=(),
            params=('Zp', 'freqbase'),
            unsupported_lines=(),
            module_name='typ_560__p_u_rpm',
            module_filename='typ_560__p_u_rpm.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='rad_deg',
            typ_id='561',
            blkdef_name='rad -> deg',
            sample_display_name='rad -> deg',
            display_label='rad -> deg',
            category_path=('Native', 'Control and Measurement', 'Measurements and Units'),
            inputs=('yi',),
            outputs=('yo',),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_561__rad_deg',
            module_filename='typ_561__rad_deg.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='rad_s_rpm',
            typ_id='562',
            blkdef_name='rad/s -> rpm',
            sample_display_name='rad/s -> rpm',
            display_label='rad/s -> rpm',
            category_path=('Native', 'Control and Measurement', 'Measurements and Units'),
            inputs=('omega',),
            outputs=('n',),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_562__rad_s_rpm',
            module_filename='typ_562__rad_s_rpm.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='rpm_p_u',
            typ_id='563',
            blkdef_name='rpm -> p.u.',
            sample_display_name='rpm -> p.u.',
            display_label='rpm -> p.u.',
            category_path=('Native', 'Control and Measurement', 'Measurements and Units'),
            inputs=('n',),
            outputs=('speed',),
            states=(),
            params=('Zp', 'freqbase'),
            unsupported_lines=(),
            module_name='typ_563__rpm_p_u',
            module_filename='typ_563__rpm_p_u.py',
        )
    )

    records.append(
        BasicBlockCatalogStaticRecord(
            template_key='rpm_rad_s',
            typ_id='564',
            blkdef_name='rpm -> rad/s',
            sample_display_name='rpm -> rad/s',
            display_label='rpm -> rad/s',
            category_path=('Native', 'Control and Measurement', 'Measurements and Units'),
            inputs=('n',),
            outputs=('omega',),
            states=(),
            params=(),
            unsupported_lines=(),
            module_name='typ_564__rpm_rad_s',
            module_filename='typ_564__rpm_rad_s.py',
        )
    )

    return tuple(records)
