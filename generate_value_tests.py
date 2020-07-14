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

import io
import json
import random

from arbitrum import value, marshall, ast

if __name__ == "__main__":
    cases = []

    random.seed(143235)

    def add_case(val, name, is_codepoint=None):
        if is_codepoint is None:
            is_codepoint = False
        data = io.BytesIO()
        marshall.marshall_value(val, data)
        proof_data = io.BytesIO()
        marshall.marshall_value(val, proof_data)
        cases.append(
            {
                "value": data.getvalue().hex(),
                "proof_value": proof_data.getvalue().hex(),
                "hash": value.value_hash(val).hex(),
                "name": name,
                "is_codepoint": is_codepoint,
            }
        )

    simple_tup = value.Tuple([5, 2, 6])
    nest1_tup = value.Tuple([5, simple_tup, 6, simple_tup])
    add_case(10, "int")
    next_hash = bytearray(random.getrandbits(8) for _ in range(32))
    basic = value.AVMCodePoint(0, ast.BasicOp(8), next_hash)
    immediate = value.AVMCodePoint(
        0, ast.ImmediateOp(ast.BasicOp(8), simple_tup), next_hash
    )
    add_case(basic, "simple codepoint", True)
    add_case(immediate, "immediate codepoint", True)
    for i in range(9):
        add_case(value.Tuple([0] * i), "tup" + str(i))
    add_case(simple_tup, "simple_tup")
    add_case(nest1_tup, "nested_tup")
    add_case(
        value.Tuple([nest1_tup, simple_tup, nest1_tup, simple_tup]), "double_nested_tup"
    )
    with open("test_cases.json", "w") as f:
        json.dump(cases, f, indent=4)

    locations = [
        "../arb-bridge-eth/test/test_cases.json",
        "../arb-avm-cpp/tests/test_cases.json",
        "../arb-util/value/test_cases.json",
        "../arb-provider-ethers/test/test_cases.json",
    ]
    for loc in locations:
        with open(loc, "w") as f:
            json.dump(cases, f, indent=4)
