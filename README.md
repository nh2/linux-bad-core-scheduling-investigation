# Bisecting a kernel scheduler regression

This is a write-up of me investigating the bug [Why does Linux's scheduler put two threads onto the same physical core on processors with HyperThreading?](http://stackoverflow.com/questions/29422073/why-does-linuxs-scheduler-put-two-threads-onto-the-same-physical-core-on-proces).

There's apparently a regression introduced between Linux v3.12
and v3.13:
On a machine with 2 cores and 4 virtual cores / HyperThreading (`Intel(R) Core(TM) i5-2520M CPU @ 2.50GHz` in a Lenovo ThinkPad X220 in my case), Linux would *sometimes* (in around 30% of the cases schedule 2 busy (100% CPU) threads onto the *same* physical core, instead of scheduling them on different physical cores, resulting in reduced performance.

To reproduce, this command showed the difference in time when
the "bad" scheduling happened (run multiple times):

```
stress-ng -c2 --cpu-method ackermann --cpu-ops 10
```

Not all machines are affected by this bug, it seems to happen
only with specific processor models.

On the linked StackOverflow page, Greg Glockner [found](http://stackoverflow.com/questions/29422073/why-does-linuxs-scheduler-put-two-threads-onto-the-same-physical-core-on-proces#comment60808046_29422073) that this bug wasn't present in Ubuntu 12.04, but present in 14.04. He investigated further and told me that the must have been introduced between v3.12 and v3.13. I could confirm that on those two kernel versions.

So I bisected the kernel to find the exact commit that caused it.

## How you can help

I'd like to create a list of all CPUs on which this bug occurs / doesn't occur.

Please run `test.py` on your machines, and file an issue containing your finding (get your CPU info from `/proc/cpuinfo`; of course you have to test with a kernel >= 2.13).

Bug present on:

* `Intel(R) Core(TM) i5-2520M CPU @ 2.50GHz`

Bug not present on:

* empty

## Making a classifier to tell whether the bug is present

As mentioned above, I could tell whether the bug is present by running `stress-ng -c2` a couple of times and looking at how quickly it finished.

I made a little Python script `test.py` that does this a couple of times on the machine in question, and inspects the relative standard deviation of the run durations; if it's large, the bug is present (due to the bi-modality of the distribution).

## Kernel setup

```
sudo adduser linux-bisect
touch /boot/kimage-test
sudo chown linux-bisect /boot/kimage-test
```

In `sudo visudo`, add an entry `linux-bisect ALL=NOPASSWD:/sbin/reboot` so that the user can reboot the machine without being asked for a password.

Setup grub config similar as described on http://moi.vonos.net/linux/bisecting-a-linux-kernel/, but since `sudo update-grub` wouldn't pick up my `50_test` file, I just edited `/boot/grub/grub.cfg` manually (see `grub-menuentry.txt`) and made sure to not run `update-grub` to not override it.

In the kernel tree:

```
git checkout v3.12
make localyesconfig
## Press Enter a lot (unfortunately one can't pipe `yes ""` into that)
cp .config ../linux-bad-core-scheduling-investigation/x220-kernel-config
```

We'll use that saved config as a starting point for `make oldconfig` for each commit that gets tested.

## First try, on the machine itself

```
cd /linux/linux  # That's where I put the kernel on the machine itself
make dist-clean
cp .test-config .config
yes "" | make oldconfig
make EXTRAVERSION=-test -j5
cp arch/x86/boot/bzImage /boot/kimage-test
```

Reboot (selecting our custom grub entry) and check (`uname -a`) that the test kernel is running and everything works.

To make my machine boot, I had to create an intitrd; for that I used `sudo update-initramfs -u -k test`. I only did this once, and used the same initrd during the entire bisection, since reproducing the bug was independent of the initrd.

(Since my partitions are typically full-disk-encrypted, I had to remove those that would block automatic booting from `/etc/crypttab` and `/etc/fstab`, and also change `/etc/uswsusp.conf` and `/etc/initramfs-tools/conf.d/resume` to tell uswsusp that it should no longer try to boot from the encrypted, not-needed-for-the-test swap partition, and generate a new initrd after changing those files - otherwise I would keep getting prompts at boot, forbidding automatic bisection.)

## The bisection

Since we have to reboot to test a new one, our bisection script has to run on a different machine, compile the kernel there, copy it over via SSH, run the test and check the result.

Use `ssh-copy-id linux-bisect@targetmachine` so that the bisection script can copy the kernel over and run the classification script without prompting.

```
git bisect good v3.12
git bisect bad v3.13
git bisect run ~/src/linux-bad-core-scheduling-investigation/bisect-script.sh
```

While this process is fully automatic in theory, I had to watch it, because sometimes Linux wouldn't boot (which I could solve by restarting the machine manually, then it just worked), or wouldn't shut down (which I could solve by force-resetting the machine while the script was waiting for it to come up -- I used Ctrl-Z to get some more time for doing that).

Note that my `bisect-script.sh` isn't perfect, e.g. it doesn't check whether the compilation or remote execution failed - to be really proper, it should also use exit code 125 to `git bisect skip` non-compiling commits, and exit code -1 to abort when the other machine can't be reached -- but luckily, all bisected commits compiled fine and I dealt with non-booting issues on the fly as described above.

## Result

Bad commit is:
`37dc6b50cee97954c4e6edcd5b1fa614b76038ee - sched: Remove unnecessary iteration over sched domains to update nr_busy_cpus`
When reverting it on top of `v3.13`, a line from this commit conflicts:
`5d4cf996`.
**That commit indicates that somebody found a performance problem, which they partially fixed but acknowledge "there may be an additional bug or a common root cause".** Maybe what I found is what they were looking for?
I resolved the conflict with https://github.com/nh2/linux/commit/627fb019acaa245768980f90a65449e6b2774e59.

## Next

I'll report this bug to LKML to find out if it can be fixed in recent kernels.
