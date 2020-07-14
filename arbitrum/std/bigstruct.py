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


# How to use BigStruct:
#
# bsobj = BigStruct(items)
#   where items is a list of items
#       each item is a triple (weight, name, initialValue)
#           weight is the relative frequency of this field being accessed
#               (used to optimize the shape of the resulting tuple tree)
#           name is the name of this field (any hashable type)
#           initialValue is the initial value that this field is
#           supposed to have
#
# bsobj.initialVal
#   is the initial value of the bigstruct, as a tree of Python lists
# bsobj.initialize(vm)
#   generates code that builds the initial value on the stack
# bsobj.get(fieldName, vm)
#   generates code that gets a field by name: [bigstruct] -> [fieldValue]
# bsobj.set_val(fieldName, vm)
#   generates code that sets a field by name:
#       [bigstruct value] -> [updatedBigStruct]

import heapq
from .. import value


def _generate_recipes(structure):
    ret = {}
    for i, item in enumerate(structure):
        ret[item] = [i]
        if isinstance(item, value.Tuple):
            sub_recipes = _generate_recipes(item)
            for (name, rec) in sub_recipes.items():
                ret[name] = [i] + rec
    return ret


def _set_helper(recipe, vm):
    # val tupleTree -> updatedTupleTree
    if len(recipe) == 1:
        vm.swap1()
        vm.tsetn(recipe[0])
    else:
        vm.dup1()
        # tupleTree val tupleTree
        vm.tgetn(recipe[0])
        # subTupleTree val tupleTree
        vm.swap1()
        _set_helper(recipe[1:], vm)
        # updatedSubTupleTree tupleTree
        vm.swap1()
        vm.tsetn(recipe[0])


def _set_static_impl(node, i, recipe, val):
    if i == len(recipe) - 1:
        return node.set_tup_val(recipe[i], val)

    sub_node = node.get_tup(recipe[i])
    sub_node = _set_static_impl(sub_node, i + 1, recipe, val)
    return node.set_tup_val(recipe[i], sub_node)


class BigStruct:
    def __init__(self, items):  # each item is (weight, name, initialValue)
        if not items:
            self.initial_val = value.Tuple([])
            self.recipes = []
        elif len(items) == 1:
            self.initial_val = items[0][2]
            self.recipes = {items[0][1]: []}
        else:
            trees = [(item[0], i, item[1], item[2]) for i, item in enumerate(items)]
            heapq.heapify(trees)
            self.next_nonce = len(trees)
            while len(trees) > 1:
                self._reduce(trees)

            self.structure = trees[0][2]
            self.initial_val = trees[0][3]
            self.recipes = _generate_recipes(self.structure)

    def _reduce(self, trees):
        size = ((len(trees) - 1) % 7) + 1
        if size == 1:
            size = 8
        sum_wt = 0
        lis = []
        initial_val = []
        for _ in range(size):
            item = heapq.heappop(trees)
            sum_wt += item[0]
            lis += [item[2]]
            initial_val += [item[3]]
        new_item = (sum_wt, self.next_nonce, value.Tuple(lis), value.Tuple(initial_val))
        self.next_nonce = self.next_nonce + 1
        heapq.heappush(trees, new_item)

    def initialize(self, vm):
        vm.push(self.initial_val)

    def __contains__(self, field_name):
        return field_name in self.recipes

    def get(self, field_name, vm):  # bigstruct -> fieldVal
        if field_name not in self.recipes:
            raise Exception("Can't find {} in BigStruct".format(field_name))
        recipe = self.recipes[field_name]
        for idx in recipe:
            vm.tgetn(idx)

    def set_static(self, field_name, val):
        recipe = self.recipes[field_name]
        if len(recipe) == 0:
            self.initial_val = val
        else:
            self.initial_val = _set_static_impl(self.initial_val, 0, recipe, val)

    def __getitem__(self, field_name):
        node = self.initial_val
        for idx in self.recipes[field_name]:
            node = node.get_tup(idx)
        return node

    def set_val(self, field_name, vm):  # bigstruct val -> updatedBigstruct
        recipe = self.recipes[field_name]
        if len(recipe) == 0:
            vm.pop()
        elif len(recipe) == 1:
            vm.tsetn(recipe[0])
        else:
            vm.swap1()
            _set_helper(recipe, vm)
