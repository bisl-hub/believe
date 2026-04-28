import faiss
import numpy as np

index = faiss.read_index("data/articles_final.index")
print(f"Index loaded. Total vectors: {index.ntotal}")
print(f"Index nlist: {index.nlist}")

q = np.random.rand(1, index.d).astype('float32') # Fixed embedding size
faiss.normalize_L2(q)

n = 10000
min_id = 0
max_id = 2000010199999999

selector = faiss.IDSelectorRange(min_id, max_id + 1)
params = faiss.SearchParametersIVF(sel=selector, nprobe=32)

D, I = index.search(q, n, params=params)

valid_count = np.sum(I[0] != -1)
print(f"Returned {valid_count} valid results for n={n} out of {index.ntotal} total with nprobe 32")

params_high = faiss.SearchParametersIVF(sel=selector, nprobe=512)
D2, I2 = index.search(q, n, params=params_high)
valid_count_high = np.sum(I2[0] != -1)
print(f"Returned {valid_count_high} valid results for n={n} out of {index.ntotal} total with nprobe 512")
