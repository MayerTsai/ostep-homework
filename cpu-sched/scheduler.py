#! /usr/bin/python3

import sys
import argparse
import time
import random
from collections import deque

parser = argparse.ArgumentParser()

parser.add_argument(
    "-j",
    "--jobs",
    default=3,
    help="number of jobs in the system",
    type=int,
)
parser.add_argument(
    "-l",
    "--jlist",
    default="",
    help="instead of random jobs, provide a comma-separated list of run times",
    type=str,
)
parser.add_argument(
    "-m",
    "--maxlen",
    default=10,
    help="max length of job",
    type=int,
)
parser.add_argument(
    "-p",
    "--policy",
    default="FIFO",
    help="sched policy to use: SJF, FIFO, RR",
    type=str,
)
parser.add_argument(
    "-q",
    "--quantum",
    help="length of time slice for RR policy",
    default=1,
    type=int,
)
parser.add_argument(
    "-c",
    "--compute",
    help="compute answers for me",
    action="store_true",
    default=False,
    dest="solve",
)

args = parser.parse_args()

if args.policy not in ["FIFO", "SJF", "RR"]:
    print(f"Error: Policy {args.policy} is not available.")
    sys.exit(1)

random.seed(int(time.time()))

joblist = []
if not args.jlist:
    joblist = [[i, random.randint(1, args.maxlen)] for i in range(args.jobs)]
else:
    joblist = [[i, float(rt)] for i, rt in enumerate(args.jlist.split(","))]

for jobnum, runtime in joblist:
    print(f"  Job {jobnum} ( length = {runtime} )")
print("\n")

if args.solve:
    print("** Solutions **\n")
    if args.policy == "SJF":
        joblist.sort(key=lambda x: x[1])
        args.policy = "FIFO"

    if args.policy == "FIFO":
        thetime, n = 0.0, len(joblist)
        responses, turnarounds, waits = [], [], []

        print("Execution trace:")
        for job_id, runtime in joblist:
            print(
                f"  [ time {int(thetime):3d} ] Run job {job_id} for {runtime:.2f} secs ( DONE at {thetime + runtime:.2f} )"
            )
            responses.append(thetime)
            turnarounds.append(thetime + runtime)
            waits.append(thetime)
            thetime += runtime

        print("\nFinal statistics:")
        for i, (job_id, _) in enumerate(joblist):
            print(
                f"  Job {job_id:3d} -- Response: {responses[i]:3.2f}  Turnaround {turnarounds[i]:3.2f}  Wait {waits[i]:3.2f}"
            )

        print(
            f"\n  Average -- Response: {sum(responses)/n:3.2f}  Turnaround {sum(turnarounds)/n:3.2f}  Wait {sum(waits)/n:3.2f}\n"
        )

    if args.policy == "RR":
        print("Execution trace:")
        n = len(joblist)
        turnaround, response, lastran, wait = (
            [0.0] * n,
            [-1.0] * n,
            [0.0] * n,
            [0.0] * n,
        )
        quantum = float(args.quantum)

        runlist = deque([list(j) for j in joblist])
        thetime, finished = 0.0, 0
        while finished < n:
            job = runlist.popleft()
            jobnum, runtime = job[0], float(job[1])

            if response[jobnum] == -1.0:
                response[jobnum] = thetime
            wait[jobnum] += thetime - lastran[jobnum]

            if runtime > quantum:
                ranfor = quantum
                print(
                    f"  [ time {int(thetime):3d} ] Run job {jobnum:3d} for {ranfor:.2f} secs"
                )
                runlist.append([jobnum, runtime - quantum])
            else:
                ranfor = runtime
                print(
                    f"  [ time {int(thetime):3d} ] Run job {jobnum:3d} for {ranfor:.2f} secs ( DONE at {thetime + ranfor:.2f} )"
                )
                turnaround[jobnum] = thetime + ranfor
                finished += 1

            thetime += ranfor
            lastran[jobnum] = thetime

        print("\nFinal statistics:")
        res_sum, turn_sum, wait_sum = sum(response), sum(turnaround), sum(wait)
        for i in range(n):
            print(
                f"  Job {i:3d} -- Response: {response[i]:3.2f}  Turnaround {turnaround[i]:3.2f}  Wait {wait[i]:3.2f}"
            )

        print(
            f"\n  Average -- Response: {res_sum/n:3.2f}  Turnaround {turn_sum/n:3.2f}  Wait {wait_sum/n:3.2f}\n"
        )

else:
    print("Compute the turnaround time, response time, and wait time for each job.")
    print("When you are done, run this program again, with the same arguments,")
    print("but with -c, which will thus provide you with the answers. You can use")
    print("-s <somenumber> or your own job list (-l 10,15,20 for example)")
    print("to generate different problems for yourself.")
    print("")
