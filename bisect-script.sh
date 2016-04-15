#!/bin/bash

set -ex

git reset --hard
git clean -fdx .
cp ../linux-bad-core-scheduling-investigation/x220-kernel-config .config
export PATH=/usr/lib/ccache:$PATH
yes "" | make oldconfig
make EXTRAVERSION=-test -j5

scp arch/x86/boot/bzImage linux-bisect@llw.local:/boot/kimage-test

ssh linux-bisect@llw.local sudo reboot

sleep 35

ssh linux-bisect@llw.local /linux/test.py | grep "not bugged"
