#!/bin/bash
while :
do
	printf "\033c" > /dev/tty1
	date > /dev/tty1
	hostname > /dev/tty1
	hostname -I | cut -d' ' -f1 | xargs printf "%s" > /dev/tty1
	sleep 1
done
