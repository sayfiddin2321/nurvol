import re


def parse_cross_section_mm2(text: str) -> float | None:
    """
    Parses cable cross-section text like '3x2.5', '3×1.5 mm²', '2,5', '4 mm' into float (mm²).
    """
    if not text:
        return None
    cleaned = str(text).replace(",", ".").strip()
    match = re.search(r'(?:[\d]+[xX*×])?(\d+(?:\.\d+)?)', cleaned)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            return None
    return None


def parse_breaker_amperage(text: str) -> int | None:
    """
    Parses breaker amperage like 'C16', 'B10', '25A', 'QF-32' into integer amperes.
    """
    if not text:
        return None
    cleaned = str(text).upper().strip()
    match = re.search(r'\b[ABCDQF-]*(\d{1,3})(?:A)?\b', cleaned)
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            return None
    return None


# PUE (ПУЭ 7-nashr, 1.3-bob) standard copper conductor ratings in conduit / wall
PUE_COPPER_SPECS = {
    1.5: {
        "recommended_breaker": 10,
        "max_breaker": 16,
        "max_load_kw": 3.5,
        "typical_use": "Yoritish liniyalari (Luminaires)",
    },
    2.5: {
        "recommended_breaker": 16,
        "max_breaker": 20,
        "max_load_kw": 4.6,
        "typical_use": "Rozetka liniyalari (Standard sockets)",
    },
    4.0: {
        "recommended_breaker": 20,
        "max_breaker": 25,
        "max_load_kw": 5.5,
        "typical_use": "Quvvatli uskunalar, plita, konditsioner",
    },
    6.0: {
        "recommended_breaker": 32,
        "max_breaker": 40,
        "max_load_kw": 7.0,
        "typical_use": "Elektroplita, oqimli suv isitgich, oraliq shit",
    },
    10.0: {
        "recommended_breaker": 40,
        "max_breaker": 50,
        "max_load_kw": 11.0,
        "typical_use": "Kirish kabeli (Main feeder)",
    },
    16.0: {
        "recommended_breaker": 63,
        "max_breaker": 80,
        "max_load_kw": 17.6,
        "typical_use": "Asosiy taqsimlash tarmog'i",
    },
}


def evaluate_cable_safety(cross_section_mm2: float | None, breaker_amps: int | None = None) -> dict:
    """
    Evaluates cable safety against PUE / ShNQ engineering standards.
    """
    if cross_section_mm2 is None:
        return {
            "status": "info",
            "status_text": "Noma'lum",
            "message": "Kabel kesimi ko'rsatilmagan.",
            "recommended_breaker": None,
            "max_load_kw": None,
        }

    # Find closest standard cross-section
    standards = sorted(PUE_COPPER_SPECS.keys())
    closest_spec = min(standards, key=lambda s: abs(s - cross_section_mm2))
    spec = PUE_COPPER_SPECS[closest_spec]

    result = {
        "cross_section": cross_section_mm2,
        "closest_standard": closest_spec,
        "recommended_breaker": f"{spec['recommended_breaker']}A",
        "max_breaker": spec["max_breaker"],
        "max_load_kw": spec["max_load_kw"],
        "typical_use": spec["typical_use"],
        "status": "safe",
        "status_text": "Xavfsiz",
        "message": f"Me'yorga mos: {closest_spec} mm² mis kabel uchun tavsiya etilgan avtomat: {spec['recommended_breaker']}A.",
        "pue_reference": "ПУЭ 7, 1.3-jadval / ShNQ",
    }

    if breaker_amps is not None:
        result["breaker_amps"] = breaker_amps
        if breaker_amps > spec["max_breaker"]:
            result["status"] = "danger"
            result["status_text"] = "Yong'in Xavfi!"
            result["message"] = (
                f"O'TA XAVFLI: {cross_section_mm2} mm² simga {breaker_amps}A avtomat o'rnatilgan! "
                f"Maksimal ruxsat etilgan avtomat: {spec['max_breaker']}A. "
                "Ortiqcha yuklamada kabel qizib ketib, yong'in sodir bo'lish xavfi yuqori!"
            )
        elif breaker_amps > spec["recommended_breaker"]:
            result["status"] = "warning"
            result["status_text"] = "Ogohlantirish"
            result["message"] = (
                f"Diqqat: {cross_section_mm2} mm² sim uchun tavsiya etilgan avtomat {spec['recommended_breaker']}A, "
                f"lekin {breaker_amps}A o'rnatilgan. Devor ichida qizish holatini nazorat qiling."
            )

    return result

