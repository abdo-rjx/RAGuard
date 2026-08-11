"""Seed demo departments, roles, users (plan Section 18) + generate sample doc files.

Idempotent: safe to re-run. Sample documents are written as .txt into data/sample_docs/
and must be ingested with `python scripts/ingest_documents.py` (that step needs the
embedding model + Chroma).

Usage:
    python scripts/seed_data.py
    python scripts/seed_data.py --reset   # drop existing demo users and re-seed
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.auth.password import hash_password  # noqa: E402
from app.config import settings  # noqa: E402
from app.database import SessionLocal, init_db  # noqa: E402
from app.models.user import Department, Role, User  # noqa: E402

DEPARTMENTS = ["finance", "it", "hr", "security", "executive", "general"]
ROLES = ["ceo", "cfo", "cto", "hr_manager", "security_engineer", "it_engineer", "accountant", "employee"]

# username → (role, home_department, is_admin)
USERS = {
    "ceo01": ("ceo", "executive", True),
    "cfo01": ("cfo", "finance", False),
    "cto01": ("cto", "it", False),
    "hr01": ("hr_manager", "hr", False),
    "seceng01": ("security_engineer", "security", True),
    "iteng01": ("it_engineer", "it", False),
    "accountant01": ("accountant", "finance", False),
    "employee01": ("employee", "general", False),
}

DEMO_PASSWORD = "Password123!"

# Sample documents matching the spec's own examples (plan Section 18).
# (filename, department, classification, content)
SAMPLE_DOCS = [
    (
        "annual_revenue.txt",
        "finance",
        "CONFIDENTIAL",
        "FIN-001 — Annual Revenue Report\n\n"
        "This year the company reported total annual revenue of $48.2 million, a 12% "
        "increase over the previous fiscal year. Gross margin improved to 61%. Operating "
        "expenses grew 8% year over year, driven primarily by investment in the sales "
        "organization and product engineering.\n\n"
        "Revenue by segment: enterprise software contributed $31.4 million, professional "
        "services contributed $9.8 million, and maintenance and support contributed $7.0 "
        "million. The strongest growth came from the enterprise software segment, which "
        "grew 19%.\n\n"
        "Net income for the year was $7.6 million. The board has approved a dividend "
        "increase of 5% effective next quarter.",
    ),
    (
        "network_architecture.txt",
        "it",
        "INTERNAL",
        "IT-001 — Network Architecture Overview\n\n"
        "The corporate network is segmented into three zones: the DMZ, the internal "
        "corporate LAN, and the server farm. The DMZ hosts the public web application "
        "firewall and the VPN concentrator. The internal LAN is further divided into "
        "VLANs per department.\n\n"
        "All inter-zone traffic passes through the next-generation firewall which "
        "enforces least-privilege rules. East-west traffic within the server farm is "
        "micro-segmented using policy-based virtual firewalls.\n\n"
        "Access to the server farm is restricted to IT operations staff via a jump host "
        "with hardware-backed MFA.",
    ),
    (
        "company_overview.txt",
        "general",
        "PUBLIC",
        "Company Overview\n\n"
        "RAGGuard Labs is a technology company that builds security software for "
        "enterprise AI applications. Founded in 2021, the company employs 240 people "
        "across offices in Casablanca and Lisbon.\n\n"
        "The company's flagship product helps organizations apply fine-grained access "
        "control to their retrieval-augmented generation systems, ensuring that "
        "sensitive documents never reach an AI assistant's context without authorization.",
    ),
    (
        "employee_salary.txt",
        "hr",
        "CONFIDENTIAL",
        "HR-001 — Employee Compensation Summary\n\n"
        "The following is a summary of executive and staff compensation. Executive "
        "salaries range from $180,000 to $420,000 per year plus equity. Staff salaries "
        "range from $55,000 to $140,000 depending on seniority and location.\n\n"
        "The median total compensation for engineering staff is $132,000. This summary "
        "is confidential and must not be shared outside the human resources department "
        "or with employees who do not have a legitimate need to know.",
    ),
    (
        "security_incident.txt",
        "security",
        "RESTRICTED",
        "SEC-001 — Security Incident Report (RESTRICTED)\n\n"
        "On the night of July 14, a phishing email bypassed the email gateway and "
        "reached 12 employees in the finance department. Two employees entered their "
        "credentials on the fraudulent page before the campaign was blocked.\n\n"
        "The affected accounts were locked within 40 minutes of detection. Forensic "
        "analysis found no evidence of lateral movement or data exfiltration. The "
        "incident is classified RESTRICTED; dissemination is limited to the security "
        "team and approved executives.",
    ),
    (
        "acquisition_strategy.txt",
        "executive",
        "TOP_SECRET",
        "EXEC-001 — Acquisition Strategy (TOP SECRET)\n\n"
        "The board is evaluating the acquisition of a competitor's enterprise software "
        "division for an indicative valuation of $210 million. A definitive agreement "
        "has not been signed and the deal is subject to due diligence and regulatory "
        "approval.\n\n"
        "This document is TOP SECRET. Knowledge of the proposed acquisition is limited "
        "to the CEO, the CFO, and outside counsel. Premature disclosure could have a "
        "material effect on the company's share price.",
    ),
]


def seed(db) -> None:
    for name in DEPARTMENTS:
        if not db.query(Department).filter(Department.name == name).first():
            db.add(Department(name=name))
    db.commit()

    for name in ROLES:
        if not db.query(Role).filter(Role.name == name).first():
            db.add(Role(name=name))
    db.commit()

    roles = {r.name: r for r in db.query(Role).all()}
    departments = {d.name: d for d in db.query(Department).all()}

    for username, (role_name, dept_name, is_admin) in USERS.items():
        if db.query(User).filter(User.username == username).first():
            continue
        db.add(
            User(
                username=username,
                hashed_password=hash_password(DEMO_PASSWORD),
                role_id=roles[role_name].id,
                department_id=departments[dept_name].id,
                is_admin=is_admin,
                is_active=True,
            )
        )
    db.commit()


def write_sample_docs() -> Path:
    sample_dir = settings.uploads_dir.parent / "sample_docs"
    sample_dir.mkdir(parents=True, exist_ok=True)
    for filename, dept, classification, content in SAMPLE_DOCS:
        (sample_dir / filename).write_text(content, encoding="utf-8")
        # Sidecar metadata so ingest_documents.py knows this file's access envelope.
        sidecar = sample_dir / f"{filename}.meta.yaml"
        sidecar.write_text(
            f"department: {dept}\nclassification: {classification}\n",
            encoding="utf-8",
        )
    return sample_dir


def main() -> None:
    if "--reset" in sys.argv:
        db = SessionLocal()
        db.query(User).delete()
        db.commit()
        db.close()
        print("Reset: existing demo users deleted.")

    init_db()
    db = SessionLocal()
    try:
        seed(db)
    finally:
        db.close()

    sample_dir = write_sample_docs()
    print(f"Seeded {len(DEPARTMENTS)} departments, {len(ROLES)} roles, {len(USERS)} users.")
    print(f"Demo password for every user: {DEMO_PASSWORD}")
    print(f"Sample documents written to {sample_dir} — ingest with: python scripts/ingest_documents.py")


if __name__ == "__main__":
    main()
