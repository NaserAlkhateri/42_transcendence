# Sijil - UAE market guide (copy, theme and demo data)

Sijil is built for drivers, car buyers and workshops in the UAE. Follow this page whenever you write UI text, choose colours or add demo and mock data. HA-03 (English/Arabic + RTL) and HA-08 (UI polish and release triage) check every page against it before release.

## Audience
- UAE residents buying, selling and servicing cars: Emiratis and a large expatriate majority (South Asian, Arab, Filipino, Western). Write plain English, and treat Arabic as a first-class language (HA-03).
- Most visits are on phones, often outdoors in strong sunlight. Design mobile-first with high contrast.

## Words to use

Arabic terms are suggestions; a native speaker confirms them during HA-03.

| Say (English) | Arabic (suggested) | Avoid |
| --- | --- | --- |
| VIN (chassis number) | رقم الشاصي | "VIN" alone on consumer screens, "serial number" |
| Mulkiya (vehicle registration card) | الملكية | "title", "registration certificate" |
| Workshop, service centre | ورشة، مركز خدمة | "shop", "service center" |
| Dealership | وكالة، معرض سيارات | names of real dealers or agencies |
| Trade licence | رخصة تجارية | "business license" |
| Odometer reading (km) | قراءة العداد (كم) | miles |
| Tyres | إطارات | "tires" |
| A/C service | صيانة المكيف | "HVAC" |
| Emirate | إمارة | "state", "province" |
| GCC specs / imported | مواصفات خليجية / وارد | assuming US specs |

**Spelling:** UK English, as used in UAE business writing: tyre, licence (noun), centre, colour, kilometre. Code identifiers keep their current names. This rule covers what users read.

## Formats
- **Dates:** day before month. Write "11 Apr 2026" in text and 11/04/2026 in tables, never 04/11/2026. The browser's native date picker follows the browser language, so an en-US browser still shows mm/dd/yyyy. Label date fields clearly, and test with an en-GB and an Arabic browser.
- **Digits:** show Western digits (0-9) in both languages for VINs, km, dates and money. Inputs still accept Arabic-Indic digits (`parseVin` already does).
- **Distance:** km with thousands separators, e.g. 88,300 km.
- **Money** (only if a feature ever shows prices): AED 1,250.
- **Phone numbers:** +971 and 9 digits, e.g. +971 50 000 0000. Demo numbers must be obviously fictional.
- **Addresses:** emirate plus area. The UAE has no postal codes, so never ask for one.
- **Emirates** (official English spelling): Abu Dhabi, Dubai, Sharjah, Ajman, Umm Al Quwain, Ras Al Khaimah, Fujairah.
- **Names:** one "Full name" field shown as entered, e.g. "Mariam Al Hashimi". Arabic names do not split cleanly into first and last.

## Tone
- Clear, polite and neutral, in short sentences that translate cleanly into Arabic. No idioms, slang or jokes.
- Error messages say what happened and what to do next.
- Keep text and imagery culturally appropriate for a general UAE audience.

## Trust and legal
- Sijil is a demo, not a government service. Never write or imply "official" or "RTA/police approved", and don't borrow wording from government vehicle portals. Keep the footer disclaimer on every page.
- Don't use the UAE flag, the national emblem, government or police logos, photos of public figures, car-brand logos, or trademarked landmarks.
- Don't ask for Emirates ID numbers. The consumer report describes the vehicle and never its owner (see `ARCHITECTURE.md`).

## Theme
- Keep the brand green (`brand-700` `#126150`). It reads as trustworthy and has strong contrast. Add any new colour, such as a warm "sand" surface, as a token in `frontend/src/index.css` first, then use the token (see `DESIGN_SYSTEM.md`).
- Use red only for errors and destructive actions. Don't arrange green, white, black and red into flag-like stripes.
- Contrast must be at least 4.5:1 for text and 3:1 for control borders, so the app stays readable on a phone in sunlight.
- **RTL (HA-03):** mirror the layout and the arrow/chevron icons. VINs, km, numbers and code stay left-to-right.
- **Fonts must work offline:** use the system fonts we have now, or self-hosted font files in the repo, never a font CDN. If an Arabic web font is added, pick an openly licensed one (e.g. Noto Sans Arabic or IBM Plex Sans Arabic) and bundle it.

## Demo and mock data
- **Cars:** use models among the most common on UAE roads: Toyota Land Cruiser, Nissan Patrol, Toyota Camry, Nissan Sunny, Toyota Prado, Mitsubishi Pajero, Lexus LX, Hyundai Accent, Kia Sportage, Chevrolet Tahoe. Give them realistic VIN prefixes for the brand (JT… Toyota Japan, JN… Nissan Japan).
- **Mileage:** about 20,000-30,000 km a year.
- **Services that match the climate:** A/C service, battery replacement (heat shortens battery life), tyres, air filters (dust), coolant and oil changes.
- **Organisations:** invented names with local flavour, each in an emirate (Falcon Bay Auto Care in Dubai, Oasis Line Motors in Abu Dhabi, Sand Dune Garage in Sharjah). Never use a real company.
- **People:** invented names that reflect the population mix (Mariam Al Hashimi, Khalid Al Mansoori, Arjun Nair, Fatima Al Zaabi, Joseph Santos, Omar Haddad). Emails stay on `@sijil.demo`.

The seed (`backend/app/seed.py`) follows these rules, and the frontend test fixtures mirror it. The demo VINs are listed in `backend/README.md`.

## Checklist for pull requests that change UI
- [ ] Copy uses the words above, UK spelling and day-before-month dates.
- [ ] Nothing implies official or government status. No flags, emblems or real logos.
- [ ] New colours are tokens. Contrast is at least 4.5:1 for text and 3:1 for controls.
- [ ] Works at 375px wide, and in Arabic/RTL once HA-03 lands (every string goes through i18n).
- [ ] Demo data, fixtures and screenshots use the cars, names and places above.
