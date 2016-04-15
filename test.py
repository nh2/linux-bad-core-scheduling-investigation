#!/usr/bin/env python3

# Requires python3 >= 3.4, and stress-ng to be installed.

import subprocess
import sys
from statistics import stdev, mean

def measure():
  time_seconds = float(str(subprocess.check_output("stress-ng -c2 --cpu-method ackermann --cpu-ops 10 | grep -o '[0-9][0-9\.]*s'", shell=True), encoding="utf-8").strip().rstrip("s"))
  return time_seconds

sample = [measure() for x in range(1,50)]
s = stdev(sample)
m = mean(sample)
relative_stdev = s / m

print("Standard deviation: ", s)
print("Relative standard deviation: ", relative_stdev)

if relative_stdev < 0.16:
  print("not bugged")
else:
  print("bugged")
  sys.exit(1)
