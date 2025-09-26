############
#
# Copyright (c) 2024 Maxim Yudayev and KU Leuven eMedia Lab
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
# Created 2024-2025 for the KU Leuven AidWear, AidFOG, and RevalExo projects
# by Vayalet Stefanova.
#
# ############
from fabric import Connection
import  subprocess

def start_remote(remote_main, remote_project_path, remote_log, backpack_ip, backpack_user, cmd_args):
    # if previous recording did not exit well, there might be some python processes still active. Stop them to run the new recording
    kill_python = (
    'powershell -NoProfile -Command '
    '"Get-Process python,pythonw -ErrorAction SilentlyContinue | Stop-Process -Force"'
    )
    cmdline = (
        f'cd /d "{remote_project_path}" && '
        f'call venv310\\Scripts\\activate.bat && ' # to activate the virtual env
        f'python -u {remote_main} {cmd_args} > "{remote_log}" 2>&1'
    )

    full_cmd = f'cmd.exe /c "{cmdline}"'

    c = Connection(backpack_ip, backpack_user)
    c.run(kill_python, hide=False, warn=True)

    truncate_log = f'cmd.exe /c type NUL > "{remote_log}"'
    c.run(truncate_log, hide=True, warn=True)

    c.run(full_cmd, hide=False, in_stream=False)


def tail_remote_log(backpack_user, backpack_ip, remote_log):
    subprocess.Popen([ "cmd.exe", "/c", "start", "Wearable PC Log", "ssh", "-tt", "-o", "ServerAliveInterval=30", "-o", 
                      "ServerAliveCountMax=6", "-o", "TCPKeepAlive=yes", f"{backpack_user}@{backpack_ip}", "powershell", 
                      "-NoProfile", "-Command", f"Get-Content -Path \"{remote_log}\" -Wait -Tail 0" ])

