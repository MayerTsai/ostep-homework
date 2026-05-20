#! /usr/bin/python3

import sys
import collections
import random
import argparse
import time


# Helper function to print victim page number or '-' if no victim
def vfunc(victim):
    if victim == -1:
        return "-"
    else:
        return str(victim)


parser = argparse.ArgumentParser(description="Simulate page replacement policies.")
parser.add_argument(
    "-a",
    "--addresses",
    default="-1",
    help="A set of comma-separated pages to access; -1 means randomly generate.",
    type=str,
)
parser.add_argument(
    "-f",
    "--addressfile",
    default="",
    help="A file with a bunch of addresses in it.",
    type=str,
)
parser.add_argument(
    "-n",
    "--numaddrs",
    default="10",
    help="If -a (--addresses) is -1, this is the number of addrs to generate.",
    type=int,
)
parser.add_argument(
    "-p",
    "--policy",
    default="FIFO",
    help="Replacement policy: FIFO, LRU, OPT, UNOPT, RAND, CLOCK.",
    type=str,
)
parser.add_argument(
    "-b",
    "--clockbits",
    default=2,
    help="For CLOCK policy, how many clock bits to use.",
    type=int,
)
parser.add_argument(
    "-C", "--cachesize", default="3", help="Size of the page cache, in pages.", type=int
)  # Changed type to int
parser.add_argument(
    "-m",
    "--maxpage",
    default="10",
    help="If randomly generating page accesses, this is the max page number.",
    type=int,
)
parser.add_argument("-s", "--seed", default=0, help="Random number seed.", type=int)
parser.add_argument(
    "-N",
    "--notrace",
    default=False,
    help="Do not print out a detailed trace.",
    action="store_true",
)
parser.add_argument(
    "-c",
    "--compute",
    default=False,
    help="Compute answers for me.",
    action="store_true",
)

args = parser.parse_args()

print("ARG addresses", args.addresses)
print("ARG addressfile", args.addressfile)
print("ARG numaddrs", args.numaddrs)
print("ARG policy", args.policy)
print("ARG clockbits", args.clockbits)
print("ARG cachesize", args.cachesize)
print("ARG maxpage", args.maxpage)
print("ARG seed", args.seed)
print("ARG notrace", args.notrace)
print("")

# Convert string arguments to appropriate types
addresses = args.addresses
addressFile = args.addressfile
numaddrs = args.numaddrs
cachesize = args.cachesize
maxpage = args.maxpage
policy = args.policy
notrace = args.notrace
clockbits = args.clockbits

seed = args.seed if args.seed != 0 else int(time.time())
random.seed(seed)

policy_map = {
    "FIFO": ("FirstIn", "Lastin "),
    "LRU": ("LRU", "MRU"),
    "MRU": ("LRU", "MRU"),
    "CLOCK": ("LRU", "MRU"),
    "OPT": ("Left ", "Right"),
    "RAND": ("Left ", "Right"),
    "UNOPT": ("Left ", "Right"),
}

if policy not in policy_map:
    print(f"Policy {policy} is not yet implemented")
    sys.exit(1)

addrList = []
if addressFile != "":
    with open(addressFile) as fd:
        for line in fd:
            addrList.append(int(line))
else:
    if addresses == "-1":
        for i in range(0, numaddrs):
            addrList.append(random.randrange(maxpage))
    else:
        addrList = [int(x) for x in addresses.split(",")]

if not args.compute:
    print(
        f"Assuming a replacement policy of {policy}, and a cache of size {cachesize} pages,"
    )
    print("figure out whether each of the following page references hit or miss")
    print("in the page cache.\n")

    for n_val in addrList:
        print(f"Access: {n_val}  Hit/Miss?  State of Memory?")
    print("")
    sys.exit(0)


if not args.notrace:
    print("Solving...\n")

# Pre-calculate page occurrences for OPT/UNOPT to optimize lookups from O(N) to O(1)
occurrences = collections.defaultdict(collections.deque)
if policy in ["OPT", "UNOPT"]:
    for i, addr in enumerate(addrList):
        occurrences[addr].append(i)
    opt_func = max if policy == "OPT" else min

# Initialize simulation state.
memory = []
is_ordered_policy = policy in ["LRU", "FIFO", "MRU"]
memory_ordered = collections.OrderedDict() if is_ordered_policy else None
mem_set = set()
hits = 0
miss = 0
ref = {}
clock_hand = 0


leftStr, riteStr = policy_map[policy]

# Main simulation loop: process each page access in the reference string
for addrIndex, n in enumerate(addrList):
    victim = -1

    # 1. OPT/UNOPT Future-Peeking Preparation
    if policy in ["OPT", "UNOPT"]:
        occurrences[n].popleft()

    # 2. Hit/Miss Detection
    is_hit = n in mem_set

    if is_hit:
        hits += 1
        if policy in ["LRU", "MRU"]:
            memory_ordered.move_to_end(n)
    else:
        miss += 1  # Cache Miss

        # 3. Eviction Logic (Only if cache is full)
        if len(mem_set) == cachesize:
            if policy in ["FIFO", "LRU"]:
                victim, _ = memory_ordered.popitem(last=False)
            elif policy == "MRU":
                victim, _ = memory_ordered.popitem(last=True)
            elif policy == "RAND":
                victim = memory.pop(random.randrange(len(memory)))
            elif policy == "CLOCK":
                while True:
                    page_at_hand = memory[clock_hand]
                    if ref.get(page_at_hand, 0) == 0:
                        victim = memory.pop(clock_hand)
                        break
                    ref[page_at_hand] = 0
                    clock_hand = (clock_hand + 1) % len(memory)
            elif policy in ["OPT", "UNOPT"]:
                victim = opt_func(
                    memory,
                    key=lambda p: occurrences[p][0] if occurrences[p] else float("inf"),
                )
                memory.remove(victim)

        if victim != -1:
            mem_set.remove(victim)
            ref.pop(victim, None)

        # 4. Insertion Logic (New page into cache)
        if is_ordered_policy:
            memory_ordered[n] = True
        else:
            memory.append(n)
        mem_set.add(n)

    # 5. Simulation Housekeeping and Stats
    if is_ordered_policy:
        if not notrace:
            memory = list(memory_ordered)
    elif policy == "CLOCK" and victim != -1:
        clock_hand %= len(memory) if memory else 1

    ref[n] = min(ref.get(n, 0) + 1, clockbits)

    if not notrace:
        outcome = "HIT " if is_hit else "MISS"
        print(
            f"Access: {n}  {outcome} {leftStr} -> {str(memory):>12} <- {riteStr} Replaced:{vfunc(victim)} [Hits:{hits} Misses:{miss}]"
        )

total = hits + miss
hitrate = (100.0 * hits) / total if total > 0 else 0.0
print(f"FINALSTATS hits {hits}   misses {miss}   hitrate {hitrate:.2f}")
print("")
