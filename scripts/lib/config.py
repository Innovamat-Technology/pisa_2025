"""Paths, file names and item lists shared by every script."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = Path(os.environ.get("PISA_RAW_DIR") or ROOT / "data" / "raw")
EXTRACT = ROOT / "data" / "extract"      # step 1 output, versioned with Git LFS (see data/README.md)
INTERIM = ROOT / "data" / "interim"      # everything else, rebuilt on every run
RESULTS = ROOT / "results"
TABLES = RESULTS / "tables"
FIGURES = RESULTS / "figures"
for _p in (EXTRACT, INTERIM, TABLES, FIGURES):
    _p.mkdir(parents=True, exist_ok=True)

# Student questionnaire files of the OECD public-use releases (SPSS format).
SAV = {2015: "CY6_MS_CMB_STU_QQQ.sav", 2018: "CY07_MSU_STU_QQQ.sav",
       2022: "CY08MSP_STU_QQQ.SAV", 2025: "CY09_MS_STU_PUF.sav"}

N_REP, N_PV, SEED = 80, 10, 7
DOMAINS = ("math", "read", "scie")
PV = [f"PV{i}{d.upper()}" for d in DOMAINS for i in range(1, N_PV + 1)]
REPW = [f"W_FSTURWT{i}" for i in range(1, N_REP + 1)]

# --- home possessions items -------------------------------------------------
BIN = [f"ST250Q0{i}JA" for i in range(1, 6)]                       # yes / no
CNT4 = ["ST251Q01JA", "ST251Q03JA", "ST251Q04JA", "ST251Q06JA", "ST251Q07JA"]
DEV = [f"ST254Q0{i}JA" for i in range(1, 6)]                       # 5 = "I don't know"
BOOKS = "ST255Q01JA"
COMMON = BIN + CNT4 + DEV + [BOOKS]                                # the 16 items in both cycles
BOOKTYPES = [f"ST256Q{i:02d}JA" for i in (1, 2, 3, 6, 7, 8, 9, 10)]  # 2022 only
DROPPED_OTHER = ["ST253Q01JA", "ST254Q06JA", "ST251Q02JA"]         # 2022 only
NATIONAL = [f"ST250Q{i:02d}DA" for i in list(range(8, 17)) + list(range(18, 29))]  # 2025 only

# 2015 and 2018: yes/no possessions (ST011), counts (ST012) and number of books (ST013)
ITEMS_2015_2018 = ([f"ST011Q{i:02d}TA" for i in range(1, 13)] + ["ST011Q16NA"]
                   + ["ST012Q01TA", "ST012Q02TA", "ST012Q03TA", "ST012Q05NA", "ST012Q06NA", "ST012Q07NA",
                      "ST012Q08NA", "ST012Q09NA", "ST013Q01TA"])

LABELS = {
    "ST250Q01JA": "A room of your own", "ST250Q02JA": "Computer for schoolwork",
    "ST250Q03JA": "Educational software", "ST250Q04JA": "Own phone with internet",
    "ST250Q05JA": "Internet access", "ST251Q01JA": "Cars", "ST251Q03JA": "Bathrooms",
    "ST251Q04JA": "Flush toilets", "ST251Q06JA": "Musical instruments", "ST251Q07JA": "Works of art",
    "ST254Q01JA": "Televisions", "ST254Q02JA": "Desktop computers", "ST254Q03JA": "Laptops",
    "ST254Q04JA": "Tablets", "ST254Q05JA": "E-book readers", "ST255Q01JA": "Books at home (number)",
    "ST256Q01JA": "Religious books", "ST256Q02JA": "Classical literature",
    "ST256Q03JA": "Contemporary literature", "ST256Q06JA": "Science books",
    "ST256Q07JA": "Art/music/design books", "ST256Q08JA": "Technical reference books",
    "ST256Q09JA": "Dictionaries", "ST256Q10JA": "Books for schoolwork",
    "ST253Q01JA": "Screen devices (number)", "ST254Q06JA": "Cell phones (number)",
    "ST251Q02JA": "Mopeds/motorcycles",
    "ST250Q08DA": "Electric lighting", "ST250Q09DA": "Plumbed water", "ST250Q10DA": "Off-street parking",
    "ST250Q11DA": "Garbage collection", "ST250Q12DA": "Stove/burner", "ST250Q13DA": "Table for meals",
    "ST250Q14DA": "Vacuum cleaner", "ST250Q15DA": "Refrigerator", "ST250Q16DA": "Sewer connection",
    "ST250Q18DA": "Air conditioning/heating", "ST250Q19DA": "Guest room",
    "ST250Q20DA": "Quiet place to study", "ST250Q21DA": "Swimming pool/jacuzzi",
    "ST250Q22DA": "Security system", "ST250Q23DA": "Smart TV", "ST250Q24DA": "Dishwasher",
    "ST250Q25DA": "Own tablet", "ST250Q26DA": "TV/streaming subscription",
    "ST250Q27DA": "Domestic workers", "ST250Q28DA": "Newspaper subscription",
}

# Costa Rica is flagged as OECD in both files but has no ESCS, HISEI or PARED in either.
EXCLUDE = ["CRI"]
