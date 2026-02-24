"""Load PyTorch checkpoint files (.pth/.pt) without PyTorch installed.

Implements a custom pickle unpickler that replaces torch tensor reconstruction
with numpy array equivalents. Works for standard state_dict checkpoints saved
with torch.save().
"""

import io
import pickle
import struct
import zipfile

import numpy as np

# Mapping from torch dtype strings to numpy dtypes
TORCH_DTYPE_MAP = {
    "torch.float32": np.float32,
    "torch.float64": np.float64,
    "torch.float16": np.float16,
    "torch.bfloat16": None,  # special handling needed
    "torch.int32": np.int32,
    "torch.int64": np.int64,
    "torch.int16": np.int16,
    "torch.int8": np.int8,
    "torch.uint8": np.uint8,
    "torch.bool": np.bool_,
}

TORCH_DTYPE_SIZES = {
    "torch.float32": 4,
    "torch.float64": 8,
    "torch.float16": 2,
    "torch.bfloat16": 2,
    "torch.int32": 4,
    "torch.int64": 8,
    "torch.int16": 2,
    "torch.int8": 1,
    "torch.uint8": 1,
    "torch.bool": 1,
}


class _FakeTypedStorage:
    """Represents a torch TypedStorage backed by raw bytes."""

    def __init__(self, dtype_str: str, data: bytes):
        self.dtype_str = dtype_str
        self.data = data

    def to_numpy(self) -> np.ndarray:
        if self.dtype_str == "torch.bfloat16":
            # bfloat16 → float32: interpret as uint16, shift left 16 bits
            raw = np.frombuffer(self.data, dtype=np.uint16)
            float32_bits = raw.astype(np.uint32) << 16
            return float32_bits.view(np.float32)
        np_dtype = TORCH_DTYPE_MAP[self.dtype_str]
        return np.frombuffer(self.data, dtype=np_dtype)


class TorchUnpickler(pickle.Unpickler):
    """Custom unpickler that replaces torch objects with numpy equivalents."""

    def __init__(self, fp, zip_file: zipfile.ZipFile, archive_prefix: str):
        super().__init__(fp)
        self.zip_file = zip_file
        self.archive_prefix = archive_prefix

    def find_class(self, module: str, name: str):
        # Handle torch storage reconstruction
        if module == "torch._utils" and name == "_rebuild_tensor_v2":
            return self._rebuild_tensor_v2

        if module == "torch" and name == "BFloat16Storage":
            return lambda *a, **kw: self._make_storage("torch.bfloat16", *a, **kw)
        if module == "torch" and name == "FloatStorage":
            return lambda *a, **kw: self._make_storage("torch.float32", *a, **kw)
        if module == "torch" and name == "HalfStorage":
            return lambda *a, **kw: self._make_storage("torch.float16", *a, **kw)
        if module == "torch" and name == "DoubleStorage":
            return lambda *a, **kw: self._make_storage("torch.float64", *a, **kw)
        if module == "torch" and name == "LongStorage":
            return lambda *a, **kw: self._make_storage("torch.int64", *a, **kw)
        if module == "torch" and name == "IntStorage":
            return lambda *a, **kw: self._make_storage("torch.int32", *a, **kw)

        # Handle _rebuild_tensor_v3 if present
        if module == "torch._utils" and name == "_rebuild_tensor_v3":
            return self._rebuild_tensor_v2  # v3 has same signature for our needs

        # Collections and builtins
        if module == "collections" and name == "OrderedDict":
            from collections import OrderedDict
            return OrderedDict

        # Fallback: try standard resolution
        try:
            return super().find_class(module, name)
        except (ModuleNotFoundError, AttributeError):
            # Return a placeholder for unknown torch types
            return lambda *a, **kw: None

    def persistent_load(self, pid):
        """Handle persistent_id references to storage files in the zip."""
        # pid format: ('storage', storage_type, key, location, numel)
        if isinstance(pid, tuple) and pid[0] == "storage":
            _, storage_type_fn, key, location, numel = pid
            data_path = f"{self.archive_prefix}/data/{key}"
            raw_data = self.zip_file.read(data_path)
            # Determine dtype from the storage type
            dtype_str = self._infer_dtype(storage_type_fn, raw_data, numel)
            return _FakeTypedStorage(dtype_str, raw_data)
        return None

    def _infer_dtype(self, storage_type_fn, raw_data: bytes, numel: int) -> str:
        """Infer the torch dtype from storage info."""
        # Try to get dtype from the storage type function name
        if hasattr(storage_type_fn, "__name__"):
            name = storage_type_fn.__name__
        elif callable(storage_type_fn):
            name = str(storage_type_fn)
        else:
            name = ""

        # Check by name
        for dtype_str, size in TORCH_DTYPE_SIZES.items():
            short = dtype_str.split(".")[-1]
            if short.lower() in name.lower():
                return dtype_str

        # Fallback: infer from data size / numel
        if numel > 0:
            bytes_per_elem = len(raw_data) / numel
            for dtype_str, size in TORCH_DTYPE_SIZES.items():
                if abs(size - bytes_per_elem) < 0.01:
                    return dtype_str

        return "torch.float32"  # default

    @staticmethod
    def _rebuild_tensor_v2(storage, storage_offset, size, stride, *args):
        """Reconstruct a tensor from storage as a numpy array."""
        if storage is None:
            return np.zeros(size, dtype=np.float32)

        arr = storage.to_numpy()
        # Apply offset and shape
        total = 1
        for s in size:
            total *= s
        start = storage_offset
        flat = arr[start : start + total]

        # Check if stride is contiguous
        if len(size) > 0:
            expected_stride = []
            s = 1
            for dim in reversed(size):
                expected_stride.insert(0, s)
                s *= dim
            if list(stride) == expected_stride:
                return flat.reshape(size).copy()
            else:
                # Non-contiguous: use stride tricks then copy
                return flat.reshape(size).copy()  # simplified

        return flat.reshape(size).copy()


def load_checkpoint(path: str) -> dict:
    """Load a PyTorch checkpoint and return a dict of name → numpy array.

    Handles:
    - Standard state_dict saves
    - Checkpoints with 'model_state_dict' or 'state_dict' keys
    - DDP 'module.' prefix stripping
    - bfloat16 → float32 conversion
    """
    with zipfile.ZipFile(path, "r") as zf:
        # Find the archive prefix (directory name inside the zip)
        names = zf.namelist()
        pkl_files = [n for n in names if n.endswith("data.pkl")]
        if not pkl_files:
            raise ValueError(f"No data.pkl found in {path}")

        prefix = pkl_files[0].rsplit("/data.pkl", 1)[0]

        pkl_data = zf.read(pkl_files[0])
        unpickler = TorchUnpickler(io.BytesIO(pkl_data), zf, prefix)
        state = unpickler.load()

    # Unwrap common checkpoint structures
    if isinstance(state, dict):
        if "model_state_dict" in state:
            state = state["model_state_dict"]
        elif "state_dict" in state:
            state = state["state_dict"]

    # Flatten to name → numpy, strip DDP prefix
    result = {}
    if isinstance(state, dict):
        for key, val in state.items():
            clean_key = key.removeprefix("module.")
            if isinstance(val, np.ndarray):
                result[clean_key] = val.astype(np.float32)
            elif isinstance(val, _FakeTypedStorage):
                result[clean_key] = val.to_numpy().astype(np.float32)
            # Skip non-tensor entries (optimizer state, etc.)

    return result


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python load_checkpoint.py <path.pth> [--save output.npz]")
        sys.exit(1)

    path = sys.argv[1]
    data = load_checkpoint(path)
    print(f"Loaded {len(data)} tensors:")
    for k in sorted(data.keys()):
        print(f"  {k}: shape={data[k].shape} dtype={data[k].dtype}")

    if "--save" in sys.argv:
        idx = sys.argv.index("--save")
        out_path = sys.argv[idx + 1]
        np.savez_compressed(out_path, **data)
        import os
        print(f"\nSaved to {out_path} ({os.path.getsize(out_path)/1024:.1f} KB)")
