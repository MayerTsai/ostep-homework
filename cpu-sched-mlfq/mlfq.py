#! /usr/bin/python3

import sys
import time
import random
from optparse import OptionParser
from collections import deque


class Job:
    def __init__(self, id, start_time, run_time, io_freq, hi_pri, q_len, a_len):
        self.id = id
        self.start_time = start_time
        self.run_time = run_time
        self.io_freq = io_freq
        self.curr_pri = hi_pri
        self.ticks_left = q_len
        self.allot_left = a_len
        self.time_left = run_time
        self.doing_io = False
        self.first_run = -1
        self.end_time = -1

    def __repr__(self):
        return f"Job {self.id}"


class Simulator:
    def __init__(self, options):
        self.options = options
        self.seed = options.seed if options.seed != 0 else int(time.time())
        random.seed(self.seed)

        # Setup Queues
        self.quantum = {}
        self.allotment = {}
        if options.quantumList != "":
            lengths = [int(x) for x in options.quantumList.split(",")]
            self.num_queues = len(lengths)
            for i, length in enumerate(reversed(lengths)):
                self.quantum[i] = length
        else:
            self.num_queues = options.numQueues
            for i in range(self.num_queues):
                self.quantum[i] = options.quantum

        if options.allotmentList != "":
            lengths = [int(x) for x in options.allotmentList.split(",")]
            if len(lengths) != self.num_queues:
                print("Error: Allotment list length must match queue count.")
                sys.exit(1)
            for i, length in enumerate(reversed(lengths)):
                self.allotment[i] = length
        else:
            for i in range(self.num_queues):
                self.allotment[i] = options.allotment

        self.hi_pri = self.num_queues - 1
        self.queues = {i: deque() for i in range(self.num_queues)}
        self.io_done = {}  # time -> list of (job_id, type)
        self.jobs = {}
        self._init_jobs()

    def _init_jobs(self):
        job_cnt = 0
        if self.options.jlist != "":
            for entry in self.options.jlist.split(":"):
                parts = entry.split(",")
                if len(parts) != 3:
                    print("Error: Job list format should be start,run,io:...")
                    sys.exit(1)
                start, run, io = map(int, parts)
                self.jobs[job_cnt] = Job(
                    job_cnt,
                    start,
                    run,
                    io,
                    self.hi_pri,
                    self.quantum[self.hi_pri],
                    self.allotment[self.hi_pri],
                )
                self.io_done.setdefault(start, []).append((job_cnt, "JOB BEGINS"))
                job_cnt += 1
        else:
            for i in range(self.options.numJobs):
                run = int(random.random() * (self.options.maxlen - 1) + 1)
                io = int(random.random() * (self.options.maxio - 1) + 1)
                self.jobs[i] = Job(
                    i,
                    0,
                    run,
                    io,
                    self.hi_pri,
                    self.quantum[self.hi_pri],
                    self.allotment[self.hi_pri],
                )
                self.io_done.setdefault(0, []).append((i, "JOB BEGINS"))

    def run(self):
        print("Here is the list of inputs:")
        print(f"OPTIONS jobs {len(self.jobs)}")
        print(f"OPTIONS queues {self.num_queues}")
        for i in range(self.num_queues - 1, -1, -1):
            print(f"OPTIONS allotments for queue {i:2d} is {self.allotment[i]:3d}")
            print(f"OPTIONS quantum length for queue {i:2d} is {self.quantum[i]:3d}")
        print(f"OPTIONS boost {self.options.boost}")
        print(f"OPTIONS ioTime {self.options.ioTime}")
        print(f"OPTIONS stayAfterIO {self.options.stay}")
        print(f"OPTIONS iobump {self.options.iobump}\n\n")

        print("Job List:")
        for i, j in self.jobs.items():
            print(
                f"  Job {i:2d}: startTime {j.start_time:3d} - runTime {j.run_time:3d} - ioFreq {j.io_freq:3d}"
            )
        print("")

        if not self.options.solve:
            print("Compute the execution trace for the given workloads.")
            print("Use the -c flag to get the exact results when you are finished.\n")
            sys.exit(0)

        curr_time = 0
        finished = 0
        total = len(self.jobs)

        print("\nExecution Trace:\n")
        while finished < total:
            # 1. Priority Boost
            if (
                self.options.boost > 0
                and curr_time > 0
                and curr_time % self.options.boost == 0
            ):
                print(f"[ time {curr_time} ] BOOST ( every {self.options.boost} )")
                for q in range(self.num_queues - 1):
                    while self.queues[q]:
                        j_id = self.queues[q].popleft()
                        self.queues[self.hi_pri].append(j_id)
                for j in self.jobs.values():
                    if j.time_left > 0:
                        j.curr_pri = self.hi_pri
                        j.ticks_left = self.quantum[self.hi_pri]
                        j.allot_left = self.allotment[self.hi_pri]

            # 2. Handle I/O completions and Job arrivals
            if curr_time in self.io_done:
                for j_id, event_type in self.io_done[curr_time]:
                    j = self.jobs[j_id]
                    j.doing_io = False
                    print(f"[ time {curr_time} ] {event_type} by JOB {j_id}")
                    q_list = self.queues[j.curr_pri]
                    if not self.options.iobump or event_type == "JOB BEGINS":
                        q_list.append(j_id)
                    else:
                        q_list.appendleft(j_id)

            # 3. Select Job
            curr_q = -1
            for q in range(self.hi_pri, -1, -1):
                if self.queues[q]:
                    curr_q = q
                    break

            if curr_q == -1:
                print(f"[ time {curr_time} ] IDLE")
                curr_time += 1
                continue

            # 4. Execute Job
            j_id = self.queues[curr_q][0]
            j = self.jobs[j_id]
            if j.first_run == -1:
                j.first_run = curr_time

            j.time_left -= 1
            j.ticks_left -= 1

            print(
                f"[ time {curr_time} ] Run JOB {j_id} at PRIORITY {curr_q} "
                f"[ TICKS {j.ticks_left} ALLOT {j.allot_left} TIME {j.time_left} (of {j.run_time}) ]"
            )

            curr_time += 1

            # 5. Post-Execution Logic
            if j.time_left == 0:
                print(f"[ time {curr_time} ] FINISHED JOB {j_id}")
                finished += 1
                j.end_time = curr_time
                self.queues[curr_q].popleft()
                continue

            issued_io = False
            if j.io_freq > 0 and ((j.run_time - j.time_left) % j.io_freq == 0):
                print(f"[ time {curr_time} ] IO_START by JOB {j_id}")
                issued_io = True
                self.queues[curr_q].popleft()
                j.doing_io = True
                if self.options.stay:
                    j.ticks_left = self.quantum[curr_q]
                    j.allot_left = self.allotment[curr_q]
                future = curr_time + self.options.ioTime
                self.io_done.setdefault(future, []).append((j_id, "IO_DONE"))

            if j.ticks_left == 0:
                if not issued_io:
                    self.queues[curr_q].popleft()

                j.allot_left -= 1
                if j.allot_left == 0:
                    # Demote or reset at bottom
                    if j.curr_pri > 0:
                        j.curr_pri -= 1
                    j.ticks_left = self.quantum[j.curr_pri]
                    j.allot_left = self.allotment[j.curr_pri]
                else:
                    # Stay at level, reset quantum
                    j.ticks_left = self.quantum[j.curr_pri]

                if not issued_io:
                    self.queues[j.curr_pri].append(j_id)

        self._print_stats()

    def _print_stats(self):
        print("\nFinal statistics:")
        resp_sum = 0
        turn_sum = 0
        for i, j in self.jobs.items():
            resp = j.first_run - j.start_time
            turn = j.end_time - j.start_time
            print(
                f"  Job {i:2d}: startTime {j.start_time:3d} - response {resp:3d} - turnaround {turn:3d}"
            )
            resp_sum += resp
            turn_sum += turn
        n = len(self.jobs)
        print(
            f"\n  Avg {n-1:2d}: startTime n/a - response {resp_sum/n:.2f} - turnaround {turn_sum/n:.2f}\n"
        )


def main():
    parser = OptionParser()
    parser.add_option("-s", "--seed", help="random seed", default=0, type="int")
    parser.add_option(
        "-n", "--numQueues", help="number of queues", default=3, type="int"
    )
    parser.add_option(
        "-q", "--quantum", help="time slice length", default=10, type="int"
    )
    parser.add_option(
        "-a", "--allotment", help="allotment length", default=1, type="int"
    )
    parser.add_option(
        "-Q",
        "--quantumList",
        help="quantum length per level",
        default="",
        type="string",
    )
    parser.add_option(
        "-A", "--allotmentList", help="allotment per level", default="", type="string"
    )
    parser.add_option("-j", "--numJobs", default=3, help="number of jobs", type="int")
    parser.add_option("-m", "--maxlen", default=100, help="max run-time", type="int")
    parser.add_option("-M", "--maxio", default=10, help="max I/O frequency", type="int")
    parser.add_option(
        "-B", "--boost", default=0, help="priority boost frequency", type="int"
    )
    parser.add_option(
        "-i", "--iotime", default=5, help="I/O duration", type="int", dest="ioTime"
    )
    parser.add_option(
        "-S",
        "--stay",
        default=False,
        help="stay at priority on I/O",
        action="store_true",
    )
    parser.add_option(
        "-I",
        "--iobump",
        default=False,
        help="move to front after I/O",
        action="store_true",
    )
    parser.add_option(
        "-l", "--jlist", default="", help="job list x,y,z:...", type="string"
    )
    parser.add_option(
        "-c", help="compute answers", action="store_true", default=False, dest="solve"
    )

    options, _ = parser.parse_args()
    sim = Simulator(options)
    sim.run()


if __name__ == "__main__":
    main()
