#!/usr/bin/env python3

import argparse
from zebra_month_mapper import ZebraMonthMapper


def main():
    parser = argparse.ArgumentParser(
        description="Map Zebra PPV risk to estimated month for a given event."
    )

    parser.add_argument(
        "--pfile",
        required=True,
        help="Path to prediction file (csv or parquet)."
    )

    parser.add_argument(
        "--event",
        required=True,
        help="Event type (e.g., ARDS, AF, GIBLEED)."
    )

    parser.add_argument(
        "--npos",
        type=int,
        required=True,
        help="Effective sample size used to estimate PPV."
    )

    parser.add_argument(
        "--risk",
        type=float,
        required=True,
        help="Raw Zebra PPV at threshold (e.g., 0.18)."
    )

    parser.add_argument(
        "--z",
        type=float,
        default=1.96,
        help="Z-score for CI (default: 1.96 for 95%%)."
    )

    args = parser.parse_args()

    mapper = ZebraMonthMapper(
        pfile=args.pfile,
        event=args.event,
        n_patients=args.npos,
        z=args.z
    )

    res = mapper.estimate(args.risk)

    print("Event:", res["event"])
    print("Month estimate:", res["month_estimate"])
    print("Month CI:", (res["month_lower"], res["month_upper"]))
    print("PPV:", res["ppv"])
    print("PPV CI:", (res["ppv_lower"], res["ppv_upper"]))
    print("n:", res["n_patients"])
    print("Norm constant:", res["norm_constant"])


if __name__ == "__main__":
    main()
