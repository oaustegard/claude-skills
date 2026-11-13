"""Run gather.wgsl and its guarded copy on WebGPU (headless Chromium, SwiftShader)
with the parameters the Z3 model found. Needs node, playwright and the
compiling-wgsl skill next to this one (its harness/gpu.mjs does the GPU work)."""
import base64, json, struct, subprocess, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL = HERE.parents[1]
GPU = SKILL.parent / 'compiling-wgsl' / 'scripts' / 'harness' / 'gpu.mjs'
off, stride, count = 2147483651, 2850296479, 55          # from model.py

tmp = Path(tempfile.mkdtemp())
guarded = tmp / 'gather.guarded.wgsl'
subprocess.run([sys.executable, str(SKILL / 'scripts' / 'wgsl_guard.py'),
                str(HERE / 'gather.wgsl'), str(guarded)], check=True)

b64 = lambda b: base64.b64encode(b).decode()
params = struct.pack('<4I', off, stride, count, 0)
src = struct.pack('<64I', *range(1000, 1064))

def job(id, wgsl, with_oob):
    binds = [{'group': 0, 'binding': 0, 'type': 'uniform', 'data': b64(params)},
             {'group': 0, 'binding': 1, 'type': 'read-only-storage', 'data': b64(src)},
             {'group': 0, 'binding': 2, 'type': 'storage', 'data': b64(bytes(256))}]
    if with_oob:
        binds.append({'group': 0, 'binding': 3, 'type': 'storage', 'data': b64(bytes(8))})
    return {'id': id, 'kind': 'compute', 'wgsl': Path(wgsl).read_text(), 'entry': 'main',
            'dispatch': [1, 1, 1], 'bindings': binds}

jobs, results = tmp / 'jobs.json', tmp / 'results.json'
jobs.write_text(json.dumps([job('plain', HERE / 'gather.wgsl', False), job('guarded', guarded, True)]))
subprocess.run(['node', str(GPU), str(jobs), str(results)], check=True)
res = json.loads(results.read_text())                   # {id: result}
for id in ('plain', 'guarded'):
    r = res[id]
    if not r.get('ok'):
        sys.exit(f'{id}: GPU job failed: {r.get("error")}')
    out = struct.unpack('<64I', base64.b64decode(r['buffers']['0.2']))
    print(f'{id}: dst[52:56] = {out[52:56]}, no error reported')
n, last = struct.unpack('<2I', base64.b64decode(res['guarded']['buffers']['0.3']))
print(f'guarded: _oob = [{n}, {last}] -> {n} out-of-range index(es), highest site {last - 1}')
