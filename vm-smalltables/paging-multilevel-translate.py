#! /usr/bin/python3

import sys
import random
import argparse


class OS:
    VALID_BIT = 0x80  # 1000 0000
    EMPTY_PTE_CONTENTS = 0x7F  # 0111 1111

    def __init__(self):
        # Simulation parameters: 4k physical memory (128 pages of 32 bytes)
        self.page_size = 32  # log2(32)   = 5
        self.phys_pages = 128  # log2(128)  = 7
        self.phys_mem_size = self.page_size * self.phys_pages  # 32 x128
        self.va_pages = 1024  # log2(1024) = 10
        self.va_size = self.page_size * self.va_pages  # 32 x 1024
        self.pte_size = 1
        self.page_bits = 5  # log2(page_size = 32)

        # Optimized memory allocation tracking
        self.free_pages = list(range(self.phys_pages))  # array with 128 elements
        self.max_page_count = self.phys_pages

        # Physical memory initialization
        self.memory = [0] * self.phys_mem_size

        # Page Directory Base Register per process
        self.pdbr = {}

        # Multi-level bitmasking (15-bit address: 5-bit PDE, 5-bit PTE, 5-bit Offset)
        self.PDE_MASK = 0x7C00  # 0111 1100 0000 0000
        self.PDE_SHIFT = 10
        self.PTE_MASK = 0x03E0  # 0000 0011 1110 0000
        self.PTE_SHIFT = 5
        self.OFFSET_MASK = 0x001F  # 0000 0000 0001 1111

    def find_free(self):
        if not self.free_pages:
            raise RuntimeError("Out of physical memory")

        # O(1) random selection and removal from the pool
        idx = random.randrange(len(self.free_pages))
        self.free_pages[idx], self.free_pages[-1] = (
            self.free_pages[-1],
            self.free_pages[idx],
        )
        look = self.free_pages.pop()
        return look

    def init_page(self, page_number):
        start = page_number << self.page_bits
        self.memory[start : start + self.page_size] = [
            self.EMPTY_PTE_CONTENTS
        ] * self.page_size

    def get_pte(self, virtual_addr, pte_page, verbose):
        pte_idx = (virtual_addr & self.PTE_MASK) >> self.PTE_SHIFT
        pte_addr = (pte_page << self.page_bits) | pte_idx
        pte = self.memory[pte_addr]
        valid = (pte & self.VALID_BIT) >> 7
        pfn = pte & 0x7F
        if verbose:
            print(
                f"    --> pte index:0x{pte_idx:x} [decimal {pte_idx}] pte contents:0x{pte:x} "
                f"(valid {valid}, pfn 0x{pfn:02x} [decimal {pfn}])"
            )
        return valid, pfn, pte_addr

    def get_pde(self, pid, virtual_addr, verbose):
        pd_page = self.pdbr[pid]
        pde_idx = (virtual_addr & self.PDE_MASK) >> self.PDE_SHIFT
        pde_addr = (pd_page << self.page_bits) | pde_idx
        pde = self.memory[pde_addr]
        valid = (pde & self.VALID_BIT) >> 7
        pt_pfn = pde & 0x7F
        if verbose:
            print(
                f"  --> pde index:0x{pde_idx:x} [decimal {pde_idx}] pde contents:0x{pde:x} "
                f"(valid {valid}, pfn 0x{pt_pfn:02x} [decimal {pt_pfn}])"
            )
        return valid, pt_pfn, pde_addr

    def set_entry(self, entry_addr, physical_page):
        self.memory[entry_addr] = self.VALID_BIT | physical_page

    def alloc_virtual_page(self, pid, virtual_page, physical_page):
        virtual_addr = virtual_page << self.page_bits
        valid, pt_pfn, pde_addr = self.get_pde(pid, virtual_addr, False)

        if not valid:
            pte_page = self.find_free()
            self.set_entry(pde_addr, pte_page)
            self.init_page(pte_page)
        else:
            pte_page = pt_pfn

        valid, pfn, pte_addr = self.get_pte(virtual_addr, pte_page, False)
        assert not valid
        self.set_entry(pte_addr, physical_page)

    def translate(self, pid, virtual_addr):
        valid, pt_pfn, _ = self.get_pde(pid, virtual_addr, True)
        if not valid:
            return -1  # PDE Fault

        valid, pfn, _ = self.get_pte(virtual_addr, pt_pfn, True)
        if not valid:
            return -2  # PTE Fault

        offset = virtual_addr & self.OFFSET_MASK
        return (pfn << self.page_bits) | offset

    def fill_page_with_data(self, page_number):
        start_idx = page_number * self.page_size
        self.memory[start_idx : start_idx + self.page_size] = [
            random.randint(0, 31) for _ in range(self.page_size)
        ]

    def allocate_process(self, pid, num_pages):
        pd_page = self.find_free()
        self.pdbr[pid] = pd_page
        self.init_page(pd_page)

        # Optimization: random.sample is much faster than a collision-checking while loop
        allocated_vps = random.sample(range(self.va_pages), num_pages)
        for vp in allocated_vps:
            pp = self.find_free()
            self.alloc_virtual_page(pid, vp, pp)
            self.fill_page_with_data(pp)
        return allocated_vps

    def memory_dump(self):
        for i in range(self.phys_pages):
            start = i * self.page_size
            chunk = self.memory[start : start + self.page_size]
            # Process memory in 2-byte chunks and join with spaces
            hex_data = " ".join(
                f"{chunk[j]:02x}{chunk[j+1]:02x}" for j in range(0, len(chunk), 2)
            )
            print(f"page {i:3d}: {hex_data}")

    def get_pdbr(self, pid):
        return self.pdbr[pid]

    def get_value(self, addr):
        return self.memory[addr]


def main():
    parser = argparse.ArgumentParser(
        description="Simulate multi-level page table translation."
    )
    parser.add_argument("-s", "--seed", default=0, type=int, help="Random seed")
    parser.add_argument(
        "-a",
        "--allocated",
        default=64,
        type=int,
        help="Number of virtual pages allocated",
    )
    parser.add_argument(
        "-n",
        "--addresses",
        default=10,
        type=int,
        help="Number of virtual addresses to generate",
    )
    parser.add_argument(
        "-c", "--solve", action="store_true", default=False, help="Compute answers"
    )

    args = parser.parse_args()

    print(f"ARG seed {args.seed}")
    print(f"ARG allocated {args.allocated}")
    print(f"ARG num {args.addresses}")
    print("")

    random.seed(args.seed if args.seed > 0 else None)

    simulation_os = OS()
    used_vps = simulation_os.allocate_process(1, args.allocated)
    simulation_os.memory_dump()

    print(
        f"\nPDBR: {simulation_os.get_pdbr(1)} (decimal) [This means the page directory is held in this page]\n"
    )

    for i in range(args.addresses):
        # Generate addresses: 50% chance of a random address, 50% chance of a validly allocated one.
        if random.random() > 0.5 or i >= len(used_vps):
            vaddr = random.randint(0, (1024 * 32) - 1)
        else:
            vaddr = (used_vps[i] << 5) | random.randint(0, 31)

        if args.solve:
            print(f"Virtual Address 0x{vaddr:04x}:")
            phys_addr = simulation_os.translate(1, vaddr)
            if phys_addr >= 0:
                print(
                    f"      --> Translates to Physical Address 0x{phys_addr:03x} --> Value: 0x{simulation_os.get_value(phys_addr):02x}"
                )
            elif phys_addr == -1:
                print("      --> Fault (page directory entry not valid)")
            else:
                print("      --> Fault (page table entry not valid)")
        else:
            print(
                f"Virtual Address {vaddr:04x}: Translates To What Physical Address (And Fetches what Value)? Or Fault?"
            )

    print("")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
