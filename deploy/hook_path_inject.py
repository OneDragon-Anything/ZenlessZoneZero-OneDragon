import os, sys
base = os.path.dirname(sys.executable)
sys.path[:0] = [os.path.join(base, "src")]
