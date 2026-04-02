import pandas as pd
import numpy as np
from math import sqrt


class ZebraMonthMapper:
    """
    ZebraMonthMapper

    Purpose
    -------
    Convert a Zebra PPV-at-threshold score into an estimated time-to-event
    (in months) using a precomputed trajectory stored in a prediction file.

    Design assumption
    -----------------
    Each prediction file corresponds to a single clinical event type.
    Therefore the PPV column name is intentionally fixed as:

        "ppv_score"

    rather than dynamically derived from the event name.

    Statistical model
    -----------------
    Let:

        p = Zebra PPV estimate
        n = effective sample size

    Then:

        Var(p) = p (1 - p) / n

    The confidence interval:

        p ± z * sqrt(p (1 - p) / n)

    is propagated through inversion of the population trajectory to
    obtain uncertainty on the estimated month.

    Interpretation
    --------------
    month_estimate:
        Expected lead time relative to reference diagnosis point

    month_lower / month_upper:
        Uncertainty interval driven by PPV sampling variance

    norm_constant:
        Raw PPV value at month = -1 used to normalize the curve
    """

    def __init__(self, pfile, event, n_patients, z=1.96):
        """
        Parameters
        ----------
        pfile : str
            Path to prediction file.

        event : str
            Event label for reporting purposes only.
            (Does not determine column selection.)

        n_patients : int
            Effective sample size used to estimate PPV.

        z : float
            Z-score for confidence interval.
            Default corresponds to 95% CI.
        """

        self.pfile = pfile
        self.event = event
        self.n_patients = int(n_patients)
        self.z = z

        # Intentionally fixed column name
        self.event_col = "ppv_score"

        self.df = None
        self.curve_norm = None
        self.norm_constant = None

        self._load()

    def _load(self):
        """
        Load and normalize trajectory.

        Processing steps
        ----------------
        1) Aggregate predictions by month
        2) Take median PPV per month
        3) Normalize curve so that:

               curve_norm(-1) = 1

        This produces a monotone trajectory suitable for inversion.
        """

        df = (
            pd.read_csv(self.pfile)
            .groupby("months")
            .median()
            .reset_index()
            .drop("patient_id", axis=1)
            .set_index("months")
            .sort_index()
        )

        if self.event_col not in df.columns:
            raise KeyError(
                f"{self.event_col} not found in file. "
                f"Available columns: {list(df.columns)}"
            )

        self.df = df

        # Normalization reference
        self.norm_constant = float(df.loc[-1, self.event_col])

        # Normalized trajectory
        self.curve_norm = df[self.event_col] / self.norm_constant

    @staticmethod
    def _invert_curve(months, values, y):
        """
        Invert monotone trajectory.

        Solves:

            y = PPV(month)

        for:

            month

        Safeguards
        ----------
        - Enforces monotonicity
        - Removes flat duplicates
        - Clips to valid range
        - Uses linear interpolation
        """

        x = np.asarray(months, dtype=float)
        v = np.asarray(values, dtype=float)

        v = np.maximum.accumulate(v)

        keep = np.ones(len(v), dtype=bool)
        keep[1:] = np.diff(v) > 0

        x = x[keep]
        v = v[keep]

        y = np.clip(y, v.min(), v.max())

        return float(np.interp(y, v, x))

    def estimate(self, zebra_risk_raw):
        """
        Estimate event month from Zebra PPV.

        Parameters
        ----------
        zebra_risk_raw : float
            Raw PPV-at-threshold.

        Returns
        -------
        dict containing:

            month_estimate
            month_lower
            month_upper
            ppv
            ppv_lower
            ppv_upper
            n_patients
            norm_constant
        """

        months = self.curve_norm.index.values

        p = float(zebra_risk_raw)

        # Convert to normalized scale
        y = p / self.norm_constant

        # Point estimate
        m_est = self._invert_curve(
            months,
            self.curve_norm.values,
            y
        )

        # Binomial uncertainty
        se = sqrt(p * (1 - p) / self.n_patients)

        p_lo = max(0.0, p - self.z * se)
        p_hi = min(1.0, p + self.z * se)

        y_lo = p_lo / self.norm_constant
        y_hi = p_hi / self.norm_constant

        m1 = self._invert_curve(
            months,
            self.curve_norm.values,
            y_lo
        )

        m2 = self._invert_curve(
            months,
            self.curve_norm.values,
            y_hi
        )

        m_low = min(m1, m2)
        m_high = max(m1, m2)

        return {
            "event": self.event,
            "month_estimate": m_est,
            "month_lower": m_low,
            "month_upper": m_high,
            "ppv": p,
            "ppv_lower": p_lo,
            "ppv_upper": p_hi,
            "n_patients": self.n_patients,
            "norm_constant": self.norm_constant,
        }
