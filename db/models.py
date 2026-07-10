"""
SQLAlchemy models for the Karnataka SCRB FIR system, based on the
provided ER diagram. Indexes are added on columns used for filtering/
joining in analytics queries (district, dates, crime heads) so this
schema behaves the same whether it holds 2,500 rows or 250,000.
"""
from sqlalchemy import (
    Column, Integer, String, Date, DateTime, Numeric, Text, Boolean,
    ForeignKey, ForeignKeyConstraint, Index
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


# ---------- Lookup / master tables ----------

class State(Base):
    __tablename__ = "state"
    StateID = Column(Integer, primary_key=True)
    StateName = Column(String, nullable=False)
    NationalityID = Column(Integer)
    Active = Column(Boolean, default=True)


class District(Base):
    __tablename__ = "district"
    DistrictID = Column(Integer, primary_key=True)
    DistrictName = Column(String, nullable=False, index=True)
    StateID = Column(Integer, ForeignKey("state.StateID"))
    Active = Column(Boolean, default=True)


class UnitType(Base):
    __tablename__ = "unit_type"
    UnitTypeID = Column(Integer, primary_key=True)
    UnitTypeName = Column(String, nullable=False)
    CityDistState = Column(String)
    Hierarchy = Column(Integer)
    Active = Column(Boolean, default=True)


class Unit(Base):
    __tablename__ = "unit"
    UnitID = Column(Integer, primary_key=True)
    UnitName = Column(String, nullable=False)
    TypeID = Column(Integer, ForeignKey("unit_type.UnitTypeID"))
    ParentUnit = Column(Integer, ForeignKey("unit.UnitID"), nullable=True)
    NationalityID = Column(Integer)
    StateID = Column(Integer, ForeignKey("state.StateID"))
    DistrictID = Column(Integer, ForeignKey("district.DistrictID"), index=True)
    Active = Column(Boolean, default=True)


class Rank(Base):
    __tablename__ = "rank_master"
    RankID = Column(Integer, primary_key=True)
    RankName = Column(String, nullable=False)
    Hierarchy = Column(Integer)
    Active = Column(Boolean, default=True)


class Designation(Base):
    __tablename__ = "designation"
    DesignationID = Column(Integer, primary_key=True)
    DesignationName = Column(String, nullable=False)
    Active = Column(Boolean, default=True)
    SortOrder = Column(Integer)


class Employee(Base):
    __tablename__ = "employee"
    EmployeeID = Column(Integer, primary_key=True)
    DistrictID = Column(Integer, ForeignKey("district.DistrictID"), index=True)
    UnitID = Column(Integer, ForeignKey("unit.UnitID"), index=True)
    RankID = Column(Integer, ForeignKey("rank_master.RankID"))
    DesignationID = Column(Integer, ForeignKey("designation.DesignationID"))
    KGID = Column(String, unique=True)
    FirstName = Column(String, nullable=False)
    EmployeeDOB = Column(Date)
    GenderID = Column(Integer)
    BloodGroupID = Column(Integer)
    PhysicallyChallenged = Column(Boolean, default=False)
    AppointmentDate = Column(Date)


class CaseCategory(Base):
    __tablename__ = "case_category"
    CaseCategoryID = Column(Integer, primary_key=True)
    LookupValue = Column(String, nullable=False)  # FIR, UDR, Zero FIR, PAR


class GravityOffence(Base):
    __tablename__ = "gravity_offence"
    GravityOffenceID = Column(Integer, primary_key=True)
    LookupValue = Column(String, nullable=False)  # Heinous, Non-Heinous


class CaseStatusMaster(Base):
    __tablename__ = "case_status_master"
    CaseStatusID = Column(Integer, primary_key=True)
    CaseStatusName = Column(String, nullable=False)


class Court(Base):
    __tablename__ = "court"
    CourtID = Column(Integer, primary_key=True)
    CourtName = Column(String, nullable=False)
    DistrictID = Column(Integer, ForeignKey("district.DistrictID"))
    StateID = Column(Integer, ForeignKey("state.StateID"))
    Active = Column(Boolean, default=True)


class Act(Base):
    __tablename__ = "act"
    ActCode = Column(String, primary_key=True)
    ActDescription = Column(String, nullable=False)
    ShortName = Column(String)
    Active = Column(Boolean, default=True)


class Section(Base):
    __tablename__ = "section"
    SectionCode = Column(String, primary_key=True)
    ActCode = Column(String, ForeignKey("act.ActCode"), primary_key=True)
    SectionDescription = Column(String)
    Active = Column(Boolean, default=True)


class CrimeHead(Base):
    __tablename__ = "crime_head"
    CrimeHeadID = Column(Integer, primary_key=True)
    CrimeGroupName = Column(String, nullable=False)  # e.g. Crimes Against Body
    Active = Column(Boolean, default=True)


class CrimeSubHead(Base):
    __tablename__ = "crime_sub_head"
    CrimeSubHeadID = Column(Integer, primary_key=True)
    CrimeHeadID = Column(Integer, ForeignKey("crime_head.CrimeHeadID"), index=True)
    CrimeHeadName = Column(String, nullable=False)  # e.g. Murder, Robbery
    SeqID = Column(Integer)


class CrimeHeadActSection(Base):
    __tablename__ = "crime_head_act_section"
    id = Column(Integer, primary_key=True, autoincrement=True)
    CrimeHeadID = Column(Integer, ForeignKey("crime_head.CrimeHeadID"))
    ActCode = Column(String, ForeignKey("act.ActCode"))
    SectionCode = Column(String)


class CasteMaster(Base):
    __tablename__ = "caste_master"
    caste_master_id = Column(Integer, primary_key=True)
    caste_master_name = Column(String, nullable=False)


class ReligionMaster(Base):
    __tablename__ = "religion_master"
    ReligionID = Column(Integer, primary_key=True)
    ReligionName = Column(String, nullable=False)


class OccupationMaster(Base):
    __tablename__ = "occupation_master"
    OccupationID = Column(Integer, primary_key=True)
    OccupationName = Column(String, nullable=False)


# ---------- Core case tables ----------

class CaseMaster(Base):
    __tablename__ = "case_master"
    CaseMasterID = Column(Integer, primary_key=True, autoincrement=True)
    CrimeNo = Column(String, unique=True, nullable=False)
    CaseNo = Column(String, nullable=False)
    CrimeRegisteredDate = Column(Date, nullable=False, index=True)
    PolicePersonID = Column(Integer, ForeignKey("employee.EmployeeID"))
    PoliceStationID = Column(Integer, ForeignKey("unit.UnitID"))
    CaseCategoryID = Column(Integer, ForeignKey("case_category.CaseCategoryID"), index=True)
    GravityOffenceID = Column(Integer, ForeignKey("gravity_offence.GravityOffenceID"), index=True)
    CrimeMajorHeadID = Column(Integer, ForeignKey("crime_head.CrimeHeadID"), index=True)
    CrimeMinorHeadID = Column(Integer, ForeignKey("crime_sub_head.CrimeSubHeadID"), index=True)
    CaseStatusID = Column(Integer, ForeignKey("case_status_master.CaseStatusID"), index=True)
    CourtID = Column(Integer, ForeignKey("court.CourtID"))
    DistrictID = Column(Integer, ForeignKey("district.DistrictID"), index=True)
    IncidentFromDate = Column(DateTime)
    IncidentToDate = Column(DateTime)
    InfoReceivedPSDate = Column(DateTime)
    latitude = Column(Numeric(9, 6), index=True)
    longitude = Column(Numeric(9, 6), index=True)
    BriefFacts = Column(Text)

    victims = relationship("Victim", back_populates="case")
    accused = relationship("Accused", back_populates="case")


class ComplainantDetails(Base):
    __tablename__ = "complainant_details"
    ComplainantID = Column(Integer, primary_key=True, autoincrement=True)
    CaseMasterID = Column(Integer, ForeignKey("case_master.CaseMasterID"), index=True)
    ComplainantName = Column(String, nullable=False)
    AgeYear = Column(Integer)
    OccupationID = Column(Integer, ForeignKey("occupation_master.OccupationID"))
    ReligionID = Column(Integer, ForeignKey("religion_master.ReligionID"))
    CasteID = Column(Integer, ForeignKey("caste_master.caste_master_id"))
    GenderID = Column(Integer)


class ActSectionAssociation(Base):
    __tablename__ = "act_section_association"
    id = Column(Integer, primary_key=True, autoincrement=True)
    CaseMasterID = Column(Integer, ForeignKey("case_master.CaseMasterID"), index=True)
    ActID = Column(String, ForeignKey("act.ActCode"), index=True)
    # SectionCode is only unique per Act (composite PK on Section is
    # (SectionCode, ActCode)), so SectionID alone can repeat across acts
    # (e.g. Section 302 exists under both IPC and BNS). We store both
    # halves of the composite key and enforce the FK against that pair,
    # rather than a bare, unenforced string column.
    SectionID = Column(String, index=True)
    ActOrderID = Column(Integer)
    SectionOrderID = Column(Integer)

    __table_args__ = (
        ForeignKeyConstraint(
            ["SectionID", "ActID"],
            ["section.SectionCode", "section.ActCode"],
            name="fk_actsection_section",
        ),
    )


class Victim(Base):
    __tablename__ = "victim"
    VictimMasterID = Column(Integer, primary_key=True, autoincrement=True)
    CaseMasterID = Column(Integer, ForeignKey("case_master.CaseMasterID"), index=True)
    VictimName = Column(String, nullable=False)
    AgeYear = Column(Integer)
    GenderID = Column(String)  # M/F/T
    VictimPolice = Column(String)

    case = relationship("CaseMaster", back_populates="victims")


class Accused(Base):
    __tablename__ = "accused"
    AccusedMasterID = Column(Integer, primary_key=True, autoincrement=True)
    CaseMasterID = Column(Integer, ForeignKey("case_master.CaseMasterID"), index=True)
    AccusedName = Column(String, nullable=False)
    AgeYear = Column(Integer)
    GenderID = Column(String)
    PersonID = Column(String)  # A1, A2, A3...

    case = relationship("CaseMaster", back_populates="accused")


class ArrestSurrender(Base):
    """
    One arrest/surrender EVENT (e.g. a police raid on a given date).
    Per the official ER diagram, one event can link MULTIPLE accused
    persons via the inv_arrestsurrenderaccused junction table below —
    it is a many-to-many relationship, not many-to-one.

    NOTE: AccusedMasterID here is intentionally removed as a direct FK.
    Use the `accused` relationship (backed by the junction table) to
    get all accused linked to this event. If you need "the" primary
    accused for a simple event, take accused[0] or query the junction
    table filtering IsAccused=True.
    """
    __tablename__ = "arrest_surrender"
    ArrestSurrenderID = Column(Integer, primary_key=True, autoincrement=True)
    CaseMasterID = Column(Integer, ForeignKey("case_master.CaseMasterID"), index=True)
    ArrestSurrenderTypeID = Column(Integer)
    ArrestSurrenderDate = Column(Date)
    ArrestSurrenderStateId = Column(Integer, ForeignKey("state.StateID"))
    ArrestSurrenderDistrictId = Column(Integer, ForeignKey("district.DistrictID"))
    PoliceStationID = Column(Integer, ForeignKey("unit.UnitID"))
    IOID = Column(Integer, ForeignKey("employee.EmployeeID"))
    CourtID = Column(Integer, ForeignKey("court.CourtID"))

    accused_links = relationship(
        "InvArrestSurrenderAccused", back_populates="arrest_surrender"
    )


class InvArrestSurrenderAccused(Base):
    """
    Junction table: links one ArrestSurrender EVENT to one or more
    Accused persons. This is what makes ArrestSurrender<->Accused a
    true many-to-many, matching the official ER diagram's
    `inv_arrestsurrenderaccused` entity.

    IsAccused / IsComplainantAccused are per (event, person) flags —
    e.g. in one raid, person A is the primary accused (IsAccused=True)
    while person B is a associate also arrested (IsAccused=False), and
    a complainant who turned out to also be an accused would have
    IsComplainantAccused=True.
    """
    __tablename__ = "inv_arrestsurrenderaccused"
    InvArrestSurrenderAccusedID = Column(Integer, primary_key=True, autoincrement=True)
    ArrestSurrenderID = Column(
        Integer, ForeignKey("arrest_surrender.ArrestSurrenderID"), index=True
    )
    AccusedMasterID = Column(
        Integer, ForeignKey("accused.AccusedMasterID"), index=True
    )
    IsAccused = Column(Boolean, default=True)
    IsComplainantAccused = Column(Boolean, default=False)

    arrest_surrender = relationship("ArrestSurrender", back_populates="accused_links")
    accused = relationship("Accused")


class ChargesheetDetails(Base):
    __tablename__ = "chargesheet_details"
    CSID = Column(Integer, primary_key=True, autoincrement=True)
    CaseMasterID = Column(Integer, ForeignKey("case_master.CaseMasterID"), index=True)
    csdate = Column(DateTime)
    cstype = Column(String)  # A=Chargesheet, B=False Case, C=Undetected
    PolicePersonID = Column(Integer, ForeignKey("employee.EmployeeID"))


# Composite indexes that matter most for the analytics/chart queries
Index("ix_case_district_date", CaseMaster.DistrictID, CaseMaster.CrimeRegisteredDate)
Index("ix_case_crimehead_date", CaseMaster.CrimeMajorHeadID, CaseMaster.CrimeRegisteredDate)


# ---------- Chat: conversations & messages ----------
# Not part of the original FIR ER diagram -- app-level tables for the
# multi-session chat feature (separate "Investigation A/B/C" threads,
# each with its own persisted history). Deliberately plain
# lowercase/snake_case naming (not the PascalCase FIR-style columns
# above) since these aren't part of the provided schema.
#
# This REPLACES the old ConversationMemory cache (in-memory /
# Catalyst Cache) as ChatService's history source -- Postgres is now
# the single source of truth for conversation history, not just a
# prompt-building cache. This also incidentally fixes the
# multi-instance problem the in-memory cache's docstring flagged as
# an AppSail blocker: Postgres is already shared across instances,
# an in-process dict never was.

class Conversation(Base):
    __tablename__ = "conversation"
    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String, nullable=False, default="New Investigation")
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False, index=True)  # drives sidebar ordering
    # Stopgap ownership check until real Catalyst Authentication + RBAC
    # is wired up (see docs/PRD.md vulnerability review). Generated
    # once at creation (secrets.token_urlsafe), returned to the client
    # exactly once, and required as the X-Owner-Token header on every
    # subsequent read/rename/delete/chat call against this
    # conversation. This is NOT a substitute for real multi-user auth
    # (there's no user identity here, just "whoever holds this token
    # owns this thread") -- it exists purely to close the
    # anyone-can-read/delete-any-conversation-by-guessing-the-id hole,
    # not to support real per-user accounts. Replace with Catalyst
    # Authentication + a real user_id FK before this handles real data.
    owner_token = Column(String, nullable=False, index=True)

    messages = relationship(
        "Message", back_populates="conversation", cascade="all, delete-orphan"
    )


class Message(Base):
    __tablename__ = "message"
    id = Column(Integer, primary_key=True, autoincrement=True)
    conversation_id = Column(
        Integer, ForeignKey("conversation.id"), nullable=False, index=True
    )
    role = Column(String, nullable=False)  # "user" | "assistant"
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime, nullable=False)

    conversation = relationship("Conversation", back_populates="messages")
