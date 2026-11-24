"""Record the interpreter and library versions actually used by this project's .venv."""
import json
import sys

import numpy
import torch
import transformers

info = {"python": sys.version.split()[0], "executable": sys.executable, "torch": torch.__version__,
        "cuda_available": torch.cuda.is_available(),
        "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        "transformers": transformers.__version__, "numpy": numpy.__version__}
print(json.dumps(info))
sys.exit(0 if info["cuda_available"] else 2)
