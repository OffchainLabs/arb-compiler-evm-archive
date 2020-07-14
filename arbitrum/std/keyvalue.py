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

import eth_utils

from . import tup
from ..annotation import modifies_stack
from .. import value
from .struct import Struct


def make_keyvalue_type(key_type, value_type, default_val=None):
    keyvalue_type = Struct("keyvalue[{}][{}]".format(key_type, value_type), [])
    if default_val is None:
        default_val = value.Tuple([])

    class KeyValue:
        @staticmethod
        def make():
            return value.Tuple([])

        @staticmethod
        @modifies_stack(0, [keyvalue_type.typ], default_val)
        def new(vm):
            vm.push(KeyValue.make())
            vm.cast(keyvalue_type.typ)

        @staticmethod
        @modifies_stack([keyvalue_type.typ, key_type], [value_type], default_val)
        def get(vm):
            # kvs key
            vm.swap1()
            vm.hash()
            vm.swap1()
            # kvs keyhash
            vm.cast(value.TupleType())

            vm.while_loop(
                lambda vm: [vm.dup0(), vm.tlen(), vm.push(8), vm.eq()],
                lambda vm: [
                    vm.cast(value.TupleType(8)),
                    # kvs keyhash
                    vm.push(8),
                    vm.dup2(),
                    vm.mod(),
                    # keyhash%8 kvs keyhash
                    vm.tget(),
                    # subkvs keyhash
                    vm.swap1(),
                    vm.push(8),
                    vm.swap1(),
                    vm.div(),
                    vm.swap1(),
                ],
            )

            vm.dup0()
            vm.tnewn(0)
            vm.eq()
            vm.ifelse(
                lambda vm: [vm.pop(), vm.pop(), vm.push(default_val)],
                lambda vm: [
                    # kvs keyhash
                    vm.cast(value.TupleType(3)),
                    vm.swap1(),
                    vm.dup1(),
                    vm.tgetn(0),
                    # tupkeyhash keyhash kvs
                    vm.eq(),
                    vm.ifelse(
                        lambda vm: [
                            # kvs
                            vm.tgetn(2)
                        ],
                        lambda vm: [
                            # kvs
                            vm.pop(),
                            vm.push(default_val),
                        ],
                    ),
                ],
            )
            vm.cast(value_type)

        @staticmethod
        @modifies_stack(
            [keyvalue_type.typ, key_type, value_type], [keyvalue_type.typ], default_val
        )
        def set_val(vm):
            # kvs key value
            vm.cast(value.TupleType())
            vm.dup2()
            vm.dup2()
            # key value kvs key value
            vm.dup0()
            vm.hash()
            # hash(key) key value kvs key value
            tup.make(3)(vm)
            # [hash(key) key value] kvs key value
            vm.swap1()
            KeyValue._set_impl(vm)
            vm.cast(keyvalue_type.typ)
            # newkvs key value
            vm.swap2()
            vm.pop()
            vm.pop()
            # newkvs

        @staticmethod
        def get_static(kvs, key):
            return KeyValue._get_static_impl(
                kvs, eth_utils.big_endian_to_int(value.value_hash(key))
            )

        @staticmethod
        def set_static(kvs, key, val):
            update = value.Tuple(
                [eth_utils.big_endian_to_int(value.value_hash(key)), key, val]
            )
            return KeyValue._set_impl_static(kvs, update)

        @staticmethod
        def _get_static_impl(kvs, key):
            while len(kvs) == 8:
                kvs = kvs[key % 8]
                key //= 8

            if not kvs:
                return default_val

            if kvs[0] == key:
                return kvs[2]

            return default_val

        @staticmethod
        @modifies_stack(
            [
                value.TupleType(),
                value.TupleType(
                    [value.IntType(), value.ValueType(), value.ValueType()]
                ),
            ],
            [value.TupleType()],
            default_val,
        )
        def _set_impl(vm):
            # kvs [hash(key) key value]
            vm.dup0()
            vm.tlen()
            # len(kvs) kvs [...]
            vm.dup0()
            vm.ifelse(
                lambda vm: [
                    # len(kvs) kvs [...]
                    vm.push(3),
                    vm.eq(),
                    # len(kvs)==3 kvs [...]
                    vm.ifelse(
                        lambda vm: [
                            vm.cast(
                                value.TupleType(
                                    [
                                        value.IntType(),
                                        value.ValueType(),
                                        value.ValueType(),
                                    ]
                                )
                            ),
                            # [oldhash oldkey oldval] [newhash newkey newval]
                            vm.dup1(),
                            vm.tgetn(1),
                            # newkey [oldhash oldkey oldval] [newhash newkey newval]
                            vm.dup1(),
                            vm.tgetn(1),
                            vm.eq(),
                            # oldkey==newkey [old...] [new...]
                            vm.ifelse(
                                lambda vm: [
                                    vm.pop(),
                                    # [newhash newkey newval]
                                ],
                                lambda vm: [
                                    vm.tnewn(8),
                                    # empty8tuple [old...] [new...]
                                    KeyValue._set_impl(vm),
                                    KeyValue._set_impl(vm),
                                ],
                            ),
                        ],
                        lambda vm: [
                            # kvs is full 8-tuple
                            # kvstuple [newhash newkey newval]
                            vm.cast(value.TupleType(8)),
                            vm.swap1(),
                            vm.dup0(),
                            vm.tgetn(0),
                            # newhash [newhash newkey newval] kvstuple
                            vm.push(8),
                            vm.dup1(),
                            vm.div(),
                            # newhash/8 newhash [new...] kvstuple
                            vm.swap1(),
                            vm.push(8),
                            vm.swap1(),
                            vm.mod(),
                            # newhash%8 newhash/8 [new...] kvstuple
                            vm.swap2(),
                            # [new...] newhash/8 newhash%8 kvstuple
                            vm.tsetn(0),
                            # subtriple newhash%8 kvstuple
                            vm.dup2(),
                            vm.dup2(),
                            # newhash%8 kvstuple subtriple newhash%8 kvstuple
                            vm.tget(),
                            vm.cast(
                                value.TupleType(
                                    [
                                        value.IntType(),
                                        value.ValueType(),
                                        value.ValueType(),
                                    ]
                                )
                            ),
                            # subkvs subtriple newhash%8 kvstuple
                            KeyValue._set_impl(vm),
                            # newsubkvs newhash%8 kvstuple
                            vm.swap2(),
                            vm.swap1(),
                            # newhash%8 kvstuple newsubkvs
                            vm.tset(),
                        ],
                    ),
                ],
                lambda vm: [
                    # len(kvs) None [hash(key) key value]
                    vm.pop(),
                    vm.pop(),
                ],
            )

        @staticmethod
        def _set_impl_static(kvs, update):
            if kvs == value.Tuple([]):
                return update

            if len(kvs) == 3:
                if kvs[1] == update[1]:
                    return update

                new_kvs = value.Tuple([value.Tuple([])] * 8)
                new_kvs = KeyValue._set_impl_static(new_kvs, kvs)
                return KeyValue._set_impl_static(new_kvs, update)

            return kvs.set_tup_val(
                update[0] % 8,
                KeyValue._set_impl_static(
                    kvs[update[0] % 8], update.set_tup_val(0, update[0] // 8)
                ),
            )

    KeyValue.typ = keyvalue_type.typ
    return KeyValue


keyvalue = make_keyvalue_type(value.ValueType(), value.ValueType())
keyvalue_int_int = make_keyvalue_type(value.IntType(), value.IntType(), 0)
