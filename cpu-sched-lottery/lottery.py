#! /usr/bin/python3

import sys
import argparse
import random
import time

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
    "-s",
    "--seed",
    default=None,
    help="random seed",
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

seed = args.seed if args.seed is not None else int(time.time())
random.seed(seed)

# Initialize job list with clearer dictionary structure
if args.jlist:
    job_list = [
        {"id": i, "runtime": int(rt), "tickets": int(tix)}
        for i, entry in enumerate(args.jlist.split(","))
        for rt, tix in [entry.split(":")]
    ]
else:
    job_list = [
        {
            "id": i,
            "runtime": random.randint(1, args.maxlen),
            "tickets": random.randint(1, args.maxticket),
        }
        for i in range(args.jobs)
    ]

for job in job_list:
    print(
        f"\tJob {job['id']} ( length = {job['runtime']}, tickets = {job['tickets']} )"
    )

# Calculate initial totals
tick_total = sum(job["tickets"] for job in job_list)
run_total = sum(job["runtime"] for job in job_list)
print(f"\trunTotal = {run_total}, tickTotal = {tick_total}")

# Active jobs list to avoid iterating over finished processes
active_jobs = [job for job in job_list if job["runtime"] > 0]
clock = 0

while active_jobs:
    r = random.randint(0, 1000000)
    winner_ticket = r % tick_total
    winner_job = None

    if args.solve:
        print(f"Random {r} -> winning tickets {winner_ticket} of {tick_total}")

    # Find the winning job
    current_sum = 0
    for job in active_jobs:
        current_sum += job["tickets"]
        if args.solve:
            print(f"job {job['id']} cumulative tickets: {current_sum}")
        if current_sum > winner_ticket:
            winner_job = job
            break

    if args.solve:
        for job in job_list:
            status = "*" if job is winner_job else " "
            tix = job["tickets"] if job["runtime"] > 0 else "---"
            print(
                f"\t({status}job:{job['id']} timeleft:{job['runtime']} tickets:{tix} )"
            )

    if winner_job is None:
        continue

    clock += args.quantum
    winner_job["runtime"] = max(0, winner_job["runtime"] - args.quantum)

    is_done = winner_job["runtime"] == 0
    if is_done:
        tick_total -= winner_job["tickets"]
        active_jobs.remove(winner_job)

    print(
        f"-> job {winner_job['id']} is running at time {clock} {'--> done' if is_done else ''}"
    )
