#! /usr/bin/python3

import sys
import argparse
import time
import random

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
    help="instead of random jobs, provide a comma-separated list of run times and ticket values (e.g., 10:100,20:100 would have two jobs with run-times of 10 and 20, each with 100 tickets)",
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
    "-T",
    "--maxticket",
    default=100,
    help="maximum ticket value, if randomly assigned",
    type=int,
)
parser.add_argument(
    "-q",
    "--quantum",
    default=1,
    help="length of time slice",
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
random.seed(int(time.time()))

if args.jlist:
    joblist = [
        [i, int(rt), int(tix)]
        for i, entry in enumerate(args.jlist.split(","))
        for rt, tix in [entry.split(":")]
    ]
else:
    joblist = [
        [i, random.randint(1, args.maxlen), random.randint(1, args.maxticket)]
        for i in range(args.jobs)
    ]

for jobnum, runtime, tickets in joblist:
    print(f"  Job {jobnum} ( length = {runtime}, tickets = {tickets} )")

runTotal = sum(job[1] for job in joblist)
tickTotal = sum(job[2] for job in joblist)
print("\n")

if not args.solve:
    print("Here is the set of random numbers you will need (at most):")
    for _ in range(runTotal):
        print(f"Random {random.randint(0, 1000000)}")

if args.solve:
    print("** Solutions **\n")

    jobs = len(joblist)
    clock = 0
    while True:
        r = random.randint(0, 1000000)
        winner = r % tickTotal

        current = 0
        for job, runtime, tickets in joblist:
            current += tickets
            if current > winner:
                wjob, wrun, wtix = (job, runtime, tickets)
                break

        print(f"Random {r} -> Winning ticket {winner} (of {tickTotal}) -> Run {wjob}")

        print("  Jobs:")
        job_stats = []
        for job, runtime, tickets in joblist:
            wstr = "*" if wjob == job else " "
            tstr = tickets if runtime > 0 else "---"
            job_stats.append(f" ({wstr} job:{job} timeleft:{runtime} tix:{tstr} ) ")
        print("".join(job_stats))

        # now do the accounting
        wrun = max(0, wrun - args.quantum)
        clock += args.quantum

        # job completed!
        if wrun == 0:
            print(f"--> JOB {wjob} DONE at time {clock}")
            tickTotal -= wtix
            wtix = 0
            jobs -= 1

        # update job list
        joblist[wjob] = [wjob, wrun, wtix]

        if jobs == 0:
            print("")
            break
