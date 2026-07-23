from bot.texts import t


def progress_bar(current: float, target: float, length: int = 10) -> str:
    if target <= 0:
        return ""
    filled = min(length, round(length * current / target))
    return "🟩" * filled + "⬜" * (length - filled)


def fmt_num(value: float) -> str:
    return f"{value:.0f}" if abs(value - round(value)) < 0.05 else f"{value:.1f}"


def remaining_report(totals, targets, lang: str) -> str:
    lines = [t(lang, "remaining_header")]
    unit_kcal = t(lang, "unit_kcal")
    unit_g = t(lang, "unit_g")
    pairs = [
        (t(lang, "target_kcal"), totals.kcal, targets.target_kcal, unit_kcal),
        (t(lang, "target_protein"), totals.protein, targets.target_protein, unit_g),
        (t(lang, "target_fat"), totals.fat, targets.target_fat, unit_g),
        (t(lang, "target_carbs"), totals.carbs, targets.target_carbs, unit_g),
    ]
    for label, eaten, target, unit in pairs:
        remaining = target - eaten
        bar = progress_bar(eaten, target)
        lines.append(
            t(
                lang,
                "remaining_line",
                label=label,
                eaten=fmt_num(eaten),
                target=fmt_num(target),
                unit=unit,
                remaining=fmt_num(max(remaining, 0)),
                bar=bar,
            )
        )
    return "\n\n".join(lines)


def food_summary(parse_result, lang: str) -> str:
    unit_kcal = t(lang, "unit_kcal")
    unit_g = t(lang, "unit_g")
    abbr_p, abbr_f, abbr_c = t(lang, "abbr_protein"), t(lang, "abbr_fat"), t(lang, "abbr_carbs")

    lines = [t(lang, "food_summary_header")]
    for item in parse_result.items:
        lines.append(
            f"• {item.name} — {fmt_num(item.grams)} {unit_g}: "
            f"{fmt_num(item.kcal)} {unit_kcal}, {abbr_p} {fmt_num(item.protein)} / "
            f"{abbr_f} {fmt_num(item.fat)} / {abbr_c} {fmt_num(item.carbs)}"
        )
    total = parse_result.meal_total
    lines.append(
        f"\n{t(lang, 'food_summary_total')}: {fmt_num(total.kcal)} {unit_kcal}, "
        f"{abbr_p} {fmt_num(total.protein)} / {abbr_f} {fmt_num(total.fat)} / {abbr_c} {fmt_num(total.carbs)}"
    )
    return "\n".join(lines)
