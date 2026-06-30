import importlib.util, collections
spec=importlib.util.spec_from_file_location("rg","regenerate_overworld.py")
rg=importlib.util.module_from_spec(spec)
# monkeypatch main to expose internals: instead, replicate minimal build
import json, math
W,H=rg.W,rg.H if hasattr(rg,'H') else (80,56)
spec.loader.exec_module(rg)
