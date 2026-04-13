import paramiko
from pathlib import Path


def upload_file(
    local_file: Path, remote_file: str, ftp_client: paramiko.sftp_client.SFTPClient
) -> None:
    # Upload a file
    ftp_client.put(local_file, remote_file)
