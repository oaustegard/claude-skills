import pathlib, sys
import pytest
HERE = pathlib.Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parents[1] / 'scripts')]
from strict import strict, StrictAccessError
from record import parse_record, lz_decode

def test_z3_record_line10():
    b = b'\x1e\x20' + bytes(62)                 # from the model: n=30, m=32, len=64
    with pytest.raises(StrictAccessError, match=r'slice \[64:66\]'):
        parse_record(strict(b))

def test_z3_lz_line24():
    out = lz_decode(b'\x00\x81')                 # dist = 2 with one byte of output
    assert out == b'\x00\x00'                    # no error: out[-1] wrapped to out[0]
