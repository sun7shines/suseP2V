# -*- coding: utf-8 -*-

import subprocess
import platform
import glob
import os, string, stat, sys
import shutil
import signal
import os.path
from errno import *
import warnings
import subprocess

import re
import threading
import iutil

import syslog
import traceback
import time
import commands

def create_driver_src(hostinfo):

    if not os.path.exists(hostinfo):
        print 'not support: %s' % (hostinfo)
        return False

    cmd = 'rm -rf /tmp/%s' % (hostinfo)
    os.system(cmd)
    if not os.path.exists(hostinfo):
        print 'ko files not exists'
        return False

    cmd = 'cp -rf %s /tmp/%s' % (hostinfo,hostinfo)
    os.system(cmd)
    return True

def create_initrd_src(kernel_version,uuid):

    tmp_path = '/tmp/initrd-xxx%s/' % (uuid)
    cmd = 'rm -rf '+tmp_path
    os.system(cmd)
    cmd = 'mkdir -p '+tmp_path
    os.system(cmd)
    initrd_path = 'initrd-'+kernel_version
    cmd = 'cp /boot/%s %s' % (initrd_path,tmp_path)
    os.system(cmd)

    return tmp_path,initrd_path

def create_initrd_env(initrd_path):

    cmd = 'mv %s %s.gz' % (initrd_path,initrd_path)
    os.system(cmd)
    cmd = 'gunzip %s.gz' % (initrd_path)
    os.system(cmd)
    cmd = 'cpio -idmv < %s' % (initrd_path)
    os.system(cmd)
    cmd = 'rm -f %s '% (initrd_path)
    os.system(cmd)
    cmd = 'cp /sbin/depmod sbin/'
    os.system(cmd)

def create_initrd_dst(initrd_path,uuid):

    cmd = 'rm -f /tmp/%s' % (initrd_path)
    os.system(cmd)
    cmd = 'find . | cpio -o -H newc | gzip -9 > /tmp/%s__%s' % (initrd_path,uuid)
    os.system(cmd)
    cmd = 'rm -f /boot/%s ' % (initrd_path)
    os.system(cmd)
    cmd = 'cp /tmp/%s__%s /boot/%s' % (initrd_path,uuid,initrd_path)
    os.system(cmd)

def cp_drivers(hostinfo):
    newmods = []

    cmd = "find /tmp/%s -name '*.ko' " % (hostinfo)
    flag,output = commands.getstatusoutput(cmd)
    if flag:
         return False,[]

    for x in output.split('\n'):
        if not x:
            continue
        src = x.strip()
        dst = '/'.join(src.split('/')[3:])  
        dstdir = '/'.join(src.split('/')[3:-1])
        if not os.path.exists(dst):
            cmd ='mkdir -p '+dstdir
            os.system(cmd)
            cmd = 'cp  %s %s' % (src,dst)
            os.system(cmd)
            print cmd
            cmd = 'insmod '+'/'+dst
            newmods.append(cmd+'\n')
            print cmd

    return True,newmods

def update_init_script(newmods):

    cmd = 'cp init init.baxxxx'
    os.system(cmd)

    fn = 'init'
    f = open(fn)
    lines = f.readlines()
    f.close()
    newlines = []

    flag = False
    for x in lines:
        newlines.append(x)
        if (x.startswith('modprobe') or x.startswith('insmod') )  and not flag:
            newlines.extend(newmods)
            flag = True

    f = open('init','w')
    f.writelines(newlines)
    f.close()


def update_initrd(kernel_version,machine,uuid):

    hostinfo = kernel_version+machine

    flag = create_driver_src(hostinfo)
    if not flag:
        return False
 
    tmp_path,initrd_path = create_initrd_src(kernel_version,uuid)

    os.chdir(tmp_path)

    create_initrd_env(initrd_path)
    flag,newmods = cp_drivers(hostinfo)
    if flag and newmods:
        update_init_script(newmods)

    rc = iutil.execWithRedirect("/sbin/depmod",
                           [ "-a"],
                           stdout = "/dev/null", stderr = "/dev/null",
                           root = tmp_path)
    if rc:
        print 'depmod failed'
        return 
    os.chdir(tmp_path)

    create_initrd_dst(initrd_path,uuid)

def get_device(line):

    dev1 = line.split()[0]
    cmd  = 'ls -l '+dev1
    flag,output = commands.getstatusoutput(cmd)
    if flag:
        return line
    dev2 = '/dev/'+output.split()[-1].split('/')[-1]
    return line.replace(dev1,dev2,1)

def update_fstab():
    
    # standard grub link
    '''
    pci-0000:00:01.1-scsi-1:0:0:0 -> ../../sr0
    pci-0000:00:08.0-virtio-pci-virtio2 -> ../../vda
    pci-0000:00:08.0-virtio-pci-virtio2-part1 -> ../../vda1
    pci-0000:00:08.0-virtio-pci-virtio2-part2 -> ../../vda2
    pci-0000:00:08.0-virtio-pci-virtio2-part3 -> ../../vda3
    '''

    f = open('/etc/fstab')    
    lines = f.readlines() 
    f.close()
    newlines = []
    for line in lines:
        if line.startswith('/dev/disk/by-id') or line.startswith('/dev/disk/by-path'):
            newline = get_device(line) 
            newlines.append(newline)
        else:
            newlines.append(line)
    f = open('/etc/fstab','w')
    f.writelines(newlines)
    f.close()

def get_root_device(line,rootdev):

    dev1 = rootdev.strip().split('=')[1]
    cmd  = 'ls -l '+dev1
    flag,output = commands.getstatusoutput(cmd)
    if flag:
        return line
    if dev1.startswith('/dev/disk/by-id') or dev1.startswith('/dev/disk/by-path'):
        dev2 = '/dev/'+output.split()[-1].split('/')[-1]
        line = line.replace(dev1,dev2,1)
    return line

def update_grub():

    f= open('/boot/grub/menu.lst')
    lines = f.readlines()
    f.close()
    newlines = []
    for line in lines:
        append_flag = False
        x = line.strip()
        if x.startswith('kernel'):
            items = x.split()
            if len(items) >=3 and items[2].strip().startswith('root'):
                newline = get_root_device(line,items[2])
                newlines.append(newline)
                append_flag = True
        if not append_flag:
            newlines.append(line)
                 
    f = open('/boot/grub/menu.lst','w')
    f.writelines(newlines)
    f.close()

def sys_backup(backupfiles):

    uuid = str(time.time())
    backupdir = '/var/syssbackup'+uuid

    cmd = 'mkdir -p '+backupdir
    os.system(cmd)     

    for key,src in backupfiles.items():
        dst = backupdir+'/'+key
        if not os.path.exists(dst):
            cmd = 'cp %s %s' % (src,dst) 
            os.system(cmd)

    fn = 'sysbackdir'
    f = open(fn,'w')
    f.writelines([backupdir])
    f.close()
    return uuid 


def get_backupfiles(kernel_version):

    initrdpath = 'initrd-%s' % (kernel_version)
    backupfiles = {'menu.lst':'/boot/grub/menu.lst','fstab':'/etc/fstab',initrdpath:'/boot/'+initrdpath}
    return backupfiles

def main():
    kernel_version = platform.uname()[2]
    machine = platform.uname()[-2]
    hostinfo = kernel_version+machine 

    if not os.path.exists(hostinfo):
        print 'not support kernel: '+kernel_version
        return

    backupfiles = get_backupfiles(kernel_version)
    uuid = sys_backup(backupfiles)

    
    update_initrd(kernel_version,machine,uuid)
    update_fstab()
    update_grub()

if __name__ == '__main__':
    main()


