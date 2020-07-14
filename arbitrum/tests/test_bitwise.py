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

from unittest import TestCase
import random

from arbitrum.std import bitwise
from arbitrum import VM

TT256 = 2 ** 256
TT256M1 = 2 ** 256 - 1
TT255 = 2 ** 255


def to_signed(i):
    return i if i < TT255 else i - TT256


class TestArray(TestCase):
    def test_flip_endianness(self):
        hexstr = bytearray.fromhex(
            "ada5013122d395ba3c54772283fb069b10426056ef8ca54750cb9bb552a59e7d"
        )
        littleInt = int.from_bytes(hexstr, byteorder="little")
        bigInt = int.from_bytes(hexstr, byteorder="big")

        vm = VM()
        vm.push(littleInt)
        bitwise.flip_endianness(vm)
        self.assertEqual(vm.stack[0], bigInt)

    def test_set_byte(self):
        origstring = bytearray.fromhex(
            "ada5013122d395ba3c54772283fb069b10426056ef8ca54750cb9bb552a59e7d"
        )
        bigInt = int.from_bytes(origstring, byteorder="big")
        for i in range(32):
            new_val = random.getrandbits(8)
            vm = VM()
            vm.push(new_val)
            vm.push(i)
            vm.push(bigInt)
            bitwise.set_byte(vm)
            finalstring = bytearray(origstring)
            finalstring[i] = new_val
            self.assertEqual(vm.stack[0], int.from_bytes(finalstring, byteorder="big"))

    def test_arithmetic_shift_right(self):
        cases = [(TT256 - 100, 2), (100, 2)]
        for case in cases:
            vm = VM()
            vm.push(case[1])
            vm.push(case[0])
            bitwise.arithmetic_shift_right(vm)
            self.assertEqual(to_signed(case[0]) >> case[1], to_signed(vm.stack[0]))

    def test_right_shift(self):
        cases = [(TT256 - 100, 2), (100, 2)]
        for case in cases:
            vm = VM()
            vm.push(case[1])
            vm.push(case[0])
            bitwise.shift_right(vm)
            self.assertEqual(case[0] >> case[1], vm.stack[0])

    def test_left_shift(self):
        cases = [(TT256 - 100, 2), (100, 2)]
        for case in cases:
            vm = VM()
            vm.push(case[1])
            vm.push(case[0])
            bitwise.shift_left(vm)
            self.assertEqual((case[0] << case[1]) & TT256M1, vm.stack[0])

            vm2 = VM()
            vm2.push(case[1])
            vm2.push(case[0])
            bitwise.shift_left(vm2)
            self.assertEqual(
                to_signed((case[0] << case[1]) & TT256M1), to_signed(vm2.stack[0])
            )
