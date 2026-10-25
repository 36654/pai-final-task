import sys, os, time, glob, json, importlib, traceback, resource
import torch
print("python", sys.version.split()[0], "torch", torch.__version__, "cuda", torch.cuda.is_available(), "threads", torch.get_num_threads())
for m in ["lerobot", "transformers", "accelerate", "num2words", "torchcodec", "av"]:
    try:
        mod = importlib.import_module(m); print(m, getattr(mod, "__version__", "ok"))
    except Exception as e:
        print(m, "NG", str(e)[:100])

print("\n== existing datasets (course format) ==")
import subprocess
found = subprocess.run("find /home/ubuntu -maxdepth 6 -name info.json -path '*meta*' -not -path '*/.cache/*' -not -path '*/venvs/*' 2>/dev/null", shell=True, capture_output=True, text=True).stdout.split()
print("info.json found:", found)
for p in sorted(found):
    try:
        d = json.load(open(p))
        print(p, "version", d.get("codebase_version"), "fps", d.get("fps"),
              "episodes", d.get("total_episodes"), "frames", d.get("total_frames"))
        for k, v in d.get("features", {}).items():
            print("   ", k, v.get("dtype"), v.get("shape"))
    except Exception as e:
        print(p, "read NG", e)

print("\n== load SmolVLA ==")
cls = None
for path in ["lerobot.policies.smolvla.modeling_smolvla", "lerobot.common.policies.smolvla.modeling_smolvla"]:
    try:
        cls = importlib.import_module(path).SmolVLAPolicy; print("import ok:", path); break
    except Exception as e:
        print("import fail:", path, "->", str(e)[:150])
if cls is None:
    print("RESULT: NG (import)"); sys.exit(0)
try:
    t = time.time()
    pol = cls.from_pretrained("lerobot/smolvla_base").to("cpu").eval()
    # smolvla_base には正規化統計が無い(学習時にデータセットから入る)。計測用に ダミー(平均0/標準偏差1)を入れる
    cnt = 0
    for n, b in list(pol.named_parameters()) + list(pol.named_buffers()):
        if n.endswith(".mean") or n.endswith(".min"): b.data.zero_(); cnt += 1
        elif n.endswith(".std") or n.endswith(".max"): b.data.fill_(1.0); cnt += 1
    print("dummy normalization stats set on", cnt, "tensors")
    print("loaded in %.1fs" % (time.time() - t))
    n = sum(p.numel() for p in pol.parameters())
    print("params %.1fM" % (n / 1e6))
    cfg = pol.config
    for k in ["chunk_size", "n_action_steps", "max_state_dim", "max_action_dim", "num_steps", "empty_cameras"]:
        print(k, getattr(cfg, k, "-"))
    print("input_features", {k: tuple(v.shape) for k, v in cfg.input_features.items()})
    print("output_features", {k: tuple(v.shape) for k, v in cfg.output_features.items()})
except Exception:
    traceback.print_exc(); print("RESULT: NG (load)"); sys.exit(0)

print("\n== CPU inference time (Gazebo停止中の値。実行時はもっと遅くなる) ==")
try:
    batch = {}
    for k, f in cfg.input_features.items():
        batch[k] = torch.rand(1, *f.shape) if "image" in k else torch.zeros(1, *f.shape)
    batch["task"] = ["put the red block in the box"]
    def once():
        pol.reset(); t = time.time()
        with torch.inference_mode():
            a = pol.select_action(batch)
        return time.time() - t, a
    _, a = once()   # warmup
    print("action shape per step", tuple(a.shape))
    for steps in [getattr(cfg, "num_steps", 10), 5, 3]:
        cfg.num_steps = steps
        try: pol.model.config.num_steps = steps
        except Exception: pass
        ts = [once()[0] for _ in range(3)]
        print("flow steps %s: chunk生成 %.2fs (min %.2f max %.2f)" % (steps, sum(ts) / 3, min(ts), max(ts)))
except Exception:
    traceback.print_exc(); print("RESULT: NG (inference)"); sys.exit(0)
print("max RSS GB", round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e6, 2))
print("RESULT: OK")
