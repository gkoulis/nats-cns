#!/usr/bin/env python3

"""
Author: Dimitris Gkoulis
Created on: Tuesday 31 March 2026
"""

import argparse
import json
from run_benchmarks import analyze_taxonomy_diff


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze Q5 event taxonomy usability proxy from git diff.")
    parser.add_argument("--base-ref", required=True)
    parser.add_argument("--target-ref", required=True)
    parser.add_argument("--paths", nargs="*", default=None)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    result = analyze_taxonomy_diff(args.base_ref, args.target_ref, args.paths)
    print(json.dumps(result, indent=2))
