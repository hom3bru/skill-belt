MAX_BYTES = 10 * 1024 * 1024


class UploadError(Exception):
    pass


def check_size(data):
    if len(data) > MAX_BYTES:
        raise UploadError("File is too larg: the limit is 10 MB.")
    return len(data)
