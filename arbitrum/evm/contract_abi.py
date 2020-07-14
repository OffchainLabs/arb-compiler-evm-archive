# Copyright 2019, Offchain Labs, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from types import MethodType

import eth_abi
import eth_utils

from .contract import Contract
from . import log
from . import contract_templates
from ..std import bytestack_frombytes
from .. import value


def generate_func(func_id, func_abi, address):
    def impl(self, seq, val, *args):
        if len(args) != len(func_abi["inputs"]):
            raise Exception(
                "Function with abi {} passed not matching {} args".format(
                    func_abi, list(args)
                )
            )
        encoded_input = func_id + eth_abi.encode_abi(
            [inp["type"] for inp in func_abi["inputs"]], list(args)
        )
        msg_data = bytestack_frombytes(encoded_input)
        return value.Tuple([address, seq, val, msg_data])

    return impl


def generate_func2(func_id, func_abi):
    def impl(self, seq, *args):
        encoded_input = eth_abi.encode_abi(
            [inp["type"] for inp in func_abi["inputs"]], list(args)
        )
        return (func_id + encoded_input).hex()

    return impl


def generate_func3(func_id, func_abi, address):
    def impl(self, *args):
        if len(args) != len(func_abi["inputs"]):
            raise Exception(
                "Function with abi {} passed not matching {} args".format(
                    func_abi, list(args)
                )
            )
        encoded_input = func_id + eth_abi.encode_abi(
            [inp["type"] for inp in func_abi["inputs"]], list(args)
        )
        msg_data = bytestack_frombytes(encoded_input)
        return value.Tuple([address, msg_data])

    return impl


class ContractABI(Contract):
    def __init__(self, contractInfo):
        super().__init__(contractInfo)
        self.name = contractInfo["name"]

        abi = contractInfo["abi"]
        func_abis = [func_abi for func_abi in abi if func_abi["type"] == "function"]
        event_abis = [event_abi for event_abi in abi if event_abi["type"] == "event"]

        self.funcs = {}
        for func_abi in func_abis:
            id_bytes = eth_utils.function_abi_to_4byte_selector(func_abi)
            self.funcs[id_bytes] = func_abi

        for func_id, func_abi in self.funcs.items():
            setattr(
                self,
                func_abi["name"],
                MethodType(generate_func(func_id, func_abi, self.address), self),
            )
            setattr(
                self,
                "_" + func_abi["name"],
                MethodType(generate_func2(func_id, func_abi), self),
            )
            setattr(
                self,
                "call_" + func_abi["name"],
                MethodType(generate_func3(func_id, func_abi, self.address), self),
            )

        self.events = {}
        for event_abi in event_abis:
            id_bytes = eth_utils.event_abi_to_log_topic(event_abi)
            event_id = eth_utils.big_endian_to_int(id_bytes)
            self.events[event_id] = event_abi

    def __repr__(self):
        return "ContractABI({})".format(self.name)


def create_output_handler(contracts):
    events = {}
    functions = {}
    arbsys_template = contract_templates.get_arbsys()
    erc20_template = contract_templates.get_erc20_contract()
    erc721_template = contract_templates.get_erc721_contract()
    extra_contracts = [
        ContractABI(arbsys_template),
        ContractABI(erc20_template),
        ContractABI(erc721_template),
    ]
    for contract in contracts + extra_contracts:
        for event_id, abi in contract.events.items():
            if contract.address not in events:
                events[contract.address] = {}
            events[contract.address][event_id] = abi
        for func_id, abi in contract.funcs.items():
            if contract.address not in functions:
                functions[contract.address] = {}
            functions[contract.address][func_id.hex()] = abi

    def output_handler(output):
        output = log.parse(output)
        output.decode(functions, events)
        return output

    return output_handler
