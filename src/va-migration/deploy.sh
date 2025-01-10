#!/bin/bash

mkdir -p deploy/ && rm -rf deploy/*
cp -a resources/va.sgdisk deploy/
cp -a output/img/initramfs-convert.img deploy/
cp -a output/img/vmlinuz-convert deploy/
cp -a upgrade.sh deploy/
