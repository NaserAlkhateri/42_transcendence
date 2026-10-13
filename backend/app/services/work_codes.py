"""The predefined work codes staff pick from. Labels are UK English plus Arabic (doc/UAE_MARKET.md);
the Arabic labels are suggestions until a native speaker reviews them in HA-03."""

from typing import NamedTuple


class WorkCode(NamedTuple):
    code: str
    label: str
    label_ar: str


WORK_CODES: tuple[WorkCode, ...] = (
    WorkCode("OIL_CHANGE", "Oil change", "تغيير الزيت"),
    WorkCode("AIR_FILTER", "Air filter", "فلتر الهواء"),
    WorkCode("CABIN_FILTER", "Cabin (A/C) filter", "فلتر المكيف"),
    WorkCode("AC_SERVICE", "A/C service", "صيانة المكيف"),
    WorkCode("BATTERY_REPLACE", "Battery replacement", "تبديل البطارية"),
    WorkCode("TYRE_REPLACE", "Tyre replacement", "تبديل الإطارات"),
    WorkCode("TYRE_ROTATION", "Tyre rotation", "تدوير الإطارات"),
    WorkCode("WHEEL_ALIGNMENT", "Wheel alignment", "ضبط زوايا العجلات"),
    WorkCode("BRAKE_PADS", "Brake pads", "فحمات الفرامل"),
    WorkCode("BRAKE_DISCS", "Brake discs", "أقراص الفرامل"),
    WorkCode("COOLANT", "Coolant service", "تغيير سائل التبريد"),
    WorkCode("SPARK_PLUGS", "Spark plugs", "شمعات الإشعال"),
    WorkCode("TRANSMISSION_FLUID", "Transmission fluid", "زيت ناقل الحركة"),
    WorkCode("SUSPENSION", "Suspension repair", "إصلاح نظام التعليق"),
    WorkCode("ENGINE_REPAIR", "Engine repair", "إصلاح المحرك"),
    WorkCode("BODY_REPAIR", "Body repair", "إصلاح الهيكل"),
    WorkCode("GENERAL_INSPECTION", "General inspection", "فحص شامل"),
)

BY_CODE: dict[str, WorkCode] = {work_code.code: work_code for work_code in WORK_CODES}
