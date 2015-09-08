
import platform
import sys
import commands
import os
import os.path


def get_mod_info(driver):

    modpath = ''
    deplist = []
    cmd = "modinfo %s | egrep 'filename|depends' " %(driver)
    flag,output = commands.getstatusoutput(cmd)
    if flag:
        return {} 

    for x in output.split('\n'):
        if not x.strip():
            continue
        line = x.strip()
        if line.startswith('filename'):
            modpath = line.split(':')[1].strip()
        if line.startswith('depends'):
            depends = line.split(':')[1].strip()
            if depends:
                deplist = depends.split(',')

    return {'filename':modpath,'depends':deplist}

def cp_file(src,dst):

    if not src:
        return

    filename = src[1:]
    dstpath = dst+'/'+filename
    if os.path.exists(dst+'/'+filename):
        return
    dstdir = ('/').join(dstpath.strip().split('/')[:-1])
    if not os.path.exists(dstdir):
        cmd = 'mkdir -p '+dstdir
        os.system(cmd)
    cmd = 'cp %s %s' % (src,dstpath)
    print cmd
    os.system(cmd)

def cp_file_new(filename,src,dst):

    if not filename:
        return
    if not dst.endswith('/'):
        dst = dst+'/'

    dstpath = filename.replace(src,dst,1)
    if os.path.exists(dstpath):
        return
    dstdir = ('/').join(dstpath.strip().split('/')[:-1])
    if not os.path.exists(dstdir):
        cmd = 'mkdir -p '+dstdir
        os.system(cmd)
    cmd = 'cp %s %s' % (filename,dstpath)
    print cmd
    os.system(cmd)

def get_all(driver):
    dlist = []
    dlist.append(driver)

    while len(dlist) > 0:
        x = dlist[0]
        info = get_mod_info(x)
        dlist.remove(x)
        if not info:
            continue
        dlist.extend(info.get('depends'))
        cp_file(info.get('filename'),platform.uname()[2]+platform.uname()[-2])

def get_pci_drivers():
    dlist = []
    cmd = 'lspci -k'
    flag,output = commands.getstatusoutput(cmd)
    if  flag:
        return []
    for x in output.split('\n'):
        line = x.strip()
        if not line.strip():
            continue
        if line.startswith('Kernel modules'):
            dlist.append(line.strip().split(':')[1].strip())
        if line.startswith('Kernel driver in use'):
            dlist.append(line.strip().split(':')[1].strip())
    return dlist

def create_initrd_src(kernel_version,uuid):

    tmp_path = '/tmp/initrd-as-src%s/' % (uuid)
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
    commands.getstatusoutput(cmd)
    cmd = 'rm -f %s '% (initrd_path)
    os.system(cmd)
    cmd = 'cp /sbin/depmod sbin/'
    os.system(cmd)

def find_initrd_drivers(tmp_path):

    cmd = "find %s -name '*.ko'" % (tmp_path)
    flag,output = commands.getstatusoutput(cmd)
    if flag:
        return
    return output.split('\n')

def get_initrd_drivers():
    import time
    uuid = str(time.time())
    kernel_version = platform.uname()[2]
    tmp_path,initrd_path = create_initrd_src(kernel_version,uuid)
    cwd = os.getcwd()
    os.chdir(tmp_path)
    create_initrd_env(initrd_path)
    os.chdir(cwd)

    for filename in find_initrd_drivers(tmp_path):
        cp_file_new(filename,tmp_path,platform.uname()[2]+platform.uname()[-2])

def main():
    for driver in get_pci_drivers():
        get_all(driver)

if __name__ == '__main__':

    main() 
    get_initrd_drivers()


