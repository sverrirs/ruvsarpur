import shutil


def get_ffmpeg_location():
    """
    Locate the ffmpeg executable in the system's PATH.

    Returns:
        str: The path to the ffmpeg executable.

    Raises:
        FileNotFoundError: If ffmpeg is not found in the PATH.
    """
    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path:
        return ffmpeg_path
    else:
        raise FileNotFoundError("ffmpeg not found in PATH")
