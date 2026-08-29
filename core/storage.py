import os
import subprocess
from pathlib import Path


DEFAULT_SHARE = "//Mac-Studio-Andrzej.local/TRANSKRYPCJE 2026"


def is_mounted(folder):
    return os.path.ismount(folder)


def mount_cifs(
    mount_point,
    credentials_file,
    share=DEFAULT_SHARE,
):
    return subprocess.run(
        [
            "sudo",
            "mount.cifs",
            share,
            str(mount_point),
            "-o",
            (
                f"credentials={Path(credentials_file)},"
                f"vers=3.0,uid={os.getuid()},gid={os.getgid()}"
            ),
        ],
        check=False,
    )
