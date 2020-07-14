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


# Credit to https://github.com/ethereum/pyethereum/blob/master/ethereum/vm.py
# for EVM-like implementation details

from eth_utils import big_endian_to_int, keccak
from eth_abi.packed import encode_single_packed
from . import instructions
from .ast import AVMLabeledCodePoint
from . import value

TT256 = 2 ** 256
TT256M1 = 2 ** 256 - 1
TT255 = 2 ** 255


def to_signed(i):
    return i if i < TT255 else i - TT256


class VMBlocked(Exception):
    """VM tried to run opcode that blocks"""

    pass


class VMBlockedAdvance(Exception):
    """VM tried to run opcode that blocks"""

    pass


class VMEnv:
    def __init__(self):
        self.messages = value.Tuple([])
        self.pending_messages = value.Tuple([])
        self.time_bounds = value.Tuple([0, 100000000, 453, 73657336])


class Stack:
    def __init__(self, items=None):
        if items is None:
            items = []
        self.items = items

    def __len__(self):
        return len(self.items)

    def __getitem__(self, *args):
        return self.items.__getitem__(*args)

    def push(self, val):
        self.items.insert(0, val)

    def pop(self, typehint=None):
        val = self.items[0]
        if typehint and not typehint.accepts(val):
            raise Exception("Pop expected {}, but got {}".format(typehint, val))
        del self.items[0]
        return val

    def peak(self):
        return self.items[0]


class BasicVM:
    def __init__(self):
        self.pc = value.ERROR_CODE_POINT
        self.stack = Stack()
        self.aux_stack = Stack()
        self.register = value.Tuple([])
        self.static = value.Tuple([])
        self.arb_gas_remaining = (1 << 256) - 1
        self.err_handler = None

        self.env = VMEnv()
        self.halted = False
        self.sent_messages = []
        self.logs = []

    def log(self):
        self.logs.append(self.stack.pop())

    def breakpoint(self):
        raise VMBlockedAdvance()

    def debug(self):
        print("Debug", self.stack[:])
        # print("get", len(self.stack[0]), self.stack[1])
        # print("Debug:\nStack:", self.stack[:], "\nAux:", self.aux_stack[:])

    def push(self, val):
        if isinstance(val, list):
            self.stack.push(value.Tuple(val))
        else:
            self.stack.push(val)

    def inbox(self):
        if self.env.messages == value.Tuple([]):
            raise VMBlocked()

        self.stack.push(self.env.messages)
        self.env.messages = value.Tuple([])

    def send(self):
        msg = self.stack.pop()
        self.sent_messages.append(msg)

    def auxpush(self):
        item = self.stack.pop()
        self.aux_stack.push(item)

    def auxpop(self):
        item = self.aux_stack.pop()
        self.stack.push(item)

    def jump(self):
        dest = self.stack.pop()
        # if isinstance(dest, AVMLabeledCodePoint):
        #     print("Jumping to", dest)
        if isinstance(dest, value.AVMCodePoint):
            pc = dest
        elif isinstance(dest, AVMLabeledCodePoint):
            pc = dest.pc
        else:
            raise Exception("Jump insn requires codepoint but recieved " + str(dest))
        self.pc = pc

    def errpush(self):
        self.stack.push(self.err_handler)

    def errset(self):
        err_handler = self.stack.pop()
        if isinstance(err_handler, value.AVMCodePoint):
            pc = err_handler
        elif isinstance(err_handler, AVMLabeledCodePoint):
            pc = err_handler.pc

        self.err_handler = pc

    def error(self):
        raise Exception("Error opcode called")

    def cjump(self):
        dest = self.stack.pop()
        cond = self.stack.pop()

        if isinstance(dest, value.AVMCodePoint):
            pass
        elif isinstance(dest, AVMLabeledCodePoint):
            dest = dest.pc
        else:
            print("Conditional jumping to {}".format(dest.name))
            raise Exception("Cjump insn requires codepoint but recieved " + str(dest))

        if cond != 0:
            self.pc = dest

    def swap1(self):
        instructions.swap1(self.stack)

    def swap2(self):
        instructions.swap2(self.stack)

    def dup0(self):
        instructions.dup0(self.stack)

    def dup1(self):
        instructions.dup1(self.stack)

    def dup2(self):
        instructions.dup2(self.stack)

    def tlen(self):
        instructions.tlen(self.stack)

    def tset(self):
        instructions.tset(self.stack)

    def tget(self):
        instructions.tget(self.stack)

    def xset(self):
        index = self.stack.pop(value.IntType())
        val = self.stack.pop(value.ValueType())
        tup = self.aux_stack.pop(value.TupleType())
        self.aux_stack.push(tup.set_tup_val(index, val))

    def xget(self):
        index = self.stack.pop(value.IntType())
        tup = self.aux_stack.pop(value.TupleType())
        if not tup.has_member_at_index(index):
            raise Exception("Tried to get index {} from tuple {}".format(index, tup))
        self.aux_stack.push(tup)
        self.stack.push(tup.get_tup(index))

    def type(self):
        item = self.stack.pop()
        if isinstance(item, int):
            self.stack.push(0)
        elif isinstance(item, value.Tuple):
            self.stack.push(3)
        else:
            self.stack.push(1)

    def spush(self):
        self.stack.push(self.static)

    def rpush(self):
        self.stack.push(self.register)

    def rset(self):
        self.register = self.stack.pop()

    def add(self):
        op1 = self.stack.pop()
        op2 = self.stack.pop()
        self.stack.push((op1 + op2) & TT256M1)

    def sub(self):
        op1 = self.stack.pop()
        op2 = self.stack.pop()
        self.stack.push((op1 - op2) & TT256M1)

    def mul(self):
        op1 = self.stack.pop()
        op2 = self.stack.pop()
        self.stack.push((op1 * op2) & TT256M1)

    def div(self):
        op1 = self.stack.pop()
        op2 = self.stack.pop()
        if op2 != 0:
            try:
                self.push(op1 // op2)
            except Exception:
                print(op1)
                print(op2)
                raise
        else:
            raise Exception("Can't divide by zero")

    def sdiv(self):
        op1 = self.stack.pop()
        op2 = self.stack.pop()
        s0, s1 = to_signed(op1), to_signed(op2)
        if s1 != 0:
            self.stack.push((abs(s0) // abs(s1) * (-1 if s0 * s1 < 0 else 1)) & TT256M1)
        else:
            raise Exception("Can't divide by zero")

    def mod(self):
        op1 = self.stack.pop()
        op2 = self.stack.pop()
        if op2 != 0:
            self.stack.push(op1 % op2)
        else:
            raise Exception("Can't mod by zero")

    def smod(self):
        op1 = self.stack.pop()
        op2 = self.stack.pop()
        s0, s1 = to_signed(op1), to_signed(op2)
        if s1 == 0:
            self.stack.push((abs(s0) % abs(s1) * (-1 if s0 < 0 else 1)) & TT256M1)
        else:
            raise Exception("Can't mod by zero")

    def exp(self):
        op1 = self.stack.pop()
        op2 = self.stack.pop()
        self.stack.push(pow(op1, op2, TT256))

    def addmod(self):
        op1 = self.stack.pop()
        op2 = self.stack.pop()
        op3 = self.stack.pop()
        self.stack.push((op1 + op2) % op3 if op3 else 0)

    def mulmod(self):
        op1 = self.stack.pop()
        op2 = self.stack.pop()
        op3 = self.stack.pop()
        self.stack.push((op1 * op2) % op3 if op3 else 0)

    def signextend(self):
        op1 = self.stack.pop()
        op2 = self.stack.pop()
        if op1 <= 31:
            testbit = op1 * 8 + 7
            if op2 & (1 << testbit):
                self.stack.push(op2 | (TT256 - (1 << testbit)))
            else:
                self.stack.push(op2 & ((1 << testbit) - 1))
        else:
            self.stack.push(op2)

    def stackempty(self):
        self.stack.push(int(len(self.stack) == 0))

    def auxstackempty(self):
        self.stack.push(int(len(self.aux_stack) == 0))

    def nop(self):
        pass

    def pop(self):
        self.stack.pop()

    def pcpush(self):
        self.stack.push(self.pc)

    def halt(self):
        raise Exception("Machine halted improperly")
        self.halted = True

    def eq(self):
        op1 = self.stack.pop()
        op2 = self.stack.pop()
        self.stack.push(int(op1 == op2))

    def iszero(self):
        op = self.stack.pop()
        self.stack.push(int(op == 0))

    def lt(self):
        op1 = self.stack.pop()
        op2 = self.stack.pop()
        self.stack.push(int(op1 < op2))

    def gt(self):
        op1 = self.stack.pop()
        op2 = self.stack.pop()
        self.stack.push(int(op1 > op2))

    def slt(self):
        op1 = self.stack.pop()
        op2 = self.stack.pop()
        s0, s1 = to_signed(op1), to_signed(op2)
        self.stack.push(1 if s0 < s1 else 0)

    def sgt(self):
        op1 = self.stack.pop()
        op2 = self.stack.pop()
        s0, s1 = to_signed(op1), to_signed(op2)
        self.stack.push(1 if s0 > s1 else 0)

    def hash(self):
        op = self.stack.pop()
        self.stack.push(big_endian_to_int(value.value_hash(op)))

    def ethhash2(self):
        op1 = self.stack.pop()
        op2 = self.stack.pop()
        res = keccak(encode_single_packed("(uint256,uint256)", [op1, op2]))
        self.stack.push(big_endian_to_int(res))

    def ecrecover(self):
        self.stack.push(0)
        print("ecrecover does not yet support native python execution")
        exit()

    def bitwise_and(self):
        op1 = self.stack.pop()
        op2 = self.stack.pop()
        self.stack.push(op1 & op2)

    def bitwise_or(self):
        op1 = self.stack.pop()
        op2 = self.stack.pop()
        self.stack.push(op1 | op2)

    def bitwise_xor(self):
        op1 = self.stack.pop()
        op2 = self.stack.pop()
        self.stack.push(op1 ^ op2)

    def bitwise_not(self):
        op1 = self.stack.pop()
        self.stack.push(TT256M1 - op1)

    def byte(self):
        op1 = self.stack.pop()
        op2 = self.stack.pop()
        if op1 >= 32:
            self.stack.push(0)
        else:
            self.stack.push((op2 // 256 ** (31 - op1)) % 256)

    def setgas(self):
        gas = self.stack.pop()
        self.arb_gas_remaining = gas

    def pushgas(self):
        self.stack.push(self.arb_gas_remaining)

    def errcodepoint(self):
        raise Exception("not implemented")

    def pushinsn(self):
        raise Exception("not implemented")

    def pushinsnimm(self):
        raise Exception("not implemented")

    def sideload(self):
        raise Exception("not implemented")

    def cast(self, typ):
        pass
        # if not typ.accepts_cast(self.stack[0]):
        #     raise Exception("Tried to perform incorrect cast of {} to {}".format(self.stack[0], typ))
