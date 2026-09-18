# SweetAstro Vedic Astrology Specification v1.0

**Status**: Frozen Baseline for V1 Backtesting & Prediction  
**Effective Date**: 2026-09-09  
**Specification ID**: SA-SPEC-V1.0  

---

## 1. Mathematical & Astronomical Foundation

### 1.1 Ayanamsha
* **Primary Standard**: **Lahiri (Chitra Paksha) Ayanamsha**.
* **Definition**: The longitude of the star Spica (Chitra) is fixed at exactly 180° 00' 00'' (0° Libra).
* **Formula**:
  $$\text{Ayanamsha}(T) = 23^\circ 51' 25.53'' + 5029.0966'' \cdot T + 1.1120'' \cdot T^2$$
  where $T$ is the Julian centuries from J2000.0 ($T = (\text{JD} - 2451545.0) / 36525$).
* **Tournament Variants** (Available for comparative backtesting in V2): Raman, Krishnamurti (KP), True Chitra.

### 1.2 Coordinate System & Sidereal Longitude
* All planetary longitudes are computed in the geocentric ecliptic coordinate system.
* Tropical longitude is converted to sidereal via:
  $$\lambda_{\text{sidereal}} = (\lambda_{\text{tropical}} - \text{Ayanamsha}) \pmod{360^\circ}$$

### 1.3 Ascendant (Lagna) & House System
* **Lagna Calculation**: Derived from the Local Sidereal Time (LST) and geographical latitude $\phi$ of the birth location.
* **V1 House System**: **Whole Sign (Rashi-as-House)**.
  * The sign containing the Ascendant is designated as House 1 (Bhava 1, 0° to 30° of that sign).
  * Subsequent signs in zodiacal order constitute Houses 2 through 12.
  * The exact degree of the Ascendant represents the sensitive Lagna point.
* **V2 Extended System**: Bhava Chalita (Sripathi) for evaluating house cusp boundaries and planet transitions across cusps.

---

## 2. Divisional Charts (Vargas)

### 2.1 Navamsa (D9)
* Each zodiac sign (30°) is divided into 9 equal parts (Navamsas) of 3° 20' (which equals one Nakshatra Pada).
* Total Navamsas in the zodiac = 12 × 9 = 108.
* **Sign Assignment Convention (Parashara Standard)**:
  * **Fire Signs** (Aries, Leo, Sagittarius): Navamsas start from **Aries** through Sagittarius.
  * **Earth Signs** (Taurus, Virgo, Capricorn): Navamsas start from **Capricorn** through Virgo.
  * **Air Signs** (Gemini, Libra, Aquarius): Navamsas start from **Libra** through Gemini.
  * **Water Signs** (Cancer, Scorpio, Pisces): Navamsas start from **Cancer** through Pisces.
* **Navamsa Lagna (D9 Ascendant)**: Computed by projecting the exact degree of the D1 Ascendant into its corresponding Navamsa sign.

---

## 3. Aspects (Drishti)

### 3.1 Parashara Standard Drishti
* All planets cast a **full aspect (100% / 7th house aspect)** on the house and planets located in the 7th house from themselves (inclusive counting: sign + 6).
* **Special Full Aspects**:
  * **Mars**: Aspects 4th, 7th, and 8th houses from its position.
  * **Jupiter**: Aspects 5th, 7th, and 9th houses from its position.
  * **Saturn**: Aspects 3rd, 7th, and 10th houses from its position.
  * **Rahu & Ketu**: Cast 5th, 7th, and 9th aspects (trinal aspects, evaluated in Category C rules).

---

## 4. Dasha Calculation (Vimshottari)

### 4.1 Base System
* **Cycle Duration**: 120 solar years across 9 planetary lords in classical sequence:
  1. Sun (Surya): 6 years
  2. Moon (Chandra): 10 years
  3. Mars (Mangala): 7 years
  4. Rahu: 18 years
  5. Jupiter (Guru): 16 years
  6. Saturn (Shani): 19 years
  7. Mercury (Budha): 17 years
  8. Ketu: 7 years
  9. Venus (Shukra): 20 years

### 4.2 Solar Year Standard
* **Temporal Standard**: 1 Tropical Year = 365.2425 mean solar days.
* Prevents cumulative multi-month drift over decades of life.

### 4.3 Balance of Birth Dasha
* Determined by the exact position of the natal Moon within its Nakshatra (13° 20' = 800' of arc):
  $$\text{Fraction Traversed} = \frac{\lambda_{\text{Moon}} \pmod{13^\circ 20'}}{13^\circ 20'}$$
  $$\text{Balance Remaining} = (1 - \text{Fraction Traversed}) \times \text{Duration}(\text{Nakshatra Lord})$$

### 4.4 Sub-Periods
* **Antardasha (AD)**:
  $$\text{Duration}(\text{AD}_j \text{ in } \text{MD}_i) = \text{Duration}(\text{MD}_i) \times \frac{\text{Duration}(\text{Lord}_j)}{120}$$
* **Pratyantardasha (PD)**:
  $$\text{Duration}(\text{PD}_k \text{ in } \text{AD}_j) = \text{Duration}(\text{AD}_j) \times \frac{\text{Duration}(\text{Lord}_k)}{120}$$

---

## 5. Transit Activations (Gochara)

### 5.1 Planetary Speeds & Windows
* **Jupiter**: ~12 months per sign.
* **Saturn**: ~2.5 years per sign.
* **Rahu / Ketu**: ~18 months per sign (retrograde motion).

### 5.2 Double Transit Principle (K.N. Rao Baseline)
Marriage requires simultaneous activation by transit Saturn and transit Jupiter:
1. **Jupiter Transit**: Must transit over, or cast a classical aspect on:
   - Natal 7th house (or 7th lord), OR
   - Natal 1st house (Lagna or Lagna lord), OR
   - Natal Venus (Karaka for marriage) or Jupiter (Karaka in female charts).
2. **Saturn Transit**: Must transit over, or cast a classical aspect on:
   - Natal 7th house / 7th lord, OR
   - Natal 1st house / Lagna lord.

---

## 6. Jaimini Karakas & Arudhas

### 6.1 7-Chara Karaka Scheme
* The 7 physical planets (Sun, Moon, Mars, Mercury, Jupiter, Venus, Saturn) ordered strictly by longitude within their signs (0° to 30°):
  1. **Atmakaraka (AK)**: Highest longitude.
  2. **Amatyakaraka (AmK)**: 2nd highest.
  3. **Bhratrukaraka (BK)**: 3rd highest.
  4. **Matrukaraka (MK)**: 4th highest.
  5. **Putrakaraka (PK)**: 5th highest.
  6. **Gnatikaraka (GK)**: 6th highest.
  7. **Darakaraka (DK)**: Lowest longitude. Represents spouse and marriage timing.

### 6.2 Upapada Lagna (UL)
* Arudha of the 12th house (Vyaya Bhava):
  * Let $S_{12}$ be the sign of the 12th house, and $L_{12}$ be the sign occupied by the lord of the 12th house.
  * Count distance $d$ from $S_{12}$ to $L_{12}$.
  * Upapada Lagna $\text{UL} = L_{12} + (d - 1)$ signs.
  * *Exception rule*: If the resulting sign falls in the 12th or 6th from the 12th house, project 10 signs forward.
