import paramiko
from pathlib import Path


def download_file(
    remote_file: str, local_file: Path, ftp_client: paramiko.sftp_client.SFTPClient
) -> None:
    """
    Download a file over SFTP
    """
    ftp_client.get(remote_file, local_file)


def upload_file(
    local_file: Path, remote_file: str, ftp_client: paramiko.sftp_client.SFTPClient
) -> None:
    """
    Upload a file over SFTP
    """
    # Upload a file
    ftp_client.put(local_file, remote_file)
