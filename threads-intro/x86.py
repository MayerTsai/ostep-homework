#! /usr/bin/python3

import sys
import time
import random
import argparse


def time_clock():
    return time.process_time()


def dospace(howmuch):
    print(" " * (25 * howmuch), end="")


# Custom assert for runtime errors
def zassert(cond, msg):
    if not cond:
        print("ABORT::", msg)
        exit(1)
    return True


class cpu:
    """x86 CPU Simulator"""

    def __init__(self, memory, memtrace, regtrace, cctrace, compute, verbose):
        #
        # CONSTANTS
        #

        # conditions
        self.COND_GT = 0
        self.COND_GTE = 1
        self.COND_LT = 2
        self.COND_LTE = 3
        self.COND_EQ = 4
        self.COND_NEQ = 5

        # registers in system
        self.REG_ZERO = 0
        self.REG_AX = 1
        self.REG_BX = 2
        self.REG_CX = 3
        self.REG_DX = 4
        self.REG_SP = 5
        self.REG_BP = 6

        # system memory: in KB
        self.max_memory = memory * 1024

        # which memory addrs and registers to trace?
        self.memtrace = memtrace
        self.regtrace = regtrace
        self.cctrace = cctrace
        self.compute = compute
        self.verbose = verbose

        self.PC = 0
        self.labels = {}
        self.vars = {}
        self.registers = [0] * 7
        self.conditions = [False] * 6
        self.memory = []
        self.pmemory = []  # for printable version of what's in memory (instructions)

        self.condlist = [
            self.COND_GTE,
            self.COND_GT,
            self.COND_LTE,
            self.COND_LT,
            self.COND_NEQ,
            self.COND_EQ,
        ]

        self.regnums = [
            self.REG_ZERO,
            self.REG_AX,
            self.REG_BX,
            self.REG_CX,
            self.REG_DX,
            self.REG_SP,
            self.REG_BP,
        ]

        self.regnames = {
            "zero": self.REG_ZERO,
            "ax": self.REG_AX,
            "bx": self.REG_BX,
            "cx": self.REG_CX,
            "dx": self.REG_DX,
            "sp": self.REG_SP,
            "bp": self.REG_BP,
        }
        self.rev_regnames = {v: k for k, v in self.regnames.items()}

        # Pre-resolved trace information for performance
        self.resolved_memtrace = []
        self.resolved_regtrace = []

        tmplist = []
        for r in self.regtrace:
            assert r in self.regnames, f"Register {r} cannot be traced"
            tmplist.append(self.regnames[r])
        self.resolved_regtrace = tmplist

        self.init_memory()
        self.init_registers()
        self.init_condition_codes()

    def init_condition_codes(self):
        for c in self.condlist:
            self.conditions[c] = False

    def init_memory(self):
        self.memory = [0] * self.max_memory
        self.pmemory = [""] * self.max_memory

    def init_registers(self):
        for i in self.regnums:
            self.registers[i] = 0

    def _resolve_traces(self):
        """Pre-resolve trace targets to avoid lookups during simulation loop."""
        self.resolved_memtrace = []
        for m in self.memtrace:
            addr = int(m) if m[0].isdigit() else self.vars.get(m)
            if addr is not None:
                self.resolved_memtrace.append((m, addr))

    def get_regnum(self, name):
        assert name in self.regnames
        return self.regnames[name]

    def get_regname(self, num):
        assert num in self.regnums
        return self.rev_regnames[num]

    def get_reg(self, reg):
        assert reg in self.regnums
        return self.registers[reg]

    def get_cond(self, cond):
        assert cond in self.condlist
        return self.conditions[cond]

    def get_pc(self):
        return self.PC

    def set_reg(self, reg, value):
        assert reg in self.regnums
        self.registers[reg] = value

    def set_cond(self, cond, value):
        assert cond in self.condlist
        self.conditions[cond] = value

    def set_pc(self, pc):
        self.PC = pc

    def halt(self):
        return -1

    def iyield(self):
        return -2

    def nop(self):
        return 0

    def rdump(self):
        regs = self.registers
        print(
            f"REGISTERS:: ax:{regs[1]} bx:{regs[2]} cx:{regs[3]} dx:{regs[4]}", end=" "
        )
        return 0

    def mdump(self, index):
        print(f"m[{index}] {self.memory[index]}")
        return 0

    def move_i_to_r(self, src, dst):
        self.registers[dst] = src
        return 0

    # memory: value, register, register
    def move_i_to_m(self, src, value, reg1, reg2):
        addr = value + self.registers[reg1] + self.registers[reg2]
        self.memory[addr] = src
        return 0

    def move_m_to_r(self, value, reg1, reg2, dst):
        addr = value + self.registers[reg1] + self.registers[reg2]
        self.registers[dst] = self.memory[addr]
        return 0

    def move_r_to_m(self, src, value, reg1, reg2):
        addr = value + self.registers[reg1] + self.registers[reg2]
        self.memory[addr] = self.registers[src]
        return 0

    def move_r_to_r(self, src, dst):
        self.registers[dst] = self.registers[src]
        return 0

    def add_i_r(self, src, dst):
        self.registers[dst] += src
        return 0

    def add_r_r(self, src, dst):
        self.registers[dst] += self.registers[src]
        return 0

    def sub_i_r(self, src, dst):
        self.registers[dst] -= src
        return 0

    def sub_r_r(self, src, dst):
        self.registers[dst] -= self.registers[src]
        return 0

    def atomic_exchange(self, src, value, reg1, reg2):
        tmp = value + self.registers[reg1] + self.registers[reg2]
        old = self.memory[tmp]
        self.memory[tmp] = self.registers[src]
        self.registers[src] = old
        return 0

    def fetchadd(self, src, value, reg1, reg2):
        tmp = value + self.registers[reg1] + self.registers[reg2]
        old = self.memory[tmp]
        self.memory[tmp] = self.memory[tmp] + self.registers[src]
        self.registers[src] = old
        return 0

    def test_all(self, src, dst):
        self.init_condition_codes()
        if dst > src:
            self.conditions[self.COND_GT] = True
        if dst >= src:
            self.conditions[self.COND_GTE] = True
        if dst < src:
            self.conditions[self.COND_LT] = True
        if dst <= src:
            self.conditions[self.COND_LTE] = True
        if dst == src:
            self.conditions[self.COND_EQ] = True
        if dst != src:
            self.conditions[self.COND_NEQ] = True
        return 0

    def test_i_r(self, src, dst):
        self.init_condition_codes()
        return self.test_all(src, self.registers[dst])

    def test_r_i(self, src, dst):
        self.init_condition_codes()
        return self.test_all(self.registers[src], dst)

    def test_r_r(self, src, dst):
        self.init_condition_codes()
        return self.test_all(self.registers[src], self.registers[dst])

    def jump(self, targ):
        self.PC = targ
        return 0

    def jump_notequal(self, targ):
        if self.conditions[self.COND_NEQ] == True:
            self.PC = targ
        return 0

    def jump_equal(self, targ):
        if self.conditions[self.COND_EQ] == True:
            self.PC = targ
        return 0

    def jump_lessthan(self, targ):
        if self.conditions[self.COND_LT] == True:
            self.PC = targ
        return 0

    def jump_lessthanorequal(self, targ):
        if self.conditions[self.COND_LTE] == True:
            self.PC = targ
        return 0

    def jump_greaterthan(self, targ):
        if self.conditions[self.COND_GT] == True:
            self.PC = targ
        return 0

    def jump_greaterthanorequal(self, targ):
        if self.conditions[self.COND_GTE] == True:
            self.PC = targ
        return 0

    #
    # CALL and RETURN
    #
    def call(self, targ):
        self.registers[self.REG_SP] -= 4
        self.memory[self.registers[self.REG_SP]] = self.PC
        self.PC = targ
        return 0

    def ret(self):
        self.PC = self.memory[self.registers[self.REG_SP]]
        self.registers[self.REG_SP] += 4
        return 0

    #
    # STACK and related
    #
    def push_r(self, reg):
        self.registers[self.REG_SP] -= 4
        self.memory[self.registers[self.REG_SP]] = self.registers[reg]
        return 0

    def push_m(self, value, reg1, reg2):
        # print 'push_m', value, reg1, reg2
        self.registers[self.REG_SP] -= 4
        tmp = value + self.registers[reg1] + self.registers[reg2]
        # push address onto stack, not memory value itself
        self.memory[self.registers[self.REG_SP]] = tmp
        return 0

    def pop(self):
        self.registers[self.REG_SP] += 4
        return 0

    def pop_r(self, dst):
        self.registers[dst] = self.registers[self.REG_SP]
        self.registers[self.REG_SP] += 4
        return 0

    #
    # HELPER func for getarg
    #
    def register_translate(self, r):
        assert r in self.regnames, f"Register {r} is not a valid register"
        return self.regnames[r]

    #
    # HELPER in parsing mov (quite primitive) and other ops
    # returns: (value, type)
    # where type is (TYPE_REGISTER, TYPE_IMMEDIATE, TYPE_MEMORY)
    #
    # FORMATS
    #    %ax           - register
    #    $10           - immediate
    #    10            - direct memory
    #    10(%ax)       - memory + reg indirect
    #    10(%ax,%bx)   - memory + 2 reg indirect
    #    10(%ax,%bx,4) - XXX (not handled)
    #
    def getarg(self, arg):
        tmp = "".join(arg.split()).replace(",", "")
        if not tmp:
            return None, "TYPE_NONE"

        if tmp[0] == "$":
            val_str = tmp[1:]
            try:
                return int(val_str), "TYPE_IMMEDIATE"
            except ValueError:
                zassert(False, "Immediate value [%s] must be an integer" % tmp)
        elif tmp[0] == "%":
            register = tmp.split("%")[1]
            return self.register_translate(register), "TYPE_REGISTER"
        elif tmp[0] == "(":
            register = tmp.split("(")[1].split(")")[0].split("%")[1]
            return (
                (0, self.register_translate(register), self.register_translate("zero")),
                "TYPE_MEMORY",
            )
        elif tmp[0] == ".":
            targ = tmp
            return targ, "TYPE_LABEL"
        elif tmp[0].isalpha() and not tmp[0].isdigit():
            zassert(tmp in self.vars, "Variable %s is not declared" % tmp)
            return (
                (
                    self.vars[tmp],
                    self.register_translate("zero"),
                    self.register_translate("zero"),
                ),
                "TYPE_MEMORY",
            )
        elif tmp[0].isdigit() or tmp[0] == "-":
            # MOST GENERAL CASE: number(reg,reg) or number(reg)
            # we ignore the common x86 number(reg,reg,constant) for now
            neg = 1
            if tmp[0] == "-":
                tmp = tmp[1:]
                neg = -1
            s = tmp.split("(")
            if len(s) == 1:
                value = neg * int(tmp)
                return (
                    (
                        int(value),
                        self.register_translate("zero"),
                        self.register_translate("zero"),
                    ),
                    "TYPE_MEMORY",
                )
            elif len(s) == 2:
                value = neg * int(s[0])
                t = s[1].split(")")[0].split(",")
                if len(t) == 1:
                    register = t[0].split("%")[1]
                    return (
                        (
                            int(value),
                            self.register_translate(register),
                            self.register_translate("zero"),
                        ),
                        "TYPE_MEMORY",
                    )
                elif len(t) == 2:
                    register1 = t[0].split("%")[1]
                    register2 = t[1].split("%")[1]
                    return (
                        (
                            int(value),
                            self.register_translate(register1),
                            self.register_translate(register2),
                        ),
                        "TYPE_MEMORY",
                    )
            else:
                print("mov: bad argument [%s]" % tmp)
                exit(1)
                return
        zassert(True, "mov: bad argument [%s]" % arg)
        return

    def load(self, infile, loadaddr):
        """Load a program into memory and pre-parse instructions into tuples."""
        pc = int(loadaddr)
        fd = open(infile)

        bpc = loadaddr
        data = 100

        for line in fd:
            cline = line.rstrip()

            if cline.startswith(("#", "//")) or not cline:
                continue

            # only pay attention to labels and variables
            tmp = cline.split("#")
            """
            if tmp[0] == ".var":
                assert len(tmp) == 2, f"no name or error name format for variable "
                assert tmp[1] in self.vars, f"Variable {tmp[1]} already declared"
                self.vars[tmp[1]] = data
                data += 4
                zassert(data < bpc, "Load address overrun by static data")
                if self.verbose:
                    print("ASSIGN VAR", tmp[0], "-->", tmp[1], self.vars[tmp[1]])
            elif tmp[0][0] == ".":
                assert len(tmp) == 1
                self.labels[tmp[0]] = int(pc)
                if self.verbose:
                    print("ASSIGN LABEL", tmp[0], "-->", pc)
            else:
                pc += 1
            """
            if tmp[0].startswith("."):
                self.labels[tmp[0]] = int(pc)
                if self.verbose:
                    print("ASSIGN LABEL", tmp[0], "-->", pc)
            else:
                pc += 1
        fd.close()

        if self.verbose:
            print("")

        # second pass: do everything else
        pc = int(loadaddr)
        fd = open(infile)
        for line in fd:
            cline = line.rstrip()
            if cline.startswith(("#", "//")) or not cline:
                continue

            # skip labels: all else must be instructions
            # stripped = cline.strip()
            if not cline.startswith("."):
                tmp = cline.split(None, 1)
                opcode = tmp[0]
                self.pmemory[pc] = cline.strip()

                # MAIN OPCODE LOOP
                if opcode == "mov":
                    rtmp = tmp[1].split(",", 1)
                    assert (
                        len(rtmp) == 2
                    ), f"mov: needs two args, separated by commas {cline}"

                    arg1 = rtmp[0].strip()
                    arg2 = rtmp[1].strip()
                    src, stype = self.getarg(arg1)
                    dst, dtype = self.getarg(arg2)
                    if stype == "TYPE_MEMORY" and dtype == "TYPE_MEMORY":
                        print("bad mov: two memory arguments")
                        exit(1)
                    elif stype == "TYPE_IMMEDIATE" and dtype == "TYPE_IMMEDIATE":
                        print("bad mov: two immediate arguments")
                        exit(1)
                    elif stype == "TYPE_IMMEDIATE" and dtype == "TYPE_REGISTER":
                        self.memory[pc] = (self.move_i_to_r, (int(src), dst))
                    elif stype == "TYPE_MEMORY" and dtype == "TYPE_REGISTER":
                        # src is already a tuple (value, reg1, reg2)
                        self.memory[pc] = (
                            self.move_m_to_r,
                            (
                                src[0],
                                src[1],
                                src[2],
                                dst,
                            ),
                        )
                    elif stype == "TYPE_REGISTER" and dtype == "TYPE_MEMORY":
                        # dst is already a tuple (value, reg1, reg2)
                        self.memory[pc] = (
                            self.move_r_to_m,
                            (
                                src,
                                dst[0],
                                dst[1],
                                dst[2],
                            ),
                        )
                    elif stype == "TYPE_REGISTER" and dtype == "TYPE_REGISTER":
                        self.memory[pc] = (self.move_r_to_r, (src, dst))
                    elif stype == "TYPE_IMMEDIATE" and dtype == "TYPE_MEMORY":
                        # dst is already a tuple (value, reg1, reg2)
                        self.memory[pc] = (
                            self.move_i_to_m,
                            (
                                src,
                                dst[0],
                                dst[1],
                                dst[2],
                            ),
                        )
                    else:
                        zassert(False, "malformed mov instruction")
                elif opcode == "pop":
                    if len(tmp) == 1:
                        self.memory[pc] = (self.pop, ())
                    elif len(tmp) == 2:
                        dst, dtype = self.getarg(tmp[1].strip())
                        zassert(
                            dtype == "TYPE_REGISTER", "Can only pop into a register"
                        )
                        self.memory[pc] = (self.pop_r, (dst,))
                    else:
                        zassert(False, "pop instruction must take zero/one args")
                elif opcode == "push":
                    src, stype = self.getarg(tmp[1].strip())
                    if stype == "TYPE_REGISTER":
                        self.memory[pc] = (self.push_r, (int(src),))
                    elif stype == "TYPE_MEMORY":
                        self.memory[pc] = (
                            self.push_m,
                            (src[0], src[1], src[2]),
                        )
                    else:
                        zassert(False, "Cannot push anything but registers")
                elif opcode == "call":
                    targ, ttype = self.getarg(tmp[1].strip())
                    if ttype == "TYPE_LABEL":
                        self.memory[pc] = (self.call, (int(self.labels[targ]),))
                    else:
                        zassert(False, "Cannot call anything but a label")
                elif opcode == "ret":
                    assert len(tmp) == 1
                    self.memory[pc] = (self.ret, ())
                elif opcode == "add":
                    rtmp = tmp[1].split(",", 1)
                    zassert(
                        len(tmp) == 2 and len(rtmp) == 2,
                        "add: needs two args, separated by commas [%s]" % cline,
                    )
                    arg1 = rtmp[0].strip()
                    arg2 = rtmp[1].strip()
                    src, stype = self.getarg(arg1)
                    dst, dtype = self.getarg(arg2)
                    if stype == "TYPE_IMMEDIATE" and dtype == "TYPE_REGISTER":
                        self.memory[pc] = (self.add_i_r, (int(src), dst))
                    elif stype == "TYPE_REGISTER" and dtype == "TYPE_REGISTER":
                        self.memory[pc] = (self.add_r_r, (int(src), dst))
                    else:
                        zassert(False, "malformed usage of add instruction")
                elif opcode == "sub":
                    rtmp = tmp[1].split(",", 1)
                    zassert(
                        len(tmp) == 2 and len(rtmp) == 2,
                        "sub: needs two args, separated by commas [%s]" % cline,
                    )
                    arg1 = rtmp[0].strip()
                    arg2 = rtmp[1].strip()
                    src, stype = self.getarg(arg1)
                    dst, dtype = self.getarg(arg2)
                    if stype == "TYPE_IMMEDIATE" and dtype == "TYPE_REGISTER":
                        self.memory[pc] = (self.sub_i_r, (int(src), dst))
                    elif stype == "TYPE_REGISTER" and dtype == "TYPE_REGISTER":
                        self.memory[pc] = (self.sub_r_r, (int(src), dst))
                    else:
                        zassert(False, "malformed usage of sub instruction")
                elif opcode == "fetchadd":
                    rtmp = tmp[1].split(",", 1)
                    zassert(
                        len(tmp) == 2 and len(rtmp) == 2,
                        "fetchadd: needs two args, separated by commas [%s]" % cline,
                    )
                    arg1 = rtmp[0].strip()
                    arg2 = rtmp[1].strip()
                    src, stype = self.getarg(arg1)
                    dst, dtype = self.getarg(arg2)
                    if stype == "TYPE_REGISTER" and dtype == "TYPE_MEMORY":
                        self.memory[pc] = (
                            self.fetchadd,
                            (
                                src,
                                dst[0],
                                dst[1],
                                dst[2],
                            ),
                        )
                    else:
                        zassert(False, "poorly specified fetch and add")
                elif opcode == "xchg":
                    rtmp = tmp[1].split(",", 1)
                    zassert(
                        len(tmp) == 2 and len(rtmp) == 2,
                        "xchg: needs two args, separated by commas [%s]" % cline,
                    )
                    arg1 = rtmp[0].strip()
                    arg2 = rtmp[1].strip()
                    src, stype = self.getarg(arg1)
                    dst, dtype = self.getarg(arg2)
                    if stype == "TYPE_REGISTER" and dtype == "TYPE_MEMORY":
                        self.memory[pc] = (
                            self.atomic_exchange,
                            (
                                src,
                                dst[0],
                                dst[1],
                                dst[2],
                            ),
                        )
                    else:
                        zassert(False, "poorly specified atomic exchange")
                elif opcode == "test":
                    rtmp = tmp[1].split(",", 1)
                    zassert(
                        len(tmp) == 2 and len(rtmp) == 2,
                        "test: needs two args, separated by commas [%s]" % cline,
                    )
                    arg1 = rtmp[0].strip()
                    arg2 = rtmp[1].strip()
                    src, stype = self.getarg(arg1)
                    dst, dtype = self.getarg(arg2)
                    if stype == "TYPE_IMMEDIATE" and dtype == "TYPE_REGISTER":
                        self.memory[pc] = (self.test_i_r, (int(src), dst))
                    elif stype == "TYPE_REGISTER" and dtype == "TYPE_REGISTER":
                        self.memory[pc] = (self.test_r_r, (int(src), dst))
                    elif stype == "TYPE_REGISTER" and dtype == "TYPE_IMMEDIATE":
                        self.memory[pc] = (self.test_r_i, (int(src), dst))
                    else:
                        zassert(False, "malformed usage of test instruction")
                elif opcode == "j":
                    targ, ttype = self.getarg(tmp[1].strip())
                    zassert(
                        ttype == "TYPE_LABEL", "bad jump target [%s]" % tmp[1].strip()
                    )
                    self.memory[pc] = (self.jump, (int(self.labels[targ]),))
                elif opcode == "jne":
                    targ, ttype = self.getarg(tmp[1].strip())
                    zassert(
                        ttype == "TYPE_LABEL", "bad jump target [%s]" % tmp[1].strip()
                    )
                    self.memory[pc] = (self.jump_notequal, (int(self.labels[targ]),))
                elif opcode == "je":
                    targ, ttype = self.getarg(tmp[1].strip())
                    zassert(
                        ttype == "TYPE_LABEL", "bad jump target [%s]" % tmp[1].strip()
                    )
                    self.memory[pc] = (self.jump_equal, (int(self.labels[targ]),))
                elif opcode == "jlt":
                    targ, ttype = self.getarg(tmp[1].strip())
                    zassert(
                        ttype == "TYPE_LABEL", "bad jump target [%s]" % tmp[1].strip()
                    )
                    self.memory[pc] = (self.jump_lessthan, (int(self.labels[targ]),))
                elif opcode == "jlte":
                    targ, ttype = self.getarg(tmp[1].strip())
                    zassert(
                        ttype == "TYPE_LABEL", "bad jump target [%s]" % tmp[1].strip()
                    )
                    self.memory[pc] = (
                        self.jump_lessthanorequal,
                        (int(self.labels[targ]),),
                    )
                elif opcode == "jgt":
                    targ, ttype = self.getarg(tmp[1].strip())
                    zassert(
                        ttype == "TYPE_LABEL", "bad jump target [%s]" % tmp[1].strip()
                    )
                    self.memory[pc] = (self.jump_greaterthan, (int(self.labels[targ]),))
                elif opcode == "jgte":
                    targ, ttype = self.getarg(tmp[1].strip())
                    zassert(
                        ttype == "TYPE_LABEL", "bad jump target [%s]" % tmp[1].strip()
                    )
                    self.memory[pc] = (
                        self.jump_greaterthanorequal,
                        (int(self.labels[targ]),),
                    )
                elif opcode == "nop":
                    self.memory[pc] = (self.nop, ())
                elif opcode == "halt":
                    self.memory[pc] = (self.halt, ())
                elif opcode == "yield":
                    self.memory[pc] = (self.iyield, ())
                elif opcode == "rdump":
                    self.memory[pc] = (self.rdump, ())
                elif opcode == "mdump":
                    self.memory[pc] = (self.mdump, (int(tmp[1]),))
                else:
                    print("illegal opcode: ", opcode)
                    exit(1)
                if self.verbose:
                    print(
                        f"pc:{pc} LOADING {self.pmemory[pc]:>20s} --> {self.memory[pc]}"
                    )
                # INCREMENT PC for loader
                pc += 1
        # END: loop over file
        fd.close()
        if self.verbose:
            print("")

        self._resolve_traces()
        return

    def print_headers(self, procs):
        header_parts = []
        if self.resolved_memtrace:
            for label, _ in self.resolved_memtrace:
                header_parts.append(f"{label:>5}")
            header_parts.append(" ")
        if self.resolved_regtrace:
            for ridx in self.resolved_regtrace:
                header_parts.append(f"{self.rev_regnames[ridx]:>5}")
            header_parts.append(" ")
        if self.cctrace:
            header_parts.append(">= >  <= <  != ==")

        for i in range(procs.getnum()):
            header_parts.append(f"       Thread {i}        ")
        print("".join(header_parts))

    def get_trace(self):
        """Constructs the trace string for the current CPU state."""
        if not (self.resolved_memtrace or self.resolved_regtrace or self.cctrace):
            return ""

        parts = []
        if self.resolved_memtrace:
            for _, addr in self.resolved_memtrace:
                if self.compute:
                    parts.append(f"{self.memory[addr]:>5}")
                else:
                    parts.append(f"{'?':>5}")
            parts.append(" ")

        if self.resolved_regtrace:
            for ridx in self.resolved_regtrace:
                if self.compute:
                    parts.append(f"{self.registers[ridx]:>5}")
                else:
                    parts.append(f"{'?':>5}")
            parts.append(" ")

        if self.cctrace:
            for c in self.condlist:
                if self.compute:
                    parts.append("1 " if self.conditions[c] else "0 ")
                else:
                    parts.append("? ")
        return "".join(parts)

    def setint(self, intfreq, intrand):
        return intfreq if not intrand else int(random.random() * intfreq) + 1

    _COLUMN_WIDTH = 25

    def run(self, procs, intfreq, intrand):
        """
        Main execution loop. Optimized by localizing method lookups.
        """
        interrupt = self.setint(intfreq, intrand)
        icount = 0

        # Optimization: Localize lookups for speed in Python hot loops
        get_trace = self.get_trace
        procs_getcurr = procs.getcurr
        procs_next = procs.next
        procs_save = procs.save
        procs_restore = procs.restore

        # Localize frequently used attributes for faster access
        memory = self.memory
        pmemory = self.pmemory
        col_width = self._COLUMN_WIDTH

        self.print_headers(procs)
        print(get_trace())

        while True:
            curr_proc = procs_getcurr()
            tid = curr_proc.gettid()

            # FETCH
            prevPC = self.PC
            func, args = memory[prevPC]
            self.PC += 1

            # EXECUTE (pre-decoded func)
            rc = func(*args)

            # Trace and instruction output
            print(f"{get_trace()}{' ' * (tid * col_width)}{prevPC} {pmemory[prevPC]}")
            icount += 1

            if rc == -1:
                procs.done()
                if procs.numdone() == procs.getnum():
                    return icount
                procs_next()
                procs_restore()

                msg = "".join(["----- Halt;Switch ----- "] * procs.getnum())
                print(f"{get_trace()}{msg}")
                interrupt = self.setint(intfreq, intrand)
                continue

            interrupt -= 1
            if interrupt == 0 or rc == -2:
                interrupt = self.setint(intfreq, intrand)
                procs_save()
                procs_next()
                procs_restore()

                msg = "".join(["------ Interrupt ------ "] * procs.getnum())
                print(f"{get_trace()}{msg}")


#
# PROCESS LIST class
#
class proclist:
    def __init__(self):
        self.plist = []
        self.curr = 0
        self.active = 0

    def done(self):
        self.plist[self.curr].setdone()
        self.active -= 1

    def numdone(self):
        return len(self.plist) - self.active

    def getnum(self):
        return len(self.plist)

    def add(self, p):
        self.active += 1
        self.plist.append(p)

    def getcurr(self):
        return self.plist[self.curr]

    def save(self):
        self.plist[self.curr].save()

    def restore(self):
        self.plist[self.curr].restore()

    def next(self):
        for i in range(self.curr + 1, len(self.plist)):
            if self.plist[i].isdone() == False:
                self.curr = i
                return
        for i in range(0, self.curr + 1):
            if self.plist[i].isdone() == False:
                self.curr = i
                return


#
# PROCESS class
#
class process:
    def __init__(self, cpu, tid, pc, stackbottom, reginit):
        self.cpu = cpu  # object reference
        self.tid = tid
        self.pc = pc
        self.regs = {}
        self.cc = {}
        self.done = False
        self.stack = stackbottom

        # init regs: all 0 or specially set to something
        for r in self.cpu.regnums:
            self.regs[r] = 0
        if reginit != "":
            # form: ax=1,bx=2 (for some subset of registers)
            for r in reginit.split(":"):
                tmp = r.split("=")
                assert len(tmp) == 2
                self.regs[self.cpu.get_regnum(tmp[0])] = int(tmp[1])

        # init CCs
        for c in self.cpu.condlist:
            self.cc[c] = False

        # stack
        self.regs[self.cpu.get_regnum("sp")] = stackbottom
        # print 'REG', self.cpu.get_regnum('sp'), self.regs[self.cpu.get_regnum('sp')]

        return

    def gettid(self):
        return self.tid

    def save(self):
        self.pc = self.cpu.get_pc()
        for c in self.cpu.condlist:
            self.cc[c] = self.cpu.get_cond(c)
        for r in self.cpu.regnums:
            self.regs[r] = self.cpu.get_reg(r)

    def restore(self):
        self.cpu.set_pc(self.pc)
        for c in self.cpu.condlist:
            self.cpu.set_cond(c, self.cc[c])
        for r in self.cpu.regnums:
            self.cpu.set_reg(r, self.regs[r])

    def setdone(self):
        self.done = True

    def isdone(self):
        return self.done == True


#
# main program
#
parser = argparse.ArgumentParser(description="x86 CPU Simulator")
parser.add_argument("-s", "--seed", default=0, help="the random seed", type=int)
parser.add_argument(
    "-t", "--threads", default=2, help="number of threads", type=int, dest="numthreads"
)
parser.add_argument(
    "-p", "--program", default="", help="source program (in .s)", dest="progfile"
)
parser.add_argument(
    "-i",
    "--interrupt",
    default=50,
    help="interrupt frequency",
    type=int,
    dest="intfreq",
)
parser.add_argument(
    "-r",
    "--randints",
    default=False,
    help="if interrupts are random",
    action="store_true",
    dest="intrand",
)
parser.add_argument(
    "-a",
    "--argv",
    default="",
    help="comma-separated per-thread args (e.g., ax=1,ax=2 sets thread 0 ax reg to 1 and thread 1 ax reg to 2); specify multiple regs per thread via colon-separated list (e.g., ax=1:bx=2,cx=3 sets thread 0 ax and bx and just cx for thread 1)",
)
parser.add_argument(
    "-L", "--loadaddr", default=1000, help="address where to load code", type=int
)
parser.add_argument(
    "-m", "--memsize", default=128, help="size of address space (KB)", type=int
)
parser.add_argument(
    "-M",
    "--memtrace",
    default="",
    help="comma-separated list of addrs to trace (e.g., 20000,20001)",
)
parser.add_argument(
    "-R",
    "--regtrace",
    default="",
    help="comma-separated list of regs to trace (e.g., ax,bx,cx,dx)",
)
parser.add_argument(
    "-C",
    "--cctrace",
    default=False,
    help="should we trace condition codes",
    action="store_true",
)
parser.add_argument(
    "-S",
    "--printstats",
    default=False,
    help="print some extra stats",
    action="store_true",
)
parser.add_argument(
    "-v", "--verbose", default=False, help="print some extra info", action="store_true"
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

print(f"ARG seed {args.seed}")
print(f"ARG numthreads {args.numthreads}")
print(f"ARG program {args.progfile}")
print(f"ARG interrupt frequency {args.intfreq}")
print(f"ARG interrupt randomness {args.intrand}")
print(f"ARG argv {args.argv}")
print(f"ARG load address {args.loadaddr}")
print(f"ARG memsize {args.memsize}")
print(f"ARG memtrace {args.memtrace}")
print(f"ARG regtrace {args.regtrace}")
print(f"ARG cctrace {args.cctrace}")
print(f"ARG printstats {args.printstats}")
print(f"ARG verbose {args.verbose}")
print("")

seed = args.seed
numthreads = args.numthreads
intfreq = args.intfreq
zassert(intfreq > 0, "Interrupt frequency must be greater than 0")
intrand = args.intrand
progfile = args.progfile
zassert(progfile != "", "Program file must be specified")
argv = args.argv.split(",")
zassert(
    len(argv) == numthreads or len(argv) == 1,
    "argv: must be one per-thread or just one set of values for all threads",
)

loadaddr = args.loadaddr
memsize = args.memsize
random.seed(seed)

memtrace = []
if args.memtrace != "":
    for m in args.memtrace.split(","):
        memtrace.append(m)

regtrace = []
if args.regtrace != "":
    for r in args.regtrace.split(","):
        regtrace.append(r)

cctrace = args.cctrace

printstats = args.printstats
verbose = args.verbose

#
# MAIN program
#
debug = False

cpu = cpu(memsize, memtrace, regtrace, cctrace, args.solve, verbose)

# load a program
cpu.load(progfile, loadaddr)

# process list
procs = proclist()
pid = 0
stack = memsize * 1000
for t in range(numthreads):
    if len(argv) > 1:
        arg = argv[pid]
    else:
        arg = argv[0]
    procs.add(process(cpu, pid, loadaddr, stack, arg))
    stack -= 1000
    pid += 1

# get first one ready!
procs.restore()

# run it
if printstats:
    t1 = time_clock()
ic = cpu.run(procs, intfreq, intrand)

if printstats:
    t2 = time_clock()
    elapsed = t2 - t1
    rate = (ic / elapsed / 1000.0) if elapsed > 0 else 0.0
    print(f"\nSTATS:: Instructions    {ic}")
    print(f"STATS:: Emulation Rate  {rate:.2f} kinst/sec")

# use this for profiling
# import cProfile
# cProfile.run('run()')
