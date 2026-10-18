from __future__ import annotations

import hashlib
import secrets
import time
from typing import Any
from uuid import uuid4

from app.settings import settings


class CompanyStore:
    """Company tenancy, invitations, and company-owned team membership."""
    def __init__(self) -> None:
        from google.cloud import firestore
        project = settings.firestore_project_id or settings.firebase_project_id
        self.db = firestore.Client(project=project) if project else firestore.Client()
        self.companies = self.db.collection("nexushelper_companies")
        self.members = self.db.collection("nexushelper_memberships")
        self.invites = self.db.collection("nexushelper_invitations")

    @staticmethod
    def _member_id(user_id: str, company_id: str) -> str:
        return f"{user_id}_{company_id}"

    def create_company(self, user_id: str, name: str) -> dict[str, Any]:
        company_id = uuid4().hex
        graph_name = f"company_{company_id}"
        company = {"id": company_id, "name": name.strip()[:100], "graph_name": graph_name,
                   "created_at": time.time(), "owner_id": user_id}
        self.companies.document(company_id).set(company)
        self.members.document(self._member_id(user_id, company_id)).set({
            "user_id": user_id, "company_id": company_id, "team_ids": [],
            "role": "owner", "expires_at": None, "created_at": time.time(),
        })
        return company

    def memberships(self, user_id: str) -> list[dict[str, Any]]:
        result = []
        for snapshot in self.members.where("user_id", "==", user_id).stream():
            member = snapshot.to_dict() or {}
            company_id = member.get("company_id")
            if not company_id:
                continue
            company = self.companies.document(company_id).get()
            if not company.exists:
                continue
            item = company.to_dict() or {}
            expires_at = member.get("expires_at")
            teams = list(member.get("team_ids", []))
            role = member.get("role", "member")
            if expires_at and float(expires_at) <= time.time():
                teams = []
                role = "member"
            result.append({**item, "team_ids": teams, "role": role,
                           "expires_at": expires_at})
        return result

    def membership(self, user_id: str, company_id: str) -> dict[str, Any] | None:
        snapshot = self.members.document(self._member_id(user_id, company_id)).get()
        if not snapshot.exists:
            return None
        value = snapshot.to_dict() or {}
        if value.get("expires_at") and float(value["expires_at"]) <= time.time():
            value["team_ids"] = []
            value["role"] = "member"
        return value

    def company(self, company_id: str) -> dict[str, Any] | None:
        snapshot = self.companies.document(company_id).get()
        return snapshot.to_dict() if snapshot.exists else None

    def create_invitation(self, owner_id: str, company_id: str, email: str,
                          team_ids: list[str], expires_in_days: int | None) -> dict[str, Any]:
        self._require_owner(owner_id, company_id)
        code = secrets.token_urlsafe(24)
        invite_id = uuid4().hex
        doc = {"id": invite_id, "company_id": company_id, "email": email.strip().lower(),
               "team_ids": sorted({team.strip().lower() for team in team_ids if team.strip()}),
               "created_by": owner_id, "expires_at": time.time() + 7 * 86400,
               "access_expires_at": time.time() + expires_in_days * 86400 if expires_in_days else None,
               "token_hash": hashlib.sha256(code.encode()).hexdigest()}
        self.invites.document(invite_id).set(doc)
        company = self.company(company_id) or {}
        return {"code": code, "company_id": company_id, "company_name": company.get("name"),
                "email": doc["email"], "team_ids": doc["team_ids"],
                "expires_at": doc["access_expires_at"], "invite_expires_at": doc["expires_at"]}

    def accept_invitation(self, user_id: str, email: str, code: str) -> dict[str, Any]:
        token_hash = hashlib.sha256(code.strip().encode()).hexdigest()
        matches = list(self.invites.where("token_hash", "==", token_hash).limit(1).stream())
        if not matches:
            raise ValueError("Invitation code is invalid or has already been used")
        snapshot = matches[0]
        invite = snapshot.to_dict() or {}
        if float(invite.get("expires_at", 0)) <= time.time():
            snapshot.reference.delete()
            raise ValueError("Invitation has expired")
        if invite.get("email") and invite["email"].lower() != email.lower():
            raise ValueError("Sign in with the email address this invitation was sent to")
        company_id = invite["company_id"]
        self.members.document(self._member_id(user_id, company_id)).set({
            "user_id": user_id, "company_id": company_id, "team_ids": invite.get("team_ids", []),
            "role": "member", "expires_at": invite.get("access_expires_at"), "created_at": time.time(),
        })
        snapshot.reference.delete()
        return self.company(company_id) or {"id": company_id}

    def list_members(self, owner_id: str, company_id: str) -> list[dict[str, Any]]:
        self._require_owner(owner_id, company_id)
        return [doc.to_dict() or {} for doc in self.members.where("company_id", "==", company_id).stream()]

    def update_member(self, owner_id: str, company_id: str, user_id: str, team_ids: list[str],
                      role: str, expires_in_days: int | None) -> dict[str, Any]:
        self._require_owner(owner_id, company_id)
        if role not in {"owner", "member"}:
            raise ValueError("Role must be owner or member")
        ref = self.members.document(self._member_id(user_id, company_id))
        current = ref.get()
        if not current.exists:
            raise ValueError("This account has not joined the company")
        value = current.to_dict() or {}
        value.update({"team_ids": sorted({t.strip().lower() for t in team_ids if t.strip()}),
                      "role": role,
                      "expires_at": time.time() + expires_in_days * 86400 if expires_in_days else None})
        ref.set(value)
        return value

    def _require_owner(self, user_id: str, company_id: str) -> None:
        member = self.membership(user_id, company_id)
        if not member or member.get("role") != "owner":
            raise PermissionError("Only a company owner can manage this company")


company_store: CompanyStore | None = None


def get_company_store() -> CompanyStore:
    global company_store
    if company_store is None:
        company_store = CompanyStore()
    return company_store


def graph_for_company(request: Any, principal: Any) -> Any:
    if principal.auth_type == "demo":
        return getattr(request.app.state, "graph", None)
    from app.services.graph import GraphRepository
    graphs = request.app.state.company_graphs
    graph = graphs.get(principal.company_id)
    if graph is None:
        graph = GraphRepository(settings.falkordb_host, settings.falkordb_port,
                                principal.graph_name, settings.falkordb_username,
                                settings.falkordb_password, settings.falkordb_use_tls)
        graph._run("RETURN 1 AS ping", {})
        graphs[principal.company_id] = graph
    return graph
