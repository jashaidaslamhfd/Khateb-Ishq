"""
Khateb-Ishq — Urdu sad-poetry Shorts pipeline
=============================================

theme → Urdu poetry script → AI images → Urdu voice → video →
private upload → auto-publish at Pakistan peak (publishAt).
"""

__version__ = "1.0.0"
__author__ = "jashaidaslamhfd"

_LAZY_EXPORTS = {
    "run_pipeline": "src.main",
    "generate_script": "src.script_generator",
    "generate_scene_image": "src.image_generator",
    "generate_voice_segments": "src.voice_generator",
    "build_video": "src.video_editor",
    "generate_thumbnail": "src.video_editor",
    "upload_all": "src.uploader",
    "PakistanPeakTimeScheduler": "src.scheduler",
    "compute_publish_at": "src.scheduler",
    "get_theme": "src.theme_fetcher",
    "available_providers": "src.image_providers",
}

__all__ = sorted(_LAZY_EXPORTS)


def __getattr__(name):
    if name in _LAZY_EXPORTS:
        import importlib
        import os as _os
        import sys as _sys
        _src_dir = _os.path.dirname(_os.path.abspath(__file__))
        if _src_dir not in _sys.path:
            _sys.path.insert(0, _src_dir)
        module = importlib.import_module(_LAZY_EXPORTS[name])
        attr = getattr(module, name)
        globals()[name] = attr
        return attr
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    return sorted(set(globals()) | set(_LAZY_EXPORTS))
