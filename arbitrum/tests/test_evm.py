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
from pyevmasm import instruction_tables, assemble_hex, assemble_one, disassemble_one
import random
from unittest import TestCase

from arbitrum import run_vm_once, value
from arbitrum.evm.contract import create_evm_vm
from arbitrum.evm.contract_abi import ContractABI, create_output_handler
from arbitrum import messagestack
from arbitrum.evm.log import EVMReturn, EVMStop


def make_msg_val(message):
    return [0, 0, 0, message]


def run_until_block(vm, test):
    while True:
        try:
            # print(vm.pc, vm.pc.path)
            run = run_vm_once(vm)
            if not run:
                break
        except Exception as err:
            test.fail("VM run hit error {}".format(err))
        if vm.halted:
            test.fail("VM unintentionally halted")


def make_evm_ext_code(op, address):
    instruction_table = instruction_tables["byzantium"]
    return [
        assemble_one("PUSH20 " + address),
        op,
        assemble_one("PUSH1 0x00"),
        instruction_table["MSTORE"],
        assemble_one("PUSH1 0x20"),
        assemble_one("PUSH1 0x00"),
        instruction_table["RETURN"],
    ]


def make_evm_codecopy_code(offset, length, address):
    return_data_size = ((length + 31) // 32) * 32 + 64
    instruction_table = instruction_tables["byzantium"]
    return [
        assemble_one(
            "PUSH32 0x" + length.to_bytes(32, byteorder="big").hex()
        ),  # length
        assemble_one(
            "PUSH32 0x" + offset.to_bytes(32, byteorder="big").hex()
        ),  # offset
        assemble_one("PUSH32 0x40"),  # destOffset
        assemble_one("PUSH20 " + address),
        instruction_table["EXTCODECOPY"],
        assemble_one("PUSH32 0x20"),
        assemble_one("PUSH1 0x00"),
        instruction_table["MSTORE"],
        assemble_one("PUSH32 0x" + length.to_bytes(32, byteorder="big").hex()),
        assemble_one("PUSH1 0x20"),
        instruction_table["MSTORE"],
        assemble_one(
            "PUSH32 0x" + return_data_size.to_bytes(32, byteorder="big").hex()
        ),
        assemble_one("PUSH1 0x00"),
        instruction_table["RETURN"],
    ]


def make_contract(evm_code, return_type):
    return ContractABI(
        {
            "address": "0x895521964D724c8362A36608AAf09A3D7d0A0445",
            "abi": [
                {
                    "constant": False,
                    "inputs": [],
                    "name": "testMethod",
                    "outputs": [{"name": "", "type": return_type}],
                    "payable": False,
                    "stateMutability": "view",
                    "type": "function",
                }
            ],
            "name": "TestContract",
            "code": assemble_hex(evm_code),
            "storage": {},
        }
    )


def create_many_contracts(contract_a):
    contracts = [contract_a]
    for _ in range(10):
        contracts.append(
            ContractABI(
                {
                    "address": eth_utils.to_checksum_address(
                        random.getrandbits(8 * 20).to_bytes(20, byteorder="big").hex()
                    ),
                    "abi": [],
                    "name": "TestContract",
                    "code": "0x00",
                    "storage": {},
                }
            )
        )
    return contracts


address_string = "0x2c1b4360234d8e65a9e162ef82d70bee71324512"
address = eth_utils.to_int(hexstr=address_string)

dest_address_string = "0x895521964D724c8362A36608AAf09A3D7d0A0445"
dest_address = eth_utils.to_int(hexstr=dest_address_string)


class TestEVM(TestCase):
    _multiprocess_can_split_ = True

    def test_codesize_contract(self):
        instruction_table = instruction_tables["byzantium"]
        evm_code = make_evm_ext_code(
            instruction_table["EXTCODESIZE"],
            "0x895521964D724c8362A36608AAf09A3D7d0A0445",
        )
        code_size = len(evm_code) + sum(op.operand_size for op in evm_code)
        contract_a = make_contract(evm_code, "uint256")
        contracts = create_many_contracts(contract_a)
        vm = create_evm_vm(contracts, False, False)
        output_handler = create_output_handler(contracts)
        vm.env.messages = messagestack.addMessage(
            value.Tuple([]),
            value.Tuple(
                make_msg_val(
                    value.Tuple(
                        [0, 2345, contract_a.testMethod(0, 0)]
                    )  # type  # sender
                )
            ),
        )
        run_until_block(vm, self)
        self.assertEqual(len(vm.logs), 1)
        val = vm.logs[0]
        parsed_out = output_handler(val)
        self.assertIsInstance(parsed_out, EVMReturn)
        self.assertEqual(parsed_out.output_values[0], code_size)

    def test_codesize_empty(self):
        instruction_table = instruction_tables["byzantium"]
        evm_code = make_evm_ext_code(instruction_table["EXTCODESIZE"], "0x9999")
        contract_a = make_contract(evm_code, "uint256")
        contracts = create_many_contracts(contract_a)
        vm = create_evm_vm(contracts, True, False)
        output_handler = create_output_handler(contracts)
        vm.env.messages = messagestack.addMessage(
            value.Tuple([]),
            value.Tuple(
                make_msg_val(
                    value.Tuple(
                        [0, 2345, contract_a.testMethod(0, 0)]
                    )  # type  # sender
                )
            ),
        )
        run_until_block(vm, self)
        self.assertEqual(len(vm.logs), 1)
        val = vm.logs[0]
        parsed_out = output_handler(val)
        self.assertIsInstance(parsed_out, EVMReturn)
        self.assertEqual(parsed_out.output_values[0], 0)

    def test_codehash_contract(self):
        evm_code = make_evm_ext_code(
            disassemble_one(bytes.fromhex("3f")),
            "0x895521964D724c8362A36608AAf09A3D7d0A0445",
        )
        hex_code = assemble_hex(evm_code)
        code_hash = int.from_bytes(
            eth_utils.crypto.keccak(hexstr=hex_code), byteorder="big"
        )
        contract_a = make_contract(evm_code, "uint256")
        contracts = create_many_contracts(contract_a)
        vm = create_evm_vm(contracts, True, False)
        output_handler = create_output_handler(contracts)
        vm.env.messages = messagestack.addMessage(
            value.Tuple([]),
            value.Tuple(
                make_msg_val(
                    value.Tuple(
                        [0, 2345, contract_a.testMethod(0, 0)]
                    )  # type  # sender
                )
            ),
        )
        run_until_block(vm, self)
        self.assertEqual(len(vm.logs), 1)
        val = vm.logs[0]
        parsed_out = output_handler(val)
        self.assertIsInstance(parsed_out, EVMReturn)
        self.assertEqual(parsed_out.output_values[0], code_hash)

    def test_codehash_empty(self):
        evm_code = make_evm_ext_code(disassemble_one(bytes.fromhex("3f")), "0x9999")
        contract_a = make_contract(evm_code, "uint256")
        contracts = create_many_contracts(contract_a)
        vm = create_evm_vm(contracts, True, False)
        output_handler = create_output_handler(contracts)
        vm.env.messages = messagestack.addMessage(
            value.Tuple([]),
            value.Tuple(
                make_msg_val(
                    value.Tuple(
                        [0, 2345, contract_a.testMethod(0, 0)]
                    )  # type  # sender
                )
            ),
        )
        run_until_block(vm, self)
        self.assertEqual(len(vm.logs), 1)
        val = vm.logs[0]
        parsed_out = output_handler(val)
        self.assertIsInstance(parsed_out, EVMReturn)
        self.assertEqual(parsed_out.output_values[0], 0)

    def test_codecopy_contract(self):
        offset = 30
        length = 80
        evm_code = make_evm_codecopy_code(
            offset, length, "0x895521964D724c8362A36608AAf09A3D7d0A0445"
        )
        hex_code = assemble_hex(evm_code)
        contract_a = make_contract(evm_code, "bytes")
        contracts = create_many_contracts(contract_a)
        vm = create_evm_vm(contracts, True, False)
        output_handler = create_output_handler(contracts)
        vm.env.messages = messagestack.addMessage(
            value.Tuple([]),
            value.Tuple(
                make_msg_val(
                    value.Tuple(
                        [0, 2345, contract_a.testMethod(0, 0)]
                    )  # type  # sender
                )
            ),
        )
        run_until_block(vm, self)
        self.assertEqual(len(vm.logs), 1)
        val = vm.logs[0]
        parsed_out = output_handler(val)
        self.assertIsInstance(parsed_out, EVMReturn)
        self.assertEqual(
            parsed_out.output_values[0].hex(),
            hex_code[2 + offset * 2 : 2 + offset * 2 + length * 2],
        )

    def test_codecopy_empty(self):
        offset = 30
        length = 80
        evm_code = make_evm_codecopy_code(offset, length, "0x9999")
        contract_a = make_contract(evm_code, "bytes")
        contracts = create_many_contracts(contract_a)
        vm = create_evm_vm(contracts, True, False)
        output_handler = create_output_handler(contracts)
        vm.env.messages = messagestack.addMessage(
            value.Tuple([]),
            value.Tuple(
                make_msg_val(
                    value.Tuple(
                        [0, 2345, contract_a.testMethod(0, 0)]
                    )  # type  # sender
                )
            ),
        )
        run_until_block(vm, self)
        self.assertEqual(len(vm.logs), 1)
        val = vm.logs[0]
        parsed_out = output_handler(val)
        self.assertIsInstance(parsed_out, EVMReturn)
        self.assertEqual(parsed_out.output_values[0].hex(), "0" * (length * 2))

    def test_balance_succeed(self):
        instruction_table = instruction_tables["byzantium"]
        evm_code = make_evm_ext_code(
            instruction_table["BALANCE"], "0x895521964D724c8362A36608AAf09A3D7d0A0445"
        )
        contract_a = make_contract(evm_code, "uint256")
        contracts = create_many_contracts(contract_a)
        vm = create_evm_vm(contracts, True, False)
        output_handler = create_output_handler(contracts)
        inbox = value.Tuple([])
        inbox = messagestack.addMessage(
            inbox,
            value.Tuple(
                make_msg_val(
                    value.Tuple(
                        [1, 2345, value.Tuple([2345, 100000])]
                    )  # type  # sender
                )
            ),
        )
        inbox = messagestack.addMessage(
            inbox,
            value.Tuple(
                make_msg_val(
                    value.Tuple(
                        [0, 2345, contract_a.testMethod(0, 62244)]  # type  # sender
                    )
                )
            ),
        )
        vm.env.messages = inbox
        run_until_block(vm, self)
        self.assertEqual(len(vm.logs), 2)
        parsed_out0 = output_handler(vm.logs[0])
        parsed_out1 = output_handler(vm.logs[1])
        self.assertIsInstance(parsed_out0, EVMStop)
        self.assertIsInstance(parsed_out1, EVMReturn)
        self.assertEqual(parsed_out1.output_values[0], 62244)
