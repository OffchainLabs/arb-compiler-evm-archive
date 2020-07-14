# Copyright 2019-2020, Offchain Labs, Inc.
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

import eth_utils

from .compile import generate_evm_code
from .. import compile_program
from . import contract_templates


class Contract:
    def __init__(self, contractInfo):
        self.address_string = contractInfo["address"]
        self.address = eth_utils.to_int(hexstr=self.address_string)
        self.code = bytes.fromhex(contractInfo["code"][2:])
        self.storage = {}
        if "storage" in contractInfo:
            raw_storage = contractInfo["storage"]
            for item in raw_storage:
                key = eth_utils.to_int(hexstr=item)
                self.storage[key] = eth_utils.to_int(hexstr=raw_storage[item])

    def __repr__(self):
        return "ArbContract({})".format(self.address_string)


def strip_cbor(code):
    cbor_length = int.from_bytes(code[-2:], byteorder="big")
    return code[: -(cbor_length + 2)]


def create_evm_vm(contracts, should_optimize=True, includes_metadata=True):
    erc20 = Contract(contract_templates.get_erc20_contract())
    erc721 = Contract(contract_templates.get_erc721_contract())
    info = Contract(contract_templates.get_info_contract())

    code = {}
    storage = {}

    for contract in [erc20, erc721, info]:
        code[contract.address] = strip_cbor(contract.code)
        storage[contract.address] = contract.storage

    for contract in contracts:
        if includes_metadata:
            contract_code = strip_cbor(contract.code)
        else:
            contract_code = contract.code
        code[contract.address] = contract_code
        storage[contract.address] = contract.storage

    initial_block, code = generate_evm_code(code, storage)

    return compile_program(initial_block, code, should_optimize)
