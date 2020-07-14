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

from .annotation import modifies_stack
from .ast import ImmediateOp, AVMLabeledCodePoint
from . import value
from .basic_vm import VMBlocked, VMBlockedAdvance
import traceback


# [val]
@modifies_stack(1, 1)
def is_zero(vm):
    vm.push(0)
    vm.eq()


class InstructionOutOfBounds(Exception):
    """VM tried to run opcode that blocks"""

    pass


def run_vm_once(vm):
    if vm.halted:
        raise Exception("Can't run VM since it is halted")
    if vm.pc.pc == -2:
        raise Exception("VM hit unhandled error")
    instr = vm.pc.op
    old_pc = vm.pc

    try:
        if isinstance(instr, ImmediateOp):
            vm.push(instr.val)
            vm.ops[instr.op.op_code]()
        elif isinstance(instr, int):
            vm.ops[instr]()
        else:
            vm.ops[instr.op_code]()

        # We only incremement the PC if the operation has not
        # otherwise modified the PC (JUMP, CJUMP)
        if vm.pc.pc == old_pc.pc:
            next_pc = vm.pc.pc + 1
        else:
            next_pc = vm.pc.pc

        if next_pc >= len(vm.code):
            raise InstructionOutOfBounds()

    except VMBlocked:
        return False
    except VMBlockedAdvance:
        vm.pc = vm.code[vm.pc.pc + 1]
        return False
    except Exception as err:
        print(
            "Hit exception {}({}) while running {}, path={}".format(
                err, type(err), vm.pc, vm.pc.path
            )
        )
        traceback.print_tb(err.__traceback__)
        exit()
        if isinstance(vm.err_handler, value.CodePointType):
            vm.pc = vm.err_handler
        elif isinstance(vm.err_handler, AVMLabeledCodePoint):
            vm.pc = vm.err_handler.pc
        elif isinstance(vm.err_handler, value.AVMCodePoint):
            vm.pc = vm.err_handler
        else:
            print("Error handler", vm.err_handler)
            raise

    if vm.pc.pc == old_pc.pc:
        vm.pc = vm.code[vm.pc.pc + 1]

    return True
