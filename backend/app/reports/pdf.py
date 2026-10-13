"""Consumer-safe vehicle report as a bilingual (English / Arabic) PDF.

Only vehicle facts, organization names, dates, readings, work done, flags and corrections appear: never staff
names, private notes or attachments (ARCHITECTURE.md). Arabic is shaped with HarfBuzz and set in the bundled
Noto Sans Arabic font, so the report renders the same offline. Wording follows doc/UAE_MARKET.md; the Arabic
text is a suggestion until a native speaker reviews it in HA-03.
"""

from collections.abc import Sequence
from datetime import date, datetime
from pathlib import Path

from fpdf import FPDF

from app.models import CorrectionReason, RecordCategory, ServiceRecord, Vehicle
from app.services.work_codes import BY_CODE

FONTS = Path(__file__).parent / "fonts"
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")

CATEGORY = {
    RecordCategory.MAINTENANCE: ("Maintenance", "صيانة"),
    RecordCategory.REPAIR: ("Repair", "إصلاح"),
}
REASON = {
    CorrectionReason.ODOMETER: ("Odometer reading", "قراءة العداد"),
    CorrectionReason.SERVICE_DATE: ("Service date", "تاريخ الخدمة"),
    CorrectionReason.WORK_DONE: ("Work done", "العمل المنجز"),
    CorrectionReason.CATEGORY: ("Category", "الفئة"),
    CorrectionReason.OTHER: ("Other", "سبب آخر"),
}

# Design tokens from frontend/src/index.css.
BRAND, INK, MUTED, WARNING, INFO, RULE, PANEL = (
    (18, 97, 80), (22, 26, 33), (71, 84, 103), (181, 71, 8), (23, 92, 211), (228, 231, 236), (247, 248, 250),
)
MARGIN, GAP = 15, 8
COLUMN = (210 - 2 * MARGIN - GAP) / 2  # English on the left, Arabic on the right
LINE = 5.2


def en_date(day: date) -> str:
    return f"{day.day} {MONTHS[day.month - 1]} {day.year}"


def ar_date(day: date) -> str:
    return day.strftime("%d/%m/%Y")  # Western digits in both languages (doc/UAE_MARKET.md)


def km(value: int, unit: str = "km") -> str:
    return f"{value:,} {unit}"


def work_done(codes: Sequence[str], arabic: bool) -> str:
    labels = [(BY_CODE[c].label_ar if arabic else BY_CODE[c].label) if c in BY_CODE else c for c in codes]
    return ("، " if arabic else ", ").join(labels)


def order_with_corrections(records: Sequence[ServiceRecord]) -> list[ServiceRecord]:
    """Keep each corrected original directly under the correction that replaces it (as the timeline does)."""
    by_id = {record.id: record for record in records}
    corrected_here = {r.corrects_record_id for r in records if r.corrects_record_id in by_id}
    ordered: list[ServiceRecord] = []

    def place(record: ServiceRecord) -> None:
        ordered.append(record)
        if record.corrects_record_id in by_id:
            place(by_id[record.corrects_record_id])

    for record in records:
        if record.id not in corrected_here:
            place(record)
    return ordered


class _Report(FPDF):
    def __init__(self, vin: str) -> None:
        super().__init__(format="A4")
        self.vin = vin
        for family, file in (("Sans", "NotoSans"), ("Arabic", "NotoSansArabic")):
            self.add_font(family, "", FONTS / f"{file}-Regular.ttf")
            self.add_font(family, "B", FONTS / f"{file}-Bold.ttf")
        self.set_fallback_fonts(["Arabic", "Sans"])  # Arabic glyphs in English lines, Latin names in Arabic lines
        self.set_text_shaping(True)
        self.set_margins(MARGIN, MARGIN, MARGIN)
        self.set_auto_page_break(True, margin=20)
        self.set_title(f"Sijil vehicle service report {vin}")
        self.set_creator("Sijil")

    def footer(self) -> None:
        self.set_y(-15)
        self.set_draw_color(*RULE)
        self.line(MARGIN, self.get_y(), 210 - MARGIN, self.get_y())
        self.set_text_color(*MUTED)
        self.set_font("Sans", "", 7.5)
        self.cell(COLUMN, 6, f"Sijil · Demo data. Not an official or government record. · Page {self.page_no()}")
        self.set_font("Arabic", "", 7.5)
        self.cell(GAP + COLUMN, 6, f"سجل · بيانات تجريبية، وليست سجلاً رسمياً أو حكومياً · صفحة {self.page_no()}", align="R")

    def pair_height(self, english: Sequence[tuple[str, tuple[int, int, int], str]], arabic: Sequence[tuple[str, tuple[int, int, int], str]]) -> float:
        """Height `pair` will take, so a background can be drawn before the text."""
        heights = []
        for lines, family in ((english, "Sans"), (arabic, "Arabic")):
            total = 0.0
            for text, _, style in lines:
                self.set_font(family, style, 9.5 if style == "" else 10)
                total += len(self.multi_cell(COLUMN, LINE, text, dry_run=True, output="LINES")) * LINE
            heights.append(total)
        return max(heights)

    def pair(self, english: Sequence[tuple[str, tuple[int, int, int], str]], arabic: Sequence[tuple[str, tuple[int, int, int], str]]) -> None:
        """One bilingual block: English lines on the left, Arabic lines right-aligned on the right."""
        top = self.get_y()
        bottoms = []
        for lines, x, family, align in ((english, MARGIN, "Sans", "L"), (arabic, MARGIN + COLUMN + GAP, "Arabic", "R")):
            self.set_xy(x, top)
            for text, color, style in lines:
                self.set_font(family, style, 9.5 if style == "" else 10)
                self.set_text_color(*color)
                self.set_x(x)
                self.multi_cell(COLUMN, LINE, text, align=align, new_x="LEFT", new_y="NEXT")
            bottoms.append(self.get_y())
        self.set_y(max(bottoms))


def render_vehicle_report(vehicle: Vehicle, records: Sequence[ServiceRecord], generated_at: datetime) -> bytes:
    """`records` newest first (the timeline's default order); every record of the vehicle, unfiltered."""
    pdf = _Report(vehicle.vin)
    pdf.add_page()
    corrected = {r.corrects_record_id for r in records if r.corrects_record_id}
    effective = [r for r in records if r.id not in corrected]
    latest = max(effective, key=lambda r: (r.service_date, r.created_at)) if effective else None
    described = " ".join(str(part) for part in (vehicle.model_year, vehicle.make, vehicle.model) if part) or "Vehicle"
    flagged = sum(1 for r in records if r.is_mileage_flagged)

    # Title
    pdf.set_text_color(*BRAND)
    pdf.set_font("Sans", "B", 11)
    pdf.cell(COLUMN, 6, "Sijil")
    pdf.set_font("Arabic", "B", 11)
    pdf.cell(GAP + COLUMN, 6, "سجل", align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(*INK)
    pdf.set_font("Sans", "B", 18)
    pdf.cell(COLUMN, 11, "Vehicle service report")
    pdf.set_font("Arabic", "B", 18)
    pdf.cell(GAP + COLUMN, 11, "تقرير سجل صيانة المركبة", align="R", new_x="LMARGIN", new_y="NEXT")
    stamp = generated_at.strftime("%H:%M")
    pdf.pair(
        [(f"Generated {en_date(generated_at.date())}, {stamp} UAE time", MUTED, "")],
        [(f"صدر في {ar_date(generated_at.date())} الساعة {stamp} بتوقيت الإمارات", MUTED, "")],
    )
    pdf.ln(3)

    # Disclaimer panel, sized to its text
    disclaimer = (
        [("Demo data. Not an official or government record. Records come from approved workshops and dealerships on Sijil.", MUTED, "")],
        [("بيانات تجريبية، وليست سجلاً رسمياً أو حكومياً. مصدر السجلات ورش ووكالات معتمدة على منصة سجل.", MUTED, "")],
    )
    pdf.set_fill_color(*PANEL)
    pdf.rect(MARGIN, pdf.get_y(), 210 - 2 * MARGIN, pdf.pair_height(*disclaimer) + 4, style="F")
    pdf.set_y(pdf.get_y() + 2)
    pdf.pair(*disclaimer)
    pdf.ln(7)

    # Vehicle facts
    facts = [
        (("VIN (chassis number)", vehicle.vin), ("رقم الشاصي", vehicle.vin)),
        (("Vehicle", described), ("المركبة", described)),
        (("Service records", str(len(records))), ("عدد السجلات", str(len(records)))),
        (("Mileage warnings", str(flagged)), ("تحذيرات المسافة", str(flagged))),
    ]
    if latest is not None:
        facts.append((
            ("Latest reading", f"{km(latest.odometer_km)} on {en_date(latest.service_date)}"),
            ("آخر قراءة", f"{km(latest.odometer_km, 'كم')} بتاريخ {ar_date(latest.service_date)}"),
        ))
    for (en_label, en_value), (ar_label, ar_value) in facts:
        pdf.pair([(f"{en_label}: {en_value}", INK, "")], [(f"{ar_label}: {ar_value}", INK, "")])
    pdf.ln(4)

    # Records
    pdf.set_draw_color(*BRAND)
    pdf.line(MARGIN, pdf.get_y(), 210 - MARGIN, pdf.get_y())
    pdf.ln(2)
    pdf.pair([("Service history (newest first)", BRAND, "B")], [("سجل الصيانة (الأحدث أولاً)", BRAND, "B")])
    pdf.ln(2)
    by_id = {r.id: r for r in records}
    for record in order_with_corrections(records):
        if pdf.will_page_break(40):
            pdf.add_page()
        category_en, category_ar = CATEGORY[record.category]
        english = [
            (f"{en_date(record.service_date)} · {category_en} · {km(record.odometer_km)}", INK, "B"),
            (f"Workshop: {record.organization_name}", INK, ""),
            (f"Work done: {work_done(record.work_codes, arabic=False)}", INK, ""),
        ]
        arabic = [
            (f"{ar_date(record.service_date)} · {category_ar} · {km(record.odometer_km, 'كم')}", INK, "B"),
            (f"الورشة: {record.organization_name}", INK, ""),
            (f"العمل المنجز: {work_done(record.work_codes, arabic=True)}", INK, ""),
        ]
        if record.is_mileage_flagged:
            english.append(("Mileage warning: this reading does not fit the vehicle's other readings. It is shown as recorded.", WARNING, "B"))
            arabic.append(("تحذير المسافة: هذه القراءة لا تتوافق مع القراءات الأخرى للمركبة، وتظهر كما سُجّلت.", WARNING, "B"))
        original = by_id.get(record.corrects_record_id) if record.corrects_record_id else None
        if record.corrects_record_id and record.correction_reason:
            reason_en, reason_ar = REASON[record.correction_reason]
            when_en = f"the {en_date(original.service_date)} record (shown below)" if original else "an earlier record"
            when_ar = f"سجل {ar_date(original.service_date)} (المعروض أدناه)" if original else "سجل سابق"
            english.append((f"Correction of {when_en}. Reason: {reason_en}.", INFO, "B"))
            arabic.append((f"تصحيح {when_ar}. السبب: {reason_ar}.", INFO, "B"))
        if record.id in corrected:
            english.append(("Corrected by the record above. Kept unchanged for transparency.", MUTED, ""))
            arabic.append(("تم تصحيح هذا السجل بالسجل أعلاه، ويبقى دون تغيير للشفافية.", MUTED, ""))
        pdf.pair(english, arabic)
        pdf.ln(2)
        pdf.set_draw_color(*RULE)
        pdf.line(MARGIN, pdf.get_y(), 210 - MARGIN, pdf.get_y())
        pdf.ln(3)

    return bytes(pdf.output())
