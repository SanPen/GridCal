# Suppose you have a collection of tasks, which in this example I'll assume is just running a function f.
# If these tasks are completely separate and independent the most then you can parallelize them easily.
# In this gist I'll show the simplest possible way to do this using mpi4py.
# There are better ways to do this, in particular if the tasks vary significantly in time taken to run.

import mpi4py.MPI


def f(i):
    "A fake task - in this case let just open a file and write a number to it"
    # open file with name based on task number
    f = open("%d.txt" % i, "w")
    # write some info to it
    for k in range(1000000):
        f.write("%d * 10 = %d\n" % (i, 10 * i))
    # close the file
    f.close()


# A list of all the tasks to do.  In your case you will probably build this task list in a more complex way.
# You don't even need to build it in advance for this approach to work
task_list = range(10)

# main program loop.  This is the unparallelized verion, for comparison
# for task in task_list:
#     f(task)

# And now moving on the parallel version

# mpi4py has the notion of a "communicator" - a collection of processors
# all operating together, usually on the same program.  Each processor
# in the communicator is identified by a number, its rank,  We'll use that
# number to split the tasks

# find out which number processor this particular instance is,
# and how many there are in total
rank = mpi4py.MPI.COMM_WORLD.Get_rank()
size = mpi4py.MPI.COMM_WORLD.Get_size()

# parallelized version
# the enumerate function gives us a number i in addition
# to the task.  (In this specific case i is the same as task!  But that's
# not true usually)
for i, task in enumerate(task_list):
    # This is how we split up the jobs.
    # The % sign is a modulus, and the "continue" means
    # "skip the rest of this bit and go to the next time
    # through the loop"
    # If we had e.g. 4 processors, this would mean
    # that proc zero did tasks 0, 4, 8, 12, 16, ...
    # and proc one did tasks 1, 5, 9, 13, 17, ...
    # and do on.
    if i % size != rank:
        continue
    print("Task number %d (i=%d) being done by processor %d of %d" % (i, task, rank, size))
    f(task)
