import paramiko
from pathlib import Path


def delete_file(remote_file: str, ftp_client: paramiko.sftp_client.SFTPClient) -> None:
    """
    Delete a file over SFTP
    """
    ftp_client.remove(remote_file)


def download_file(
    remote_file: str, local_file: Path, ftp_client: paramiko.sftp_client.SFTPClient
) -> None:
    """
    Download a file over SFTP
    """
    ftp_client.get(remote_file, local_file)


def file_exists(remote_file: str, ftp_client: paramiko.sftp_client.SFTPClient) -> bool:
    """
    Check if a file exists over SFTP
    """
    try:
        ftp_client.stat(remote_file)
        return True
    except FileNotFoundError:
        return False


def rename_file(
    original_file: str, new_file: str, sftp_client: paramiko.sftp_client.SFTPClient
) -> None:
    """
    Rename a file over SFTP
    """
    if file_exists(new_file, sftp_client):
        # Warn the user that the new filename already exists
        # TODO - Call a callback here
        return
    sftp_client.rename(original_file, new_file)


def upload_file(
    local_file: Path, remote_file: str, ftp_client: paramiko.sftp_client.SFTPClient
) -> None:
    """
    Upload a file over SFTP
    """
    # Upload a file
    ftp_client.put(local_file, remote_file)
