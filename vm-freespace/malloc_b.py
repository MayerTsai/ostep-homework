#! /usr/bin/python3

import random
import sys
import argparse
import time
import bisect


def abort(message):
    print(f"Error: {message}", file=sys.stderr)
    sys.exit(1)


class malloc:
    def __init__(self, size, start, headerSize, policy, order, coalesce, align):
        # size of space
        self.size = size

        # info about pretend headers
        self.headerSize = headerSize

        # init free list
        self.freelist = []
        self.freelist.append((start, size))

        # keep track of ptr to size mappings
        self.sizemap = {}

        # policy
        self.policy = policy
        assert self.policy in ["FIRST", "BEST", "WORST"]

        # list ordering
        self.returnPolicy = order
        assert self.returnPolicy in [
            "ADDRSORT",
            "SIZESORT+",
            "SIZESORT-",
            "INSERT-FRONT",
            "INSERT-BACK",
        ]

        # this does a ridiculous full-list coalesce, but that is ok
        self.coalesce = coalesce

        # alignment (-1 if no alignment)
        self.align = align
        assert self.align == -1 or self.align > 0

    def addToMap(self, addr, size):
        assert addr not in self.sizemap
        self.sizemap[addr] = size
        # print('adding', addr, 'to map of size', size)

    def malloc(self, size):
        if size <= 0:
            raise ValueError("Size must be a positive integer")

        if self.align != -1:
            size += (self.align - (size % self.align)) % self.align

        size += self.headerSize

        bestIdx = -1
        bestSize = float("inf") if self.policy == "BEST" else float("-inf")
        bestAddr = -1
        count = 0

        # Optimization: Move policy check out of the hot loop to avoid redundant string comparisons
        if self.policy == "FIRST":
            for i, (eaddr, esize) in enumerate(self.freelist):
                count += 1
                if esize >= size:
                    bestAddr, bestSize, bestIdx = eaddr, esize, i
                    break
        elif self.policy == "BEST":
            for i, (eaddr, esize) in enumerate(self.freelist):
                count += 1
                if esize >= size and esize < bestSize:
                    bestAddr, bestSize, bestIdx = eaddr, esize, i
        elif self.policy == "WORST":
            for i, (eaddr, esize) in enumerate(self.freelist):
                count += 1
                if esize >= size and esize > bestSize:
                    bestAddr, bestSize, bestIdx = eaddr, esize, i

        if bestIdx != -1:
            self.addToMap(bestAddr, size)
            if bestSize > size:
                self.freelist[bestIdx] = (bestAddr + size, bestSize - size)
            else:
                # PERFECT MATCH (no split)
                self.freelist.pop(bestIdx)
            return (bestAddr, count)

        return (-1, count)

    def free(self, addr):
        # simple back on end of list, no coalesce
        if addr not in self.sizemap:
            return -1

        size = self.sizemap[addr]
        new_entry = (addr, size)

        if self.returnPolicy == "INSERT-BACK":
            self.freelist.append(new_entry)
        elif self.returnPolicy == "INSERT-FRONT":
            self.freelist.insert(0, new_entry)
        elif self.returnPolicy == "ADDRSORT":
            # Use bisect to insert in sorted order, more efficient than full sort
            bisect.insort_left(self.freelist, new_entry)
        elif self.returnPolicy == "SIZESORT+":
            # For SIZESORT, a full sort after appending is simpler
            # than bisect with a custom key, but less efficient.
            self.freelist.append(new_entry)
            self.freelist.sort(key=lambda e: e[1])
        elif self.returnPolicy == "SIZESORT-":
            self.freelist.append(new_entry)
            self.freelist.sort(key=lambda e: e[1], reverse=True)

        # not meant to be an efficient or realistic coalescing...
        if self.coalesce:
            if not self.freelist:
                return 0
            newlist = []
            curr_addr, curr_size = self.freelist[0]
            for next_addr, next_size in self.freelist[1:]:
                if next_addr == (curr_addr + curr_size):
                    curr_size += next_size
                else:
                    newlist.append((curr_addr, curr_size))
                    curr_addr, curr_size = next_addr, next_size
            newlist.append((curr_addr, curr_size))
            self.freelist = newlist

        del self.sizemap[addr]
        return 0

    def dump(self):
        print(f"Free List [ Size {len(self.freelist)} ]: ", end="")
        for e in self.freelist:
            print(f"[ addr:{e[0]} sz:{e[1]} ]", end="")
        print("")


#
# main program
#
parser = argparse.ArgumentParser()

parser.add_argument(
    "-S",
    "--size",
    default=100,
    help="size of the heap",
    action="store",
    type=int,
    dest="heapSize",
)
parser.add_argument(
    "-b",
    "--baseAddr",
    default=1000,
    help="base address of heap",
    action="store",
    type=int,
    dest="baseAddr",
)
parser.add_argument(
    "-H",
    "--headerSize",
    default=0,
    help="size of the header",
    action="store",
    type=int,
    dest="headerSize",
)
parser.add_argument(
    "-a",
    "--alignment",
    default=-1,
    help="align allocated units to size; -1->no align",
    action="store",
    type=int,
    dest="alignment",
)
parser.add_argument(
    "-p",
    "--policy",
    default="BEST",
    help="list search (BEST, WORST, FIRST)",
    action="store",
    type=str,
    dest="policy",
)
parser.add_argument(
    "-l",
    "--listOrder",
    default="ADDRSORT",
    help="list order (ADDRSORT, SIZESORT+, SIZESORT-, INSERT-FRONT, INSERT-BACK)",
    action="store",
    type=str,
    dest="order",
)
parser.add_argument(
    "-s",
    "--seed",
    default=0,
    help="the random seed",
    action="store",
    type=int,
    dest="seed",
)
parser.add_argument(
    "-C",
    "--coalesce",
    default=False,
    help="coalesce the free list?",
    action="store_true",
    dest="coalesce",
)
parser.add_argument(
    "-n",
    "--numOps",
    default=10,
    help="number of random ops to generate",
    action="store",
    type=int,
    dest="opsNum",
)
parser.add_argument(
    "-r",
    "--range",
    default=10,
    help="max alloc size",
    action="store",
    type=int,
    dest="opsRange",
)
parser.add_argument(
    "-P",
    "--percentAlloc",
    default=50,
    help="percent of ops that are allocs",
    action="store",
    type=int,
    dest="opsPAlloc",
)
parser.add_argument(
    "-A",
    "--allocList",
    default="",
    help="instead of random, list of ops (+10,-0,etc)",
    action="store",
    type=str,
    dest="opsList",
)
parser.add_argument(
    "-c",
    "--compute",
    default=False,
    help="compute answers for me",
    action="store_true",
    dest="solve",
)

args = parser.parse_args()

m = malloc(
    args.heapSize,
    args.baseAddr,
    args.headerSize,
    args.policy,
    args.order,
    args.coalesce,
    args.alignment,
)

print(f"size {args.heapSize}")
print(f"baseAddr {args.baseAddr}")
print(f"headerSize {args.headerSize}")
print(f"alignment {args.alignment}")
print(f"policy {args.policy}")
print(f"listOrder {args.order}")
print(f"coalesce {args.coalesce}")
print(f"numOps {args.opsNum}")
print(f"range {args.opsRange}")
print(f"percentAlloc {args.opsPAlloc}")
print(f"allocList {args.opsList}")
print(f"compute {args.solve}")
print("")

percent = args.opsPAlloc / 100.0
assert percent > 0

seed = args.seed if args.seed != 0 else int(time.time())
random.seed(seed)  # Use the provided seed for reproducibility
L = []
p = {}


if args.opsList == "":
    c = 0
    j = 0
    while j < args.opsNum:
        pr = False
        if random.random() < percent:
            size = random.randint(1, args.opsRange)
            ptr, cnt = m.malloc(size)
            if ptr != -1:
                p[c] = ptr
                L.append(c)

            print(f"ptr[{c}] = Alloc({size})", end="")
            if args.solve:
                print(f" returned {ptr + args.headerSize} (searched {cnt} elements)")
            else:
                print(" returned ?")

            c += 1
            j += 1
            pr = True
        else:
            if p:
                # pick random one to delete
                target_ptr_id = L.pop(random.randrange(len(L)))
                rc = m.free(p.pop(target_ptr_id))
                print(f"Free(ptr[{target_ptr_id}])", end="")
                if args.solve:
                    print(f" returned {rc}")
                else:
                    print(" returned ?")
                pr = True
                j += 1
        if pr:
            if args.solve:
                m.dump()
            else:
                print("List? ")
            print("")
else:
    c = 0
    for op in args.opsList.split(","):
        if op[0] == "+":
            # allocation!
            size = int(op.split("+")[1])
            ptr, cnt = m.malloc(size)
            if ptr != -1:
                p[c] = ptr
            print(f"ptr[{c}] = Alloc({size})", end="")

            if args.solve:
                print(f" returned {ptr} (searched {cnt} elements)")
            else:
                print(" returned ?")

            c += 1
        elif op[0] == "-":
            # free
            index = int(op.split("-")[1])
            if index not in p:
                print("Invalid Free: Skipping")
                continue
            print(f"Free(ptr[{index}])", end="")
            rc = m.free(p.pop(index))

            if args.solve:
                print(f" returned {rc}")
            else:
                print(" returned ?")

        else:
            abort("Badly specified operand: must be +Size or -Index")

        if args.solve:
            m.dump()
        else:
            print("List?")

        print("")
