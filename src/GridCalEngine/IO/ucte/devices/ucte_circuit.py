# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from typing import List, Dict
from GridCalEngine.IO.ucte.devices.ucte_node import UcteNode
from GridCalEngine.IO.ucte.devices.ucte_comment import UcteComment
from GridCalEngine.IO.ucte.devices.ucte_line import UcteLine
from GridCalEngine.IO.ucte.devices.ucte_transformer import UcteTransformer
from GridCalEngine.IO.ucte.devices.ucte_transformer_regulation import UcteTransformerRegulation
from GridCalEngine.IO.ucte.devices.ucte_transformer_tap_table import UcteTransformerTapTable
from GridCalEngine.IO.ucte.devices.ucte_exchange_power import UcteExchangePower
from GridCalEngine.basic_structures import Logger


class UcteCircuit:
    """
    UCTE circuit class
    """


    def __init__(self):
        """

        """
        self.comments: List[UcteComment] = list()
        self.nodes: List[UcteNode] = list()
        self.lines: List[UcteLine] = list()
        self.transformers: List[UcteTransformer] = list()
        self.regulations: List[UcteTransformerRegulation] = list()
        self.transformer_tap_tables: List[UcteTransformerTapTable] = list()
        self.exchange_powers: List[UcteExchangePower] = list()

        self.regulations_dict: Dict[str, UcteTransformerRegulation] = dict()
        self.transformer_tap_tables_dict: Dict[str, UcteTransformerTapTable] = dict()

    @staticmethod
    def check_file_extension(f_name: str) -> bool:
        """
        Check that file extension is ok
        :param f_name: file name
        :return: is ok?
        """
        fname2 = f_name.lower()
        return fname2.endswith(".ucte") or fname2.endswith(".uct")

    def parse_file(self, files: List[str], logger: Logger = None):
        """
        parse a list of UCTE files
        :param files: list of UCTE files
        :param logger: logger object
        :return:
        """

        if logger is None:
            logger = Logger()

        for file_path in files:

            if self.check_file_extension(file_path):
                current_block = None

                with open(file_path, "r") as file:
                    for line in file:
                        if line.startswith("##"):
                            if line.startswith("##C"):
                                current_block = "comments"
                            elif line.startswith("##N"):
                                current_block = "nodes"
                            elif line.startswith("##L"):
                                current_block = "lines"
                            elif line.startswith("##T"):
                                current_block = "transformers"
                            elif line.startswith("##R"):
                                current_block = "regulations"
                            elif line.startswith("##TT"):
                                current_block = "special_transformers"
                            elif line.startswith("##E"):
                                current_block = "exchange_powers"
                            else:
                                pass
                        else:
                            if current_block == "comments":
                                comment = UcteComment()
                                comment.parse(line)
                                self.comments.append(comment)

                            elif current_block == "nodes":
                                node = UcteNode()
                                node.parse(line, logger)
                                self.nodes.append(node)

                            elif current_block == "lines":
                                line_obj = UcteLine()
                                line_obj.parse(line, logger)
                                self.lines.append(line_obj)

                            elif current_block == "transformers":
                                transformer = UcteTransformer()
                                transformer.parse(line, logger)
                                self.transformers.append(transformer)

                            elif current_block == "regulations":
                                regulation = UcteTransformerRegulation()
                                regulation.parse(line, logger)
                                self.regulations.append(regulation)
                                self.regulations_dict[regulation.get_primary_key()] = regulation


                            elif current_block == "special_transformers":
                                special_transformer = UcteTransformerTapTable()
                                special_transformer.parse(line, logger)
                                self.transformer_tap_tables.append(special_transformer)
                                self.transformer_tap_tables_dict[special_transformer.get_primary_key()] = special_transformer


                            elif current_block == "exchange_powers":
                                exchange = UcteExchangePower()
                                exchange.parse(line, logger)
                                self.exchange_powers.append(exchange)
            else:
                logger.add_error("Passed non-ucte file to UCTE reading process",
                                 value=file_path)

    def get_transformer_regulation(self, elm: UcteTransformer) -> UcteTransformerRegulation | None:
        """

        :param elm:
        :return:
        """
        key = elm.get_primary_key()
        return self.regulations_dict.get(key, None)

    def get_transformers_tap_table(self, elm: UcteTransformer) -> UcteTransformerTapTable | None:
        """

        :param elm:
        :return:
        """
        key = elm.get_primary_key()
        return self.transformer_tap_tables_dict.get(key, None)

    def summary(self):
        print(f"Comments: {len(self.comments)}")
        print(f"Nodes: {len(self.nodes)}")
        print(f"Lines: {len(self.lines)}")
        print(f"Transformers: {len(self.transformers)}")
        print(f"Regulations: {len(self.regulations)}")
        print(f"Special Transformers: {len(self.transformer_tap_tables)}")
        print(f"Exchange Powers: {len(self.exchange_powers)}")

    def fuse_comments(self):
        """
        fuse comments as one
        :return:
        """
        val = ""
        for cmnt in self.comments:
            val += cmnt.content + "\n"

        return val

