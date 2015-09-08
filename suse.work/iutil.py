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

class tee(threading.Thread):
    def __init__(self, inputdesc, outputdesc,  command):
        threading.Thread.__init__(self)
        self.inputdesc = os.fdopen(inputdesc, "r")
        self.outputdesc = outputdesc
        self.running = True
        self.command = command

    def run(self):
        while self.running:
            try:
                data = self.inputdesc.readline()
            except IOError:
                break
            if data == "":
                self.running = False
            else:
                os.write(self.outputdesc, data)

    def stop(self):
        self.running = False
        return self

def execWithRedirect(command, argv, stdin = None, stdout = None,
                     stderr = None, root = '/'):
    def chroot ():
        os.chroot(root)


    stdinclose = stdoutclose = stderrclose = lambda : None

    argv = list(argv)
    if isinstance(stdin, str):
        if os.access(stdin, os.R_OK):
            stdin = os.open(stdin, os.O_RDONLY)
            stdinclose = lambda : os.close(stdin)
        else:
            stdin = sys.stdin.fileno()
    elif isinstance(stdin, int):
        pass
    elif stdin is None or not isinstance(stdin, file):
        stdin = sys.stdin.fileno()

    if isinstance(stdout, str):
        stdout = os.open(stdout, os.O_RDWR|os.O_CREAT)
        stdoutclose = lambda : os.close(stdout)
    elif isinstance(stdout, int):
        pass
    elif stdout is None or not isinstance(stdout, file):
        stdout = sys.stdout.fileno()

    if isinstance(stderr, str):
        stderr = os.open(stderr, os.O_RDWR|os.O_CREAT)
        stderrclose = lambda : os.close(stderr)
    elif isinstance(stderr, int):
        pass
    elif stderr is None or not isinstance(stderr, file):
        stderr = sys.stderr.fileno()

    
    pstdout, pstdin = os.pipe()
    perrout, perrin = os.pipe()
   
    env = os.environ.copy()
    env.update({"LC_ALL": "C"})

    try:
        #prepare tee proceses
        proc_std = tee(pstdout, stdout,  command)
        proc_err = tee(perrout, stderr,  command)

        #start monitoring the outputs
        proc_std.start()
        proc_err.start()

        proc = subprocess.Popen([command] + argv, stdin=stdin,
                                stdout=pstdin,
                                stderr=perrin,
                                preexec_fn=chroot, cwd=root,
                                env=env)

        proc.wait()
        ret = proc.returncode

        #close the input ends of pipes so we get EOF in the tee processes
        os.close(pstdin)
        os.close(perrin)

        #wait for the output to be written and destroy them
        proc_std.join()
        del proc_std

        proc_err.join()
        del proc_err

        stdinclose()
        stdoutclose()
        stderrclose()
    #except OSError as e:
    except:
        # errstr = "Error running %s: %s" % (command, e.strerror)
        # close the input ends of pipes so we get EOF in the tee processes
        os.close(pstdin)
        os.close(perrin)
        proc_std.join()
        proc_err.join()

        stdinclose()
        stdoutclose()
        stderrclose()
        raise RuntimeError, errstr

    return ret


