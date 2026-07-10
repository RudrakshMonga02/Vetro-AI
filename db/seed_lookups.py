"""
Seeds small reference/lookup tables with real-world values:
Karnataka districts, real IPC acts/sections, real crime head
classifications, etc. These are deterministic, not Faker-random,
because judges (and your own sanity) will notice fake district names.

Safe to re-run: uses get_or_create style inserts keyed on natural id.
"""
from db.connection import get_session
from db.models import (
    State, District, UnitType, Unit, Rank, Designation,
    CaseCategory, GravityOffence, CaseStatusMaster, Court,
    Act, Section, CrimeHead, CrimeSubHead,
    CasteMaster, ReligionMaster, OccupationMaster,
)

KARNATAKA_DISTRICTS = [
    "Bagalkot", "Ballari", "Belagavi", "Bengaluru Rural", "Bengaluru Urban",
    "Bidar", "Chamarajanagar", "Chikballapur", "Chikkamagaluru", "Chitradurga",
    "Dakshina Kannada", "Davanagere", "Dharwad", "Gadag", "Hassan", "Haveri",
    "Kalaburagi", "Kodagu", "Kolar", "Koppal", "Mandya", "Mysuru", "Raichur",
    "Ramanagara", "Shivamogga", "Tumakuru", "Udupi", "Uttara Kannada",
    "Vijayapura", "Vijayanagara", "Yadgir",
]

CASE_CATEGORIES = ["FIR", "UDR", "Zero FIR", "PAR"]

GRAVITY_LEVELS = ["Heinous", "Non-Heinous"]

CASE_STATUSES = [
    "Under Investigation", "Charge Sheeted", "Closed", "Undetected", "False Case",
]

# (ActCode, ActDescription, ShortName)
ACTS = [
    ("IPC", "Indian Penal Code", "IPC"),
    ("NDPS", "Narcotic Drugs and Psychotropic Substances Act", "NDPS"),
    ("IT_ACT", "Information Technology Act", "IT Act"),
    ("MV_ACT", "Motor Vehicles Act", "MV Act"),
    ("POCSO", "Protection of Children from Sexual Offences Act", "POCSO"),
]

# (ActCode, SectionCode, Description)
SECTIONS = [
    ("IPC", "302", "Murder"),
    ("IPC", "307", "Attempt to murder"),
    ("IPC", "376", "Rape"),
    ("IPC", "379", "Theft"),
    ("IPC", "392", "Robbery"),
    ("IPC", "420", "Cheating"),
    ("IPC", "354", "Assault on woman with intent to outrage modesty"),
    ("IPC", "323", "Voluntarily causing hurt"),
    ("IPC", "506", "Criminal intimidation"),
    ("NDPS", "20", "Possession/sale of cannabis"),
    ("IT_ACT", "66C", "Identity theft"),
    ("IT_ACT", "66D", "Cheating by personation using computer"),
    ("MV_ACT", "184", "Dangerous driving"),
    ("POCSO", "4", "Penetrative sexual assault on a child"),
]

# (CrimeGroupName, [sub-heads])
CRIME_HEADS = {
    "Crimes Against Body": ["Murder", "Attempt to Murder", "Grievous Hurt", "Assault"],
    "Crimes Against Property": ["Theft", "Robbery", "Burglary", "Dacoity"],
    "Crimes Against Women": ["Rape", "Molestation", "Dowry Harassment", "Domestic Violence"],
    "Cybercrime": ["Online Fraud", "Identity Theft", "Cyberstalking", "Phishing"],
    "Crimes Against Children": ["POCSO Offences", "Child Trafficking"],
    "Narcotics": ["Drug Possession", "Drug Trafficking"],
    "Traffic Offences": ["Rash Driving", "Hit and Run"],
    "Public Order": ["Rioting", "Unlawful Assembly", "Criminal Intimidation"],
}

RELIGIONS = ["Hindu", "Muslim", "Christian", "Sikh", "Jain", "Buddhist", "Other"]
CASTES = ["General", "OBC", "SC", "ST", "Other"]
OCCUPATIONS = [
    "Farmer", "Government Employee", "Private Employee", "Business",
    "Daily Wage Labourer", "Student", "Unemployed", "Homemaker", "Other",
]

UNIT_TYPES = [
    ("Police Station", "City", 3),
    ("Circle Office", "District", 2),
    ("District HQ", "District", 1),
]

RANKS = ["Constable", "Head Constable", "ASI", "SI", "PSI", "CPI", "DSP", "SP"]

DESIGNATIONS = ["Investigating Officer", "SHO", "Beat Officer", "Duty Officer"]


def seed_lookups():
    session = get_session()
    try:
        # State
        if not session.query(State).filter_by(StateID=1).first():
            session.add(State(StateID=1, StateName="Karnataka", NationalityID=1, Active=True))
        session.flush()

        # Districts
        for i, name in enumerate(KARNATAKA_DISTRICTS, start=1):
            if not session.query(District).filter_by(DistrictID=i).first():
                session.add(District(DistrictID=i, DistrictName=name, StateID=1, Active=True))

        # Unit types
        for i, (name, level, hier) in enumerate(UNIT_TYPES, start=1):
            if not session.query(UnitType).filter_by(UnitTypeID=i).first():
                session.add(UnitType(UnitTypeID=i, UnitTypeName=name, CityDistState=level,
                                      Hierarchy=hier, Active=True))
        session.flush()

        # One "Police Station" unit per district, for FK completeness
        for i, name in enumerate(KARNATAKA_DISTRICTS, start=1):
            if not session.query(Unit).filter_by(UnitID=i).first():
                session.add(Unit(UnitID=i, UnitName=f"{name} Town PS", TypeID=1,
                                  StateID=1, DistrictID=i, Active=True))

        # Ranks
        for i, name in enumerate(RANKS, start=1):
            if not session.query(Rank).filter_by(RankID=i).first():
                session.add(Rank(RankID=i, RankName=name, Hierarchy=i, Active=True))

        # Designations
        for i, name in enumerate(DESIGNATIONS, start=1):
            if not session.query(Designation).filter_by(DesignationID=i).first():
                session.add(Designation(DesignationID=i, DesignationName=name,
                                         Active=True, SortOrder=i))

        # Case categories
        for i, name in enumerate(CASE_CATEGORIES, start=1):
            if not session.query(CaseCategory).filter_by(CaseCategoryID=i).first():
                session.add(CaseCategory(CaseCategoryID=i, LookupValue=name))

        # Gravity
        for i, name in enumerate(GRAVITY_LEVELS, start=1):
            if not session.query(GravityOffence).filter_by(GravityOffenceID=i).first():
                session.add(GravityOffence(GravityOffenceID=i, LookupValue=name))

        # Case status
        for i, name in enumerate(CASE_STATUSES, start=1):
            if not session.query(CaseStatusMaster).filter_by(CaseStatusID=i).first():
                session.add(CaseStatusMaster(CaseStatusID=i, CaseStatusName=name))

        session.flush()

        # Courts - one per district
        for i, name in enumerate(KARNATAKA_DISTRICTS, start=1):
            if not session.query(Court).filter_by(CourtID=i).first():
                session.add(Court(CourtID=i, CourtName=f"District & Sessions Court, {name}",
                                   DistrictID=i, StateID=1, Active=True))

        # Acts
        for code, desc, short in ACTS:
            if not session.query(Act).filter_by(ActCode=code).first():
                session.add(Act(ActCode=code, ActDescription=desc, ShortName=short, Active=True))
        session.flush()

        # Sections
        for act_code, sec_code, desc in SECTIONS:
            if not session.query(Section).filter_by(ActCode=act_code, SectionCode=sec_code).first():
                session.add(Section(ActCode=act_code, SectionCode=sec_code,
                                     SectionDescription=desc, Active=True))

        # Crime heads + sub-heads
        head_id = 1
        subhead_id = 1
        for group_name, subheads in CRIME_HEADS.items():
            if not session.query(CrimeHead).filter_by(CrimeHeadID=head_id).first():
                session.add(CrimeHead(CrimeHeadID=head_id, CrimeGroupName=group_name, Active=True))
            session.flush()
            for seq, sub in enumerate(subheads, start=1):
                if not session.query(CrimeSubHead).filter_by(CrimeSubHeadID=subhead_id).first():
                    session.add(CrimeSubHead(CrimeSubHeadID=subhead_id, CrimeHeadID=head_id,
                                              CrimeHeadName=sub, SeqID=seq))
                subhead_id += 1
            head_id += 1

        # People-attribute lookups
        for i, name in enumerate(RELIGIONS, start=1):
            if not session.query(ReligionMaster).filter_by(ReligionID=i).first():
                session.add(ReligionMaster(ReligionID=i, ReligionName=name))

        for i, name in enumerate(CASTES, start=1):
            if not session.query(CasteMaster).filter_by(caste_master_id=i).first():
                session.add(CasteMaster(caste_master_id=i, caste_master_name=name))

        for i, name in enumerate(OCCUPATIONS, start=1):
            if not session.query(OccupationMaster).filter_by(OccupationID=i).first():
                session.add(OccupationMaster(OccupationID=i, OccupationName=name))

        session.commit()
        print("Lookup tables seeded successfully.")
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    seed_lookups()
