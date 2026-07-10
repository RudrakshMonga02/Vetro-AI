"""
Generates ~2,500 CaseMaster rows plus child records (Victim, Accused,
ComplainantDetails, ArrestSurrender, ActSectionAssociation) using Faker.
Lat/lng are bounded to Karnataka's actual geographic extent so the
hotspot map isn't showing points in the ocean.

Re-running this wipes and regenerates case-level data only (lookups
are untouched) -- useful while iterating on the schema/shape of dummy
data before the real dataset lands.
"""
import random
from datetime import date, datetime, timedelta

from faker import Faker

from db.connection import get_session
from db.models import (
    CaseMaster, Victim, Accused, ComplainantDetails, ArrestSurrender,
    InvArrestSurrenderAccused, ActSectionAssociation, District,
    CaseCategory, GravityOffence, CrimeHead, CrimeSubHead,
    CaseStatusMaster, Section, Unit,
)

fake = Faker("en_IN")
random.seed(42)

# Karnataka's approximate bounding box
LAT_RANGE = (11.5, 18.5)
LNG_RANGE = (74.0, 78.5)

NUM_CASES = 1000
START_DATE = date(2022, 1, 1)
END_DATE = date(2026, 6, 30)

GENDERS = ["M", "F", "T"]


def random_date(start: date, end: date) -> date:
    delta = (end - start).days
    return start + timedelta(days=random.randint(0, delta))


def random_karnataka_point():
    lat = round(random.uniform(*LAT_RANGE), 6)
    lng = round(random.uniform(*LNG_RANGE), 6)
    return lat, lng


def build_crime_no(category_code: int, district_id: int, unit_id: int, year: int, serial: int) -> str:
    # 1 digit category + 4 digit district + 4 digit unit + 4 digit year + 5 digit serial
    return f"{category_code}{district_id:04d}{unit_id:04d}{year}{serial:05d}"


def seed_cases(num_cases: int = NUM_CASES):
    session = get_session()
    try:
        district_ids = [d.DistrictID for d in session.query(District.DistrictID).all()]
        category_ids = [c.CaseCategoryID for c in session.query(CaseCategory.CaseCategoryID).all()]
        gravity_ids = [g.GravityOffenceID for g in session.query(GravityOffence.GravityOffenceID).all()]
        status_ids = [s.CaseStatusID for s in session.query(CaseStatusMaster.CaseStatusID).all()]
        subheads = session.query(CrimeSubHead.CrimeSubHeadID, CrimeSubHead.CrimeHeadID).all()
        sections = session.query(Section.ActCode, Section.SectionCode).all()
        unit_ids = [u.UnitID for u in session.query(Unit.UnitID).all()]

        if not district_ids or not subheads:
            raise RuntimeError("Lookup tables are empty. Run `python -m db.seed_lookups` first.")

        serial_counters = {}  # (district, unit, category, year) -> running serial

        print(f"Generating {num_cases} CaseMaster rows...")
        for i in range(1, num_cases + 1):
            district_id = random.choice(district_ids)
            unit_id = district_id  # one PS per district, seeded 1:1 in seed_lookups
            category_id = random.choice(category_ids)
            gravity_id = random.choice(gravity_ids)
            status_id = random.choice(status_ids)
            subhead_id, head_id = random.choice(subheads)

            reg_date = random_date(START_DATE, END_DATE)
            year = reg_date.year

            key = (district_id, unit_id, category_id, year)
            serial_counters[key] = serial_counters.get(key, 0) + 1
            serial = serial_counters[key]

            crime_no = build_crime_no(category_id, district_id, unit_id, year, serial)
            case_no = f"{year}{serial:05d}"

            incident_from = datetime.combine(reg_date, datetime.min.time()) - timedelta(
                hours=random.randint(0, 72)
            )
            incident_to = incident_from + timedelta(hours=random.randint(0, 6))
            info_received = incident_to + timedelta(hours=random.randint(0, 24))

            lat, lng = random_karnataka_point()

            case = CaseMaster(
                CaseMasterID=i,
                CrimeNo=crime_no,
                CaseNo=case_no,
                CrimeRegisteredDate=reg_date,
                PolicePersonID=None,  # employees not seeded in this pass; optional FK
                PoliceStationID=unit_id,
                CaseCategoryID=category_id,
                GravityOffenceID=gravity_id,
                CrimeMajorHeadID=head_id,
                CrimeMinorHeadID=subhead_id,
                CaseStatusID=status_id,
                CourtID=district_id,  # one court per district, seeded 1:1
                DistrictID=district_id,
                IncidentFromDate=incident_from,
                IncidentToDate=incident_to,
                InfoReceivedPSDate=info_received,
                latitude=lat,
                longitude=lng,
                BriefFacts=None,  # filled in later by rag/generate_briefs.py
            )
            session.add(case)
            session.flush()  # ensure CaseMaster row exists before child FK inserts

            # 1 act-section per case (sometimes 2)
            act_code, sec_code = random.choice(sections)
            session.add(ActSectionAssociation(
                CaseMasterID=i, ActID=act_code, SectionID=sec_code,
                ActOrderID=1, SectionOrderID=1,
            ))
            if random.random() < 0.2:
                act_code2, sec_code2 = random.choice(sections)
                session.add(ActSectionAssociation(
                    CaseMasterID=i, ActID=act_code2, SectionID=sec_code2,
                    ActOrderID=2, SectionOrderID=2,
                ))

            # 1 complainant per case
            session.add(ComplainantDetails(
                CaseMasterID=i,
                ComplainantName=fake.name(),
                AgeYear=random.randint(18, 75),
                OccupationID=random.randint(1, 9),
                ReligionID=random.randint(1, 7),
                CasteID=random.randint(1, 5),
                GenderID=random.choice([1, 2]),
            ))

            # 1-3 victims
            for _ in range(random.randint(1, 3)):
                session.add(Victim(
                    CaseMasterID=i,
                    VictimName=fake.name(),
                    AgeYear=random.randint(5, 80),
                    GenderID=random.choice(GENDERS),
                    VictimPolice="0",
                ))

            # 0-3 accused
            num_accused = random.choices([0, 1, 2, 3], weights=[0.1, 0.5, 0.3, 0.1])[0]
            accused_records = []
            for a_idx in range(num_accused):
                accused_records.append(Accused(
                    CaseMasterID=i,
                    AccusedName=fake.name(),
                    AgeYear=random.randint(16, 70),
                    GenderID=random.choice(GENDERS),
                    PersonID=f"A{a_idx + 1}",
                ))
            session.add_all(accused_records)
            session.flush()  # get AccusedMasterID values for arrest records

            # Arrest/surrender events. Real arrests often net multiple
            # accused in one raid, so we group accused into events
            # (1 event per accused most of the time, but ~25% of cases
            # with 2+ accused get a single joint-arrest event) and link
            # each accused to their event via the junction table -- this
            # exercises the many-to-many ArrestSurrender<->Accused shape
            # from the official ER diagram instead of faking a 1:1.
            arrestable = [a for a in accused_records if random.random() < 0.6]
            if arrestable:
                joint_arrest = len(arrestable) >= 2 and random.random() < 0.25
                groups = [arrestable] if joint_arrest else [[a] for a in arrestable]

                for group in groups:
                    arrest_date = reg_date + timedelta(days=random.randint(0, 60))
                    event = ArrestSurrender(
                        CaseMasterID=i,
                        ArrestSurrenderTypeID=random.choice([1, 2]),
                        ArrestSurrenderDate=arrest_date,
                        ArrestSurrenderStateId=1,
                        ArrestSurrenderDistrictId=district_id,
                        PoliceStationID=unit_id,
                        IOID=None,
                        CourtID=district_id,
                    )
                    session.add(event)
                    session.flush()  # get ArrestSurrenderID for junction rows

                    for idx, accused in enumerate(group):
                        session.add(InvArrestSurrenderAccused(
                            ArrestSurrenderID=event.ArrestSurrenderID,
                            AccusedMasterID=accused.AccusedMasterID,
                            IsAccused=(idx == 0),  # first person = primary accused
                            IsComplainantAccused=False,
                        ))

            if i % 500 == 0:
                session.commit()
                print(f"  committed {i}/{num_cases}")

        session.commit()
        print(f"Done. {num_cases} cases generated with child records.")
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    seed_cases()
