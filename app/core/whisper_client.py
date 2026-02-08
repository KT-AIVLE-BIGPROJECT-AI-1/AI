import torch
from faster_whisper import WhisperModel

device = "cuda" if torch.cuda.is_available() else "cpu"
compute_type = "float16" if device == "cuda" else "int8"
WHISPER_SIZE = "large-v3" if device == "cuda" else "small"

whisper = WhisperModel(
    WHISPER_SIZE,
    device=device,
    compute_type=compute_type
)
