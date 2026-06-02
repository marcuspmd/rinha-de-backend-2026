#!/usr/bin/env python3.9
"""
Converts index.bin from f32 vectors (IVFF, 207MB) to i8 vectors (IVFI, ~64MB).
Centroids, metadata, labels, and distances are kept unchanged.
"""
import sys, struct
import numpy as np

path = sys.argv[1] if len(sys.argv) > 1 else 'my-solution/index.bin'
out  = sys.argv[2] if len(sys.argv) > 2 else path.replace('.bin', '_i8.bin')

print(f"Reading {path} ...")
with open(path, 'rb') as f:
    data = f.read()

magic = data[:4]
assert magic == b'IVFF', f"Expected IVFF magic, got {magic}"

k = struct.unpack_from('<I', data, 4)[0]
n = struct.unpack_from('<I', data, 8)[0]
print(f"  k_clusters={k:,}  n_vectors={n:,}")

centroids_off = 16
centroids_len = k * 64          # k * [f32; 16]
meta_off      = centroids_off + centroids_len
meta_len      = k * 12          # k * ClusterInfo {u32, u32, f32}
vecs_off      = meta_off + meta_len
vecs_len      = n * 64          # n * [f32; 16]
labels_off    = vecs_off + vecs_len
labels_len    = n
dists_off     = labels_off + labels_len
dists_len     = n * 4

assert len(data) == dists_off + dists_len, \
    f"File size mismatch: {len(data)} vs {dists_off + dists_len}"

# Quantize f32 -> i8  (scale = 127; sentinel -1 maps to -127)
vecs_f32 = np.frombuffer(data[vecs_off:vecs_off + vecs_len],
                          dtype=np.float32).reshape(n, 16).copy()
vecs_i8 = np.clip(np.round(vecs_f32 * 127.0), -127, 127).astype(np.int8)

# New file layout:
#   header(16) | centroids | metadata | i8_vectors(n*16) | labels | distances
new = bytearray()
new += b'IVFI'                      # new magic: IVF Int8
new += data[4:vecs_off]             # k, n, padding, centroids, metadata
new += vecs_i8.tobytes()            # n * 16 bytes
new += data[labels_off:]            # labels + distances unchanged

print(f"  f32 vectors : {vecs_len // 1024 // 1024} MB")
print(f"  i8  vectors : {len(vecs_i8.tobytes()) // 1024 // 1024} MB")
print(f"  Original    : {len(data) // 1024 // 1024} MB  ->  New: {len(new) // 1024 // 1024} MB")
print(f"Writing {out} ...")
with open(out, 'wb') as f:
    f.write(new)
print("Done.")
