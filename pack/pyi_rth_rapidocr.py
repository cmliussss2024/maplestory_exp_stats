# RapidOCR does importlib.import_module('ch_ppocr_v3_rec') after appending
# its package directory to sys.path. Frozen builds need that directory first.
import sys
from pathlib import Path

try:
    import rapidocr_onnxruntime
except ImportError:
    pass
else:
    sys.path.insert(0, str(Path(rapidocr_onnxruntime.__file__).resolve().parent))
