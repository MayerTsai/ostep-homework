#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#include <sys/time.h>

// Simple routine to return absolute time (in seconds).
double Time_GetSeconds()
{
    struct timeval t;
    int rc = gettimeofday(&t, NULL);
    assert(rc == 0);
    return (double)((double)t.tv_sec + (double)t.tv_usec / 1e6);
}

// Program that allocates an array of ints of certain size,
// and then proceeds to update each int in a loop, forever.
int main(int argc, char *argv[])
{
    if (argc != 2)
    {
        fprintf(stderr, "usage: ./mem <memory (MB)>\n");
        exit(1);
    }
    long long int size = atoll(argv[1]);
    if (size <= 0)
    {
        fprintf(stderr, "error: memory size must be a positive integer\n");
        exit(1);
    }
    long long int size_in_bytes = size * 1024 * 1024;

    printf("allocating %lld bytes (%lld MB)\n", size_in_bytes, size);

    // the big memory allocation happens here
    int *x = malloc(size_in_bytes);
    if (x == NULL)
    {
        fprintf(stderr, "memory allocation failed\n");
        exit(1);
    }

    long long int num_ints = size_in_bytes / (long long int)sizeof(int);
    printf("  number of integers(%zu) in array: %lld\n", sizeof(int), num_ints);

    // now the main loop: each time through, touch each integer
    // (and increment its value by 1).
    double time_since_last_print = 0.2;
    double t = Time_GetSeconds();
    int loop_count = 0;
    while (1)
    {
        // Using a tight inner loop allows the compiler to vectorize the increments
        // and removes the branching overhead from the hot path.
        for (long long int j = 0; j < num_ints; j++)
            x[j]++;
        double current_time = Time_GetSeconds();
        double delta_time = current_time - t;

        time_since_last_print += delta_time;
        if (time_since_last_print >= 0.2)
        { // only print every .2 seconds
            printf("loop %d in %.2f ms (bandwidth: %.2f MB/s)\n",
                   loop_count, 1000 * delta_time, (double)size / delta_time);
            time_since_last_print = 0;
        }
        t = current_time;
        loop_count++;
    }

    return 0;
}
