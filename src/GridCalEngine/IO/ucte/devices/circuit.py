# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from typing import List
from GridCalEngine.IO.ucte.devices.node import Node
from GridCalEngine.IO.ucte.devices.comment import Comment
from GridCalEngine.IO.ucte.devices.line import Line
from GridCalEngine.IO.ucte.devices.transformer import Transformer
from GridCalEngine.IO.ucte.devices.transformer_regulation import TransformerRegulation
from GridCalEngine.IO.ucte.devices.transformer_special import TransformerSpecial
from GridCalEngine.IO.ucte.devices.exchange_power import ExchangePower
from GridCalEngine.basic_structures import Logger


class UCTECircuit:
    """
    UCTE circuit class
    """


    def __init__(self):
        """

        """
        self.comments: List[Comment] = list()
        self.nodes: List[Node] = list()
        self.lines: List[Line] = list()
        self.transformers: List[Transformer] = list()
        self.regulations: List[TransformerRegulation] = list()
        self.special_transformers: List[TransformerSpecial] = list()
        self.exchange_powers: List[ExchangePower] = list()

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

            if file_path.endswith(".ucte"):
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
                                comment = Comment()
                                comment.parse(line)
                                self.comments.append(comment)
                            elif current_block == "nodes":
                                node = Node()
                                node.parse(line)
                                self.nodes.append(node)
                            elif current_block == "lines":
                                line_obj = Line()
                                line_obj.parse(line)
                                self.lines.append(line_obj)
                            elif current_block == "transformers":
                                transformer = Transformer()
                                transformer.parse(line)
                                self.transformers.append(transformer)
                            elif current_block == "regulations":
                                regulation = TransformerRegulation()
                                regulation.parse(line)
                                self.regulations.append(regulation)
                            elif current_block == "special_transformers":
                                special_transformer = TransformerSpecial()
                                special_transformer.parse(line)
                                self.special_transformers.append(special_transformer)
                            elif current_block == "exchange_powers":
                                exchange = ExchangePower()
                                exchange.parse(line)
                                self.exchange_powers.append(exchange)
            else:
                logger.add_error("Passed non-ucte file to UCTE reading process",
                                 value=file_path)

    def summary(self):
        print(f"Comments: {len(self.comments)}")
        print(f"Nodes: {len(self.nodes)}")
        print(f"Lines: {len(self.lines)}")
        print(f"Transformers: {len(self.transformers)}")
        print(f"Regulations: {len(self.regulations)}")
        print(f"Special Transformers: {len(self.special_transformers)}")
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

