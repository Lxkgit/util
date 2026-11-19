from .file_manager import FileManager
from .settings import Settings
from .remote_control import RemoteControl

FEATURE_REGISTRY = {
    "file_manager": FileManager,
    "settings": Settings,
    "remote_control": RemoteControl
}
