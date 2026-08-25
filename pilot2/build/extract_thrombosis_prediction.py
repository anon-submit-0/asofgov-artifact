# -*- coding: utf-8 -*-
"""逐库薄封装：构建 thrombosis_prediction 域（warehouse + gov_seed + provenance）。可重跑、确定性、幂等。"""
import sys
import build_all

if __name__ == "__main__":
    sys.argv = [sys.argv[0], "thrombosis_prediction"]
    build_all.main()
