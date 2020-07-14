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

from ..annotation import modifies_stack
from .. import value


@modifies_stack([value.IntType(), value.IntType()], [value.IntType()])
def lte(vm):
    vm.dup1()
    vm.dup1()
    vm.lt()
    # lt a b
    vm.swap2()
    vm.eq()
    vm.bitwise_or()


@modifies_stack([value.IntType(), value.IntType()], [value.IntType()])
def gte(vm):
    vm.dup1()
    vm.dup1()
    vm.gt()
    # lt a b
    vm.swap2()
    vm.eq()
    vm.bitwise_or()
