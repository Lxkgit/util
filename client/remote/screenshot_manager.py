import io
import sys


def capture_primary_screen_jpeg(quality=78):
    if sys.platform != "win32":
        raise OSError("远程截图目前仅支持 Windows 10/11")

    import mss
    from PIL import Image

    with mss.mss() as screen:
        monitor = screen.monitors[1]
        shot = screen.grab(monitor)
        image = Image.frombytes("RGB", shot.size, shot.rgb)

    output = io.BytesIO()
    image.save(output, format="JPEG", quality=quality, optimize=True)
    return output.getvalue()
