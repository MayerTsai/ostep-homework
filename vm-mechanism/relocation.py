#! /usr/bin/env python

import sys
import argparse
import random
import time

UNITS = {"k": 1024, "m": 1024 * 1024, "g": 1024 * 1024 * 1024}


def convert(size):
    """Converts strings like '1k', '4m' to integer byte counts."""
    size = str(size)
    try:
        if not size:
            return 0
        if size[-1].lower() in UNITS:
            return int(size[:-1]) * UNITS[size[-1].lower()]
        return int(float(size))
    except ValueError:
        return 0


#
# main program
#
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-a",
        "--asize",
        default="1k",
        help="address space size (e.g., 16, 64k, 32m, 1g)",
        type=str,
    )
    parser.add_argument(
        "-p",
        "--physmem",
        default="16k",
        help="physical memory size (e.g., 16, 64k, 32m, 1g)",
        type=str,
        dest="psize",
    )
    parser.add_argument(
        "-n",
        "--addresses",
        default=5,
        help="number of virtual addresses to generate",
        type=int,
        dest="num",
    )
    parser.add_argument(
        "-b",
        "--base",
        default="-1",
        help="value of base register",
        type=str,
        dest="base",
    )
    parser.add_argument(
        "-l",
        "--limit",
        default="-1",
        help="value of limit register",
        type=str,
        dest="limit",
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
    seed = int(time.time())
    print(f"ARG seed {seed}")
    print(f"ARG address space size {args.asize}")
    print(f"ARG phys mem size {args.psize}\n")

    asize = convert(args.asize)
    psize = convert(args.psize)

    if psize <= 1:
        print("Error: must specify a non-zero physical memory size.")
        sys.exit(1)

    if asize == 0:
        print("Error: must specify a non-zero address-space size.")
        sys.exit(1)

    if psize <= asize:
        print(
            "Error: physical memory size must be GREATER than address space size (for this simulation)"
        )
        sys.exit(1)

    #
    # need to generate base, bounds for segment registers
    #
    limit = convert(args.limit)
    base = convert(args.base)
    random.seed(seed)

    if limit == -1:
        limit = int(asize / 4.0 + (asize / 4.0 * random.random()))

    if base == -1:
        # Direct calculation is more efficient than a while loop
        base = random.randint(0, psize - limit)

    print("Base-and-Bounds register information:\n")
    print(f"  Base   : 0x{base:08x} (decimal {base})")
    print(f"  Limit  : {limit}\n")

    if base + limit > psize:
        print(
            "Error: address space does not fit into physical memory with those base/bounds values."
        )
        print(f"Base + Limit: {base + limit}  Psize: {psize}")
        sys.exit(1)

    #
    # now, need to generate virtual address trace
    #
    print("Virtual Address Trace")
    for i in range(args.num):
        vaddr = random.randrange(asize)
        if not args.solve:
            print(
                f"  VA {i:2d}: 0x{vaddr:08x} (decimal: {vaddr:4d}) --> PA or segmentation violation?"
            )
        else:
            if vaddr >= limit:
                print(
                    f"  VA {i:2d}: 0x{vaddr:08x} (decimal: {vaddr:4d}) --> SEGMENTATION VIOLATION"
                )
            else:
                paddr = vaddr + base
                print(
                    f"  VA {i:2d}: 0x{vaddr:08x} (decimal: {vaddr:4d}) --> VALID: 0x{paddr:08x} (decimal: {paddr:4d})"
                )

    print("")

    if not args.solve:
        print(
            "For each virtual address, either write down the physical address it translates to"
        )
        print(
            "OR write down that it is an out-of-bounds address (a segmentation violation). For"
        )
        print(
            "this problem, you should assume a simple virtual address space of a given size."
        )
        print("")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
