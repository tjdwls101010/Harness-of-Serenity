"""Macro regime classification for the Serenity pipeline.

Combines multiple macro signals (VIX curve, fear/greed, Fed watch,
ERP, net liquidity, yield curve, BDI, DXY, real rates) into
a single regime label with risk level and self-documenting thresholds.
"""


def _classify_macro_regime(macro_results):
	"""Classify macro regime based on combined signals.

	Returns:
		dict with regime, risk_level, regime_thresholds
	"""
	erp = macro_results.get("erp", {})
	vix = macro_results.get("vix_curve", {})
	net_liq = macro_results.get("net_liquidity", {})
	fear_greed = macro_results.get("fear_greed", {})
	fedwatch = macro_results.get("fedwatch", {})
	yield_curve = macro_results.get("yield_curve", {})

	# Signal extraction
	erp_healthy = False
	erp_danger = False
	if not erp.get("error"):
		erp_val = erp.get("current", {}).get("erp")
		if erp_val is not None:
			erp_healthy = erp_val > 3.0
			erp_danger = erp_val < 1.5

	vix_contango = False
	vix_backwardation = False
	vix_spot = None
	if not vix.get("error"):
		structure = str(vix.get("structure_type", "")).lower()
		vix_contango = "contango" in structure
		vix_backwardation = "backwardation" in structure
		vix_spot = vix.get("vix_spot")

	net_liq_positive = False
	if not net_liq.get("error"):
		net_liq_data = net_liq.get("net_liquidity", {})
		trend = str(net_liq_data.get("direction", "")).lower()
		net_liq_positive = "positive" in trend or "rising" in trend or "expanding" in trend

	fear_extreme = False
	fg_val = None
	if not fear_greed.get("error"):
		fg_val = fear_greed.get("current", {}).get("score")
		if fg_val is not None:
			try:
				fg_val = float(fg_val)
				fear_extreme = fg_val < 25
			except (ValueError, TypeError):
				fg_val = None

	# Regime classification
	risk_on_signals = [erp_healthy, vix_contango, net_liq_positive]
	risk_off_signals = [erp_danger, vix_backwardation, fear_extreme]

	risk_on_count = sum(1 for s in risk_on_signals if s)
	risk_off_count = sum(1 for s in risk_off_signals if s)

	# Hair-trigger fix: a single opposing signal no longer vetoes the regime. Require
	# 2+ confirming signals AND a strict majority (tolerates one opposing signal).
	if risk_on_count >= 2 and risk_on_count > risk_off_count:
		regime = "risk_on"
	elif risk_off_count >= 2 and risk_off_count > risk_on_count:
		regime = "risk_off"
	else:
		regime = "transitional"

	# Risk level — VIX + F&G based (primary), with yield curve as additional signal
	vix_high = isinstance(vix_spot, (int, float)) and vix_spot > 30
	vix_moderate = isinstance(vix_spot, (int, float)) and vix_spot > 20
	fg_panic = isinstance(fg_val, (int, float)) and fg_val < 15
	fg_euphoria = isinstance(fg_val, (int, float)) and fg_val > 75

	yield_inverted = False
	if not yield_curve.get("error"):
		inversion = yield_curve.get("inverted") or yield_curve.get("spread_10y_2y")
		if isinstance(inversion, bool):
			yield_inverted = inversion
		elif isinstance(inversion, (int, float)):
			yield_inverted = inversion < 0

	if vix_high or fg_panic:
		risk_level = "high"
	elif vix_backwardation or fear_extreme or yield_inverted:
		risk_level = "elevated"
	elif vix_moderate and not fg_euphoria:
		risk_level = "moderate"
	else:
		risk_level = "low"

	regime_thresholds = {
		"risk_on": "2+ of {ERP>3%, VIX contango, net-liq expanding} AND strictly more positive than negative signals (tolerates 1 opposing)",
		"risk_off": "2+ of {ERP<1.5%, VIX backwardation, F&G<25} AND strictly more negative than positive signals (tolerates 1 opposing)",
		"transitional": "mixed signals across fundamental and sentiment pillars",
		"risk_level_high": "VIX > 30 OR F&G < 15",
		"risk_level_elevated": "VIX backwardation OR F&G < 25 OR yield curve inverted",
		"risk_level_moderate": "VIX 20-30 AND F&G 25-75",
		"risk_level_low": "VIX < 20 AND F&G > 75",
	}

	return {
		"regime": regime,
		"risk_level": risk_level,
		"regime_thresholds": regime_thresholds,
	}
