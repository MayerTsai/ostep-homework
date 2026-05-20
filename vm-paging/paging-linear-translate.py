#! /usr/bin/python3

import sys
import argparse
import random
import math
import array


def convert_size_string_to_bytes(size_str):
    """Converts a size string (e.g., '16k', '32m') to bytes."""
    size_str = size_str.lower()
    multipliers = {"k": 1024, "m": 1024**2, "g": 1024**3}

    multiplier = 1
    if size_str and size_str[-1] in multipliers:
        multiplier = multipliers[size_str[-1]]
        size_str = size_str[:-1]

    try:
        return int(size_str) * multiplier
    except ValueError:
        print(f"Error: Invalid size string '{size_str}'.")
        sys.exit(1)


def check_is_power_of_2(value, name):
    """Checks if a value is a positive power of 2."""
    if value <= 0 or (value & (value - 1) != 0):
        print(f"Error: {name} ({value}) must be a positive power of 2.")
        sys.exit(1)


def check_is_multiple_of(bignum, num, name):
    """Checks if bignum is a multiple of num."""
    if bignum % num != 0:
        print(f"Error: {name} ({bignum}) must be a multiple of {num}.")
        sys.exit(1)


def generate_page_table(asize, psize, pagesize, used_percent, verbose):
    """Generates a random page table."""
    num_physical_pages = psize // pagesize
    num_virtual_pages = asize // pagesize

    # `used_physical_pages` tracks which physical pages are already assigned.
    # `page_table_entries` stores the PFN for each VPN, or -1 if invalid.
    page_table_entries = array.array("i", [-1] * num_virtual_pages)

    # Optimization: Pre-shuffle physical frames to avoid collision loops
    pfn_pool = list(range(num_physical_pages))
    random.shuffle(pfn_pool)

    print("\nPage Table (from entry 0 down to the max size)")
    print("The format of the page table is simple:")
    print("The high-order (left-most) bit is the VALID bit.")
    print("  If the bit is 1, the rest of the entry is the PFN.")
    print("  If the bit is 0, the page is not valid.")
    if not verbose:
        print("Use verbose mode (-v) if you want to print the VPN # by")
        print("each entry of the page table.")
    print("")

    threshold = used_percent / 100.0
    for vpn in range(num_virtual_pages):
        pfn, entry = -1, 0
        if random.random() < threshold:
            pfn = pfn_pool.pop()
            entry = 0x80000000 | pfn

        page_table_entries[vpn] = pfn
        if verbose:
            print(f"  [{vpn:8d}]  0x{entry:08x}")
        else:
            print(f"  0x{entry:08x}")
    print("")
    return page_table_entries


def process_address_trace(
    addresses_str,
    num_addrs_to_generate,
    asize,
    pagesize,
    page_table_entries,
    solve,
    vpn_shift,
    pagemask,
    vpnmask,
):
    """Processes a list of virtual addresses and translates them."""
    if addresses_str == "-1":
        addr_list = [random.randrange(asize) for _ in range(num_addrs_to_generate)]
    else:
        try:
            addr_list = [int(addr) for addr in addresses_str.split(",")]
        except ValueError:
            print(
                f"Error: Invalid address list '{addresses_str}'. Addresses must be integers separated by commas."
            )
            sys.exit(1)

    print("Virtual Address Trace")
    for vaddr in addr_list:
        header = f"  VA 0x{vaddr:08x} (decimal: {vaddr:8d}) -->"
        if not solve:
            print(f"{header} PA or invalid address?")
            continue

        if vaddr < 0 or vaddr >= asize:
            print(f"{header} Invalid (address out of bounds)")
            continue

        vpn = (vaddr & vpnmask) >> vpn_shift
        pfn = page_table_entries[vpn]
        if pfn < 0:
            print(f"{header} Invalid (VPN {vpn} not valid)")
        else:
            paddr = (pfn << vpn_shift) | (vaddr & pagemask)
            print(f"{header} 0x{paddr:08x} (decimal {paddr:8d}) [VPN {vpn}]")
    print("")

    if not solve:
        print(
            "For each virtual address, write down the physical address it translates to"
        )
        print("OR write down that it is an out-of-bounds address (e.g., segfault).")
        print("")


def main():
    parser = argparse.ArgumentParser(
        description="Simulate linear page table translation."
    )
    parser.add_argument(
        "-A",
        "--addresses",
        default="-1",
        help="a set of comma-separated virtual addresses to access; -1 means randomly generate",
        type=str,
    )
    parser.add_argument(
        "-a",
        "--asize",
        default="16k",
        help="address space size (e.g., 16, 64k, 32m, 1g)",
        type=str,
    )
    parser.add_argument(
        "-p",
        "--physmem",
        default="64k",
        help="physical memory size (e.g., 16, 64k, 32m, 1g)",
        type=str,
    )
    parser.add_argument(
        "-P",
        "--pagesize",
        default="4k",
        help="page size (e.g., 4k, 8k, whatever)",
        type=str,
    )
    parser.add_argument(
        "-n",
        "--numaddrs",
        default=5,
        help="number of virtual addresses to generate",
        type=int,
    )
    parser.add_argument(
        "-u",
        "--used",
        default=50,
        help="percent of virtual address space that is used (0-100)",
        type=int,
    )
    parser.add_argument(
        "-v", "--verbose", help="verbose mode", action="store_true", default=False
    )
    parser.add_argument(
        "-c",
        "--solve",
        help="compute answers for me",
        action="store_true",
        default=False,
    )

    args = parser.parse_args()

    print(f"ARG address space size: {args.asize}")
    print(f"ARG phys mem size: {args.physmem}")
    print(f"ARG page size: {args.pagesize}")
    print(f"ARG verbose: {args.verbose}")
    print(f"ARG addresses: {args.addresses}")
    print("")

    asize = convert_size_string_to_bytes(args.asize)
    psize = convert_size_string_to_bytes(args.physmem)
    pagesize = convert_size_string_to_bytes(args.pagesize)

    # Input validation
    if psize <= 0 or asize <= 0:
        print("Error: Physical memory and address space sizes must be greater than 0.")
        sys.exit(1)
    if psize <= asize:
        print(
            "Error: Physical memory size must be GREATER than address space size (for this simulation)."
        )
        sys.exit(1)

    limit_1g = 1024**3
    if psize >= limit_1g or asize >= limit_1g:
        print("Error: Must use smaller sizes (less than 1 GB) for this simulation.")
        sys.exit(1)
    if not (0 <= args.used <= 100):
        print("Error: Percent used (-u) must be between 0 and 100.")
        sys.exit(1)

    check_is_multiple_of(asize, pagesize, "Address space size")
    check_is_multiple_of(psize, pagesize, "Physical memory size")
    check_is_power_of_2(asize, "Address space size")
    check_is_power_of_2(pagesize, "Page size")

    # Pre-compute translation constants
    vpn_shift = pagesize.bit_length() - 1
    pagemask = pagesize - 1
    vpnmask = 0xFFFFFFFF & ~pagemask

    print(f"pagemask: {pagemask}({hex(pagemask)})")
    print(f"vpnmask: {vpnmask}({hex(vpnmask)})")
    print(f"vpn_shift: {vpn_shift}")
    print("")

    page_table = generate_page_table(asize, psize, pagesize, args.used, args.verbose)
    process_address_trace(
        args.addresses,
        args.numaddrs,
        asize,
        pagesize,
        page_table,
        args.solve,
        vpn_shift,
        pagemask,
        vpnmask,
    )


if __name__ == "__main__":
    main()
