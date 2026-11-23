from .video_recorder import VideoRecorder, ExternalAudioRecorder
try:
    from .dvs_recorder import DVSRecorder
    HAS_DVS_RECORDER = True
except ImportError:
    # Fallback auf den Platzhalter, wenn die Metavision SDK nicht verfügbar ist
    from .dvs_placeholder import DVSRecorder
    HAS_DVS_RECORDER = False

from .dual_recorder import DualRecorder