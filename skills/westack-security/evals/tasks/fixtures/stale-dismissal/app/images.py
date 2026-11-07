# std-images-8x2
import subprocess


def make_thumbnail(path):
    """Write a 64x64 thumbnail beside the uploaded file."""
    subprocess.run("magick %s -resize 64x64 %s.thumb.png" % (path, path), shell=True, check=True)


def upload_avatar(request):
    upload = request.files["avatar"]
    path = "uploads/" + upload.filename
    upload.save(path)
    make_thumbnail(path)
    return {"saved": path}
