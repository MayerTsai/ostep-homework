#! /usr/bin/env python

import random
import sys
import time
from argparse import ArgumentParser


# minimum unit of transfer to RAID
BLOCKSIZE = 4096


def convert(size):
    size = str(size).lower()
    multipliers = {"k": 1024, "m": 1024 * 1024, "g": 1024 * 1024 * 1024}
    if size and size[-1] in multipliers:
        return int(size[:-1]) * multipliers[size[-1]]
    return int(size)


class disk:
    def __init__(self, seekTime=10, xferTime=0.1, queueLen=8):
        # these are both in milliseconds
        # seek is the time to seek (simple constant amount)
        # transfer is the time to read one block
        self.seekTime = seekTime
        self.xferTime = xferTime

        # length of scheduling queue
        self.queueLen = queueLen

        # current location: make it negative so that whatever
        # the first read is, it causes a seek
        self.currAddr = -10000

        # queue
        self.queue = []

        # disk geometry
        self.numTracks = 100
        self.blocksPerTrack = 100
        self.blocksPerDisk = self.numTracks * self.blocksPerTrack

        # stats
        self.countIO = 0
        self.countSeq = 0
        self.countNseq = 0
        self.countRand = 0
        self.utilTime = 0

    def stats(self):
        return (
            self.countIO,
            self.countSeq,
            self.countNseq,
            self.countRand,
            self.utilTime,
        )

    def enqueue(self, addr):
        assert addr < self.blocksPerDisk
        self.countIO += 1

        # check if this is on the same track, or a different one
        currTrack = self.currAddr // self.blocksPerTrack
        newTrack = addr // self.blocksPerTrack
        diff = abs(addr - self.currAddr)

        # if on the same track...
        if currTrack == newTrack:
            if diff == 1:
                self.countSeq += 1
            else:
                self.countNseq += 1
            self.utilTime += diff * self.xferTime
        else:
            self.countRand += 1
            self.utilTime += self.seekTime + self.xferTime
        self.currAddr = addr

    def go(self):
        return self.utilTime


class raid:
    def __init__(
        self,
        chunkSize="4k",
        numDisks=4,
        level=0,
        timing=False,
        reverse=False,
        solve=False,
        raid5type="LS",
    ):
        chunkSize = int(convert(chunkSize))
        self.chunkSize = int(chunkSize / BLOCKSIZE)
        self.numDisks = numDisks
        self.raidLevel = level
        self.timing = timing
        self.reverse = reverse
        self.solve = solve
        self.raid5type = raid5type

        if (chunkSize % BLOCKSIZE) != 0:
            print(
                f"chunksize ({chunkSize}) must be multiple of blocksize ({BLOCKSIZE}): {self.chunkSize % BLOCKSIZE}"
            )
            sys.exit(1)
        if self.raidLevel == 1 and numDisks % 2 != 0:
            print(f"raid1: disks ({numDisks}) must be a multiple of two")
            sys.exit(1)

        if self.raidLevel in [4, 5]:
            self.blocksInStripe = (self.numDisks - 1) * self.chunkSize
            self.pdisk = self.numDisks - 1 if self.raidLevel == 4 else -1

        self.disks = [disk() for _ in range(self.numDisks)]

    # print per-disk stats
    def stats(self, totalTime):
        for d in range(self.numDisks):
            s = self.disks[d].stats()
            util = (100.0 * s[4] / totalTime) if totalTime > 0 else 0.0
            # Adjust spacing for alignment based on utility value
            spacing = "  " if s[4] == totalTime or s[4] != 0 else "   "
            print(
                f"disk:{d}  busy:{spacing}{util:5.2f}  I/Os: {s[0]:5d} (sequential:{s[1]} nearly:{s[2]} random:{s[3]})"
            )

    # global enqueue function
    def enqueue(self, addr, size, isWrite):
        # should we print out the logical operation?
        if self.timing == False:
            if self.solve or self.reverse == False:
                op = "WRITE to " if isWrite else "READ from"
                print(f"LOGICAL {op} addr:{addr} size:{size * BLOCKSIZE}")
                if self.solve == False:
                    print("  Physical reads/writes?\n")
            else:
                print("LOGICAL OPERATION is ?")

        # should we print out the physical operations?
        self.printPhysical = (not self.timing) and (self.solve or self.reverse)

        if self.raidLevel == 0:
            self.enqueue0(addr, size, isWrite)
        elif self.raidLevel == 1:
            self.enqueue1(addr, size, isWrite)
        elif self.raidLevel == 4 or self.raidLevel == 5:
            self.enqueue45(addr, size, isWrite)

    # process disk workloads one at a time, returning final completion time
    def go(self):
        tmax = 0
        for d in range(self.numDisks):
            t = self.disks[d].go()
            if t > tmax:
                tmax = t
        return tmax

    # helper functions
    def doSingleRead(self, disk, off, doNewline=False):
        if self.printPhysical:
            print(f"  read  [disk {disk}, offset {off}]  ", end="")
            if doNewline:
                print("")
        self.disks[disk].enqueue(off)

    def doSingleWrite(self, disk, off, doNewline=False):
        if self.printPhysical:
            print(f"  write [disk {disk}, offset {off}]  ", end="")
            if doNewline:
                print("")
        self.disks[disk].enqueue(off)

    #
    # mapping for RAID 0 (striping)
    #
    def bmap0(self, bnum):
        cnum = bnum // self.chunkSize
        coff = bnum % self.chunkSize
        return (
            cnum % self.numDisks,
            (cnum // self.numDisks) * self.chunkSize + coff,
        )

    def enqueue0(self, addr, size, isWrite):
        # can ignore isWrite, as I/O pattern is the same for striping
        for b in range(addr, addr + size):
            (disk, off) = self.bmap0(b)
            if isWrite:
                self.doSingleWrite(disk, off, True)
            else:
                self.doSingleRead(disk, off, True)
        if self.timing == False and self.printPhysical:
            print("")

    #
    # mapping for RAID 1 (mirroring)
    #
    def bmap1(self, bnum):
        cnum = bnum // self.chunkSize
        coff = bnum % self.chunkSize
        disk = 2 * (cnum % (self.numDisks // 2))
        return (
            disk,
            disk + 1,
            (cnum // (self.numDisks // 2)) * self.chunkSize + coff,
        )

    def enqueue1(self, addr, size, isWrite):
        for b in range(addr, addr + size):
            (disk1, disk2, off) = self.bmap1(b)
            # print 'enqueue:', addr, size, '-->', m
            if isWrite:
                self.doSingleWrite(disk1, off, False)
                self.doSingleWrite(disk2, off, True)
            else:
                # the raid-1 read balancing algorithm is here;
                # could be something more intelligent --
                # instead, it is just based on the disk offset
                # to produce something easily reproducible
                if off % 2 == 0:
                    self.doSingleRead(disk1, off, True)
                else:
                    self.doSingleRead(disk2, off, True)
        if self.timing == False and self.printPhysical:
            print("")

    #
    # mapping for RAID 4 (parity disk)
    #
    # assumes (for now) that there is just one parity disk
    #
    def bmap4(self, bnum):
        cnum = bnum // self.chunkSize
        coff = bnum % self.chunkSize
        return (
            cnum % (self.numDisks - 1),
            (cnum // (self.numDisks - 1)) * self.chunkSize + coff,
        )

    def pmap4(self, snum):
        return self.pdisk

    #
    # mapping for RAID 5 (rotated parity)
    #
    def __bmap5(self, bnum):
        cnum = bnum // self.chunkSize
        coff = bnum % self.chunkSize
        ddsk = cnum // (self.numDisks - 1)
        doff = ddsk * self.chunkSize + coff
        disk = cnum % (self.numDisks - 1)
        col = ddsk % self.numDisks
        pdisk = (self.numDisks - 1) - col

        # supports left-asymmetric and left-symmetric layouts
        if self.raid5type == "LA":
            if disk >= pdisk:
                disk += 1
        elif self.raid5type == "LS":
            disk = (disk - col) % (self.numDisks)
        else:
            print(f"error: no such RAID scheme: {self.raid5type}")
            sys.exit(1)
        assert disk != pdisk
        return (disk, pdisk, doff)

    # Shared address mapping logic for RAID 5
    def bmap5(self, bnum):
        (disk, pdisk, off) = self.__bmap5(bnum)
        return (disk, off)

    # this too is lame (redundant call to __bmap5 is serious programmer laziness)
    def pmap5(self, snum):
        (disk, pdisk, off) = self.__bmap5(snum * self.blocksInStripe)
        return pdisk

    # RAID 4/5 helper routine to write out some blocks in a stripe
    def doPartialWrite(self, stripe, begin, end, bmap, pmap):
        numWrites = end - begin
        pdisk = pmap(stripe)
        if (numWrites + 1) <= (self.blocksInStripe - numWrites):
            # SUBTRACTIVE PARITY
            # print 'SUBTRACTIVE'
            offList = []
            for voff in range(begin, end):
                (disk, off) = bmap(voff)
                self.doSingleRead(disk, off)
                if off not in offList:
                    offList.append(off)
            for i in range(len(offList)):
                self.doSingleRead(pdisk, offList[i], i == (len(offList) - 1))
        else:
            # ADDITIVE PARITY
            # print 'ADDITIVE'
            stripeBegin = stripe * self.blocksInStripe
            stripeEnd = stripeBegin + self.blocksInStripe
            for voff in range(stripeBegin, begin):
                (disk, off) = bmap(voff)
                self.doSingleRead(
                    disk, off, (voff == (begin - 1)) and (end == stripeEnd)
                )
            for voff in range(end, stripeEnd):
                (disk, off) = bmap(voff)
                self.doSingleRead(disk, off, voff == (stripeEnd - 1))

        # WRITES: same for additive or subtractive parity
        offList = []
        for voff in range(begin, end):
            (disk, off) = bmap(voff)
            self.doSingleWrite(disk, off)
            if off not in offList:
                offList.append(off)
        for i in range(len(offList)):
            self.doSingleWrite(pdisk, offList[i], i == (len(offList) - 1))

    # RAID 4/5 enqueue routine
    def enqueue45(self, addr, size, isWrite):
        if self.raidLevel == 4:
            (bmap, pmap) = (self.bmap4, self.pmap4)
        elif self.raidLevel == 5:
            (bmap, pmap) = (self.bmap5, self.pmap5)

        if isWrite == False:
            for b in range(addr, addr + size):
                (disk, off) = bmap(b)
                self.doSingleRead(disk, off)
        else:
            # process the write request, one stripe at a time
            initStripe = addr // self.blocksInStripe
            finalStripe = (addr + size - 1) // self.blocksInStripe

            left = size
            begin = addr
            for stripe in range(initStripe, finalStripe + 1):
                endOfStripe = (stripe * self.blocksInStripe) + self.blocksInStripe

                if left >= self.blocksInStripe:
                    end = begin + self.blocksInStripe
                else:
                    end = begin + left

                if end >= endOfStripe:
                    end = endOfStripe

                self.doPartialWrite(stripe, begin, end, bmap, pmap)

                left -= end - begin
                begin = end

        # for all cases, print this for pretty-ness in mapping mode
        if self.timing == False and self.printPhysical:
            print("")


#
# main program
#
parser = ArgumentParser()
parser.add_argument("-s", "--seed", default=0, help="the random seed", type=int)
parser.add_argument(
    "-D", "--numDisks", default=4, help="number of disks in RAID", type=int
)
parser.add_argument("-C", "--chunkSize", default="4k", help="chunk size of the RAID")
parser.add_argument(
    "-n", "--numRequests", default=10, help="number of requests to simulate", type=int
)
parser.add_argument(
    "-S", "--reqSize", default="4k", help="size of requests", dest="size"
)
parser.add_argument(
    "-W", "--workload", default="rand", help='either "rand" or "seq" workloads'
)
parser.add_argument(
    "-w",
    "--writeFrac",
    default=0,
    help="write fraction (100->all writes, 0->all reads)",
    type=int,
)
parser.add_argument(
    "-R", "--randRange", default=10000, help="range of requests", type=int, dest="range"
)
parser.add_argument(
    "-L", "--level", default=0, help="RAID level (0, 1, 4, 5)", type=int
)
parser.add_argument(
    "-5",
    "--raid5",
    default="LS",
    help='RAID-5 left-symmetric "LS" or left-asym "LA"',
    dest="raid5type",
)
parser.add_argument(
    "-r",
    "--reverse",
    default=False,
    help="instead of showing logical ops, show physical",
    action="store_true",
)
parser.add_argument(
    "-t",
    "--timing",
    default=False,
    help="use timing mode, instead of mapping mode",
    action="store_true",
)
parser.add_argument(
    "-c",
    "--compute",
    default=False,
    help="compute answers for me",
    action="store_true",
    dest="solve",
)

options = parser.parse_args()

print(f"ARG blockSize {BLOCKSIZE}")
seed = int(time.time()) if options.seed == 0 else options.seed
print(f"ARG seed {seed}")
print("ARG numDisks", options.numDisks)
print("ARG chunkSize", options.chunkSize)
print("ARG numRequests", options.numRequests)
print("ARG reqSize", options.size)
print("ARG workload", options.workload)
print("ARG writeFrac", options.writeFrac)
print("ARG randRange", options.range)
print("ARG level", options.level)
print("ARG raid5", options.raid5type)
print("ARG reverse", options.reverse)
print("ARG timing", options.timing)
print("")

writeFrac = options.writeFrac / 100.0
assert writeFrac >= 0.0 and writeFrac <= 1.0

random.seed(seed)

size = convert(options.size)
if size % BLOCKSIZE != 0:
    print(f"error: request size ({size}) must be a multiple of BLOCKSIZE ({BLOCKSIZE})")
    sys.exit(1)
size = size // BLOCKSIZE

if (
    options.workload == "seq"
    or options.workload == "s"
    or options.workload == "sequential"
):
    workloadIsSequential = True
elif (
    options.workload == "rand"
    or options.workload == "r"
    or options.workload == "random"
):
    workloadIsSequential = False
else:
    print("error: workload must be either r/rand/random or s/seq/sequential")
    sys.exit(1)

assert options.level in [0, 1, 4, 5]
if options.level != 0 and options.numDisks < 2:
    print("RAID-4 and RAID-5 need more than 1 disk")
    sys.exit(1)

if options.level == 5 and options.raid5type != "LA" and options.raid5type != "LS":
    print(f"Only two types of RAID-5 supported: LA and LS ({options.raid5type} is not)")
    sys.exit(1)

# instantiate RAID
r = raid(
    chunkSize=options.chunkSize,
    numDisks=options.numDisks,
    level=options.level,
    timing=options.timing,
    reverse=options.reverse,
    solve=options.solve,
    raid5type=options.raid5type,
)

# generate requests
off = 0
for i in range(options.numRequests):
    if workloadIsSequential == True:
        blk = off
        off += size
    else:
        blk = int(random.random() * options.range)

    isWrite = random.random() < writeFrac
    print(blk, size)
    r.enqueue(blk, size, isWrite)

# process requests
t = r.go()

# print out some final info, if needed
if options.timing == False:
    print("")
    sys.exit(0)

if options.solve:
    print("")
    r.stats(t)
    print("")
    print("STAT totalTime", t)
    print("")
else:
    print("")
    print("Estimate how long the workload should take to complete.")
    print("- Roughly how many requests should each disk receive?")
    print("- How many requests are random, how many sequential?")
    print("")
