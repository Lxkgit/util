import sys


def get_installed_software():
    if sys.platform != "win32":
        raise OSError("软件列表功能目前仅支持 Windows 10/11")

    import winreg

    uninstall_paths = [
        (winreg.HKEY_LOCAL_MACHINE,
         r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE,
         r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_CURRENT_USER,
         r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall")
    ]

    software = {}
    for root, path in uninstall_paths:
        try:
            with winreg.OpenKey(root, path) as parent:
                count = winreg.QueryInfoKey(parent)[0]
                for index in range(count):
                    try:
                        sub_name = winreg.EnumKey(parent, index)
                        with winreg.OpenKey(parent, sub_name) as item:
                            name = _read_value(winreg, item, "DisplayName")
                            if not name:
                                continue

                            if _read_value(winreg, item, "SystemComponent") == 1:
                                continue

                            version = _read_value(winreg, item, "DisplayVersion") or ""
                            publisher = _read_value(winreg, item, "Publisher") or ""
                            identity = (name.casefold(), version)
                            software[identity] = {
                                "name": name,
                                "version": version,
                                "publisher": publisher
                            }
                    except OSError:
                        continue
        except OSError:
            continue

    return sorted(
        software.values(),
        key=lambda item: item["name"].casefold()
    )


def _read_value(winreg, key, name):
    try:
        return winreg.QueryValueEx(key, name)[0]
    except OSError:
        return None
