"""
Case Management System for Workflow Orchestration

This module provides comprehensive case management features including:
- Incident response workflows
- Case tracking and management
- Escalation procedures
- SLA monitoring
- Case lifecycle management
- Incident classification and routing

Inspired by: Tracecat, StackStorm, Apache Airflow
"""

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class CaseStatus(Enum):
    """Case status enumeration"""

    OPEN = "open"
    IN_PROGRESS = "in_progress"
    ESCALATED = "escalated"
    RESOLVED = "resolved"
    CLOSED = "closed"
    CANCELLED = "cancelled"


class CasePriority(Enum):
    """Case priority levels"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


class CaseType(Enum):
    """Case type classification"""

    INCIDENT = "incident"
    REQUEST = "request"
    PROBLEM = "problem"
    CHANGE = "change"
    SECURITY = "security"
    COMPLIANCE = "compliance"
    OPERATIONAL = "operational"


class EscalationLevel(Enum):
    """Escalation levels"""

    LEVEL_1 = "level_1"
    LEVEL_2 = "level_2"
    LEVEL_3 = "level_3"
    MANAGEMENT = "management"
    EXECUTIVE = "executive"


@dataclass
class SLA:
    """Service Level Agreement definition"""

    name: str
    description: str
    response_time: timedelta
    resolution_time: timedelta
    business_hours: dict[str, list[str]] = field(default_factory=dict)
    priority_multipliers: dict[CasePriority, float] = field(
        default_factory=dict
    )
    escalation_rules: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class Case:
    """Case definition"""

    id: str
    title: str
    description: str
    case_type: CaseType
    priority: CasePriority
    status: CaseStatus
    assigned_to: Optional[str] = None
    created_by: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    sla: Optional[SLA] = None
    tags: set[str] = field(default_factory=set)
    metadata: dict[str, Any] = field(default_factory=dict)
    workflow_id: Optional[str] = None
    escalation_level: EscalationLevel = EscalationLevel.LEVEL_1
    parent_case_id: Optional[str] = None
    child_case_ids: set[str] = field(default_factory=set)


@dataclass
class CaseComment:
    """Case comment/note"""

    id: str
    case_id: str
    author: str
    content: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    is_internal: bool = False
    attachments: list[str] = field(default_factory=list)


@dataclass
class CaseActivity:
    """Case activity log"""

    id: str
    case_id: str
    action: str
    actor: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    details: dict[str, Any] = field(default_factory=dict)
    old_value: Any = None
    new_value: Any = None


@dataclass
class EscalationRule:
    """Escalation rule definition"""

    id: str
    name: str
    description: str
    conditions: dict[str, Any]
    actions: list[dict[str, Any]]
    priority: int = 0
    is_active: bool = True


class CaseManager:
    """Main case management system"""

    def __init__(self, storage_file: str = "cases.json"):
        self.storage_file = Path(storage_file)
        self.cases: dict[str, Case] = {}
        self.comments: dict[str, list[CaseComment]] = {}
        self.activities: dict[str, list[CaseActivity]] = {}
        self.slas: dict[str, SLA] = {}
        self.escalation_rules: list[EscalationRule] = []
        self.workflow_manager = None

        self._load_data()
        self._create_default_slas()
        self._create_default_escalation_rules()

    def _load_data(self):
        """Load cases from storage"""
        if self.storage_file.exists():
            try:
                with open(self.storage_file) as f:
                    data = json.load(f)

                    # Load cases
                    for case_data in data.get("cases", []):
                        case = Case(
                            id=case_data["id"],
                            title=case_data["title"],
                            description=case_data["description"],
                            case_type=CaseType(case_data["case_type"]),
                            priority=CasePriority(case_data["priority"]),
                            status=CaseStatus(case_data["status"]),
                            assigned_to=case_data.get("assigned_to"),
                            created_by=case_data.get("created_by", ""),
                            created_at=datetime.fromisoformat(
                                case_data["created_at"]
                            ),
                            updated_at=datetime.fromisoformat(
                                case_data["updated_at"]
                            ),
                            resolved_at=(
                                datetime.fromisoformat(case_data["resolved_at"])
                                if case_data.get("resolved_at")
                                else None
                            ),
                            closed_at=(
                                datetime.fromisoformat(case_data["closed_at"])
                                if case_data.get("closed_at")
                                else None
                            ),
                            tags=set(case_data.get("tags", [])),
                            metadata=case_data.get("metadata", {}),
                            workflow_id=case_data.get("workflow_id"),
                            escalation_level=EscalationLevel(
                                case_data.get("escalation_level", "level_1")
                            ),
                            parent_case_id=case_data.get("parent_case_id"),
                            child_case_ids=set(
                                case_data.get("child_case_ids", [])
                            ),
                        )
                        self.cases[case.id] = case

                    # Load comments
                    for comment_data in data.get("comments", []):
                        comment = CaseComment(
                            id=comment_data["id"],
                            case_id=comment_data["case_id"],
                            author=comment_data["author"],
                            content=comment_data["content"],
                            created_at=datetime.fromisoformat(
                                comment_data["created_at"]
                            ),
                            is_internal=comment_data.get("is_internal", False),
                            attachments=comment_data.get("attachments", []),
                        )
                        if comment.case_id not in self.comments:
                            self.comments[comment.case_id] = []
                        self.comments[comment.case_id].append(comment)

                    # Load activities
                    for activity_data in data.get("activities", []):
                        activity = CaseActivity(
                            id=activity_data["id"],
                            case_id=activity_data["case_id"],
                            action=activity_data["action"],
                            actor=activity_data["actor"],
                            timestamp=datetime.fromisoformat(
                                activity_data["timestamp"]
                            ),
                            details=activity_data.get("details", {}),
                            old_value=activity_data.get("old_value"),
                            new_value=activity_data.get("new_value"),
                        )
                        if activity.case_id not in self.activities:
                            self.activities[activity.case_id] = []
                        self.activities[activity.case_id].append(activity)

            except Exception as e:
                logger.error(f"Failed to load case data: {e}")

    def _save_data(self):
        """Save cases to storage"""
        try:
            data = {
                "cases": [
                    {
                        "id": case.id,
                        "title": case.title,
                        "description": case.description,
                        "case_type": case.case_type.value,
                        "priority": case.priority.value,
                        "status": case.status.value,
                        "assigned_to": case.assigned_to,
                        "created_by": case.created_by,
                        "created_at": case.created_at.isoformat(),
                        "updated_at": case.updated_at.isoformat(),
                        "resolved_at": (
                            case.resolved_at.isoformat()
                            if case.resolved_at
                            else None
                        ),
                        "closed_at": (
                            case.closed_at.isoformat()
                            if case.closed_at
                            else None
                        ),
                        "tags": list(case.tags),
                        "metadata": case.metadata,
                        "workflow_id": case.workflow_id,
                        "escalation_level": case.escalation_level.value,
                        "parent_case_id": case.parent_case_id,
                        "child_case_ids": list(case.child_case_ids),
                    }
                    for case in self.cases.values()
                ],
                "comments": [
                    {
                        "id": comment.id,
                        "case_id": comment.case_id,
                        "author": comment.author,
                        "content": comment.content,
                        "created_at": comment.created_at.isoformat(),
                        "is_internal": comment.is_internal,
                        "attachments": comment.attachments,
                    }
                    for comments in self.comments.values()
                    for comment in comments
                ],
                "activities": [
                    {
                        "id": activity.id,
                        "case_id": activity.case_id,
                        "action": activity.action,
                        "actor": activity.actor,
                        "timestamp": activity.timestamp.isoformat(),
                        "details": activity.details,
                        "old_value": activity.old_value,
                        "new_value": activity.new_value,
                    }
                    for activities in self.activities.values()
                    for activity in activities
                ],
            }

            with open(self.storage_file, "w") as f:
                json.dump(data, f, indent=2)

        except Exception as e:
            logger.error(f"Failed to save case data: {e}")

    def _create_default_slas(self):
        """Create default SLAs"""
        self.slas = {
            "standard": SLA(
                name="Standard SLA",
                description="Standard service level agreement",
                response_time=timedelta(hours=4),
                resolution_time=timedelta(hours=24),
                priority_multipliers={
                    CasePriority.LOW: 1.0,
                    CasePriority.MEDIUM: 0.75,
                    CasePriority.HIGH: 0.5,
                    CasePriority.CRITICAL: 0.25,
                    CasePriority.EMERGENCY: 0.1,
                },
            ),
            "critical": SLA(
                name="Critical SLA",
                description="Critical incident SLA",
                response_time=timedelta(minutes=30),
                resolution_time=timedelta(hours=4),
                priority_multipliers={
                    CasePriority.LOW: 0.5,
                    CasePriority.MEDIUM: 0.25,
                    CasePriority.HIGH: 0.1,
                    CasePriority.CRITICAL: 0.05,
                    CasePriority.EMERGENCY: 0.02,
                },
            ),
        }

    def _create_default_escalation_rules(self):
        """Create default escalation rules"""
        self.escalation_rules = [
            EscalationRule(
                id="time_based_escalation",
                name="Time-based Escalation",
                description="Escalate cases that exceed response time",
                conditions={
                    "type": "time_exceeded",
                    "field": "response_time",
                    "threshold": 0.8,  # 80% of SLA time
                },
                actions=[
                    {
                        "type": "escalate_level",
                        "target_level": EscalationLevel.LEVEL_2,
                    },
                    {"type": "notify", "recipients": ["manager"]},
                ],
                priority=1,
            ),
            EscalationRule(
                id="priority_escalation",
                name="Priority-based Escalation",
                description="Escalate high priority cases",
                conditions={
                    "type": "priority_check",
                    "priority": [CasePriority.CRITICAL, CasePriority.EMERGENCY],
                },
                actions=[
                    {
                        "type": "escalate_level",
                        "target_level": EscalationLevel.MANAGEMENT,
                    },
                    {"type": "notify", "recipients": ["management", "oncall"]},
                ],
                priority=2,
            ),
        ]

    def create_case(
        self,
        title: str,
        description: str,
        case_type: CaseType,
        priority: CasePriority,
        created_by: str,
        tags: list[str] = None,
        sla_name: str = "standard",
        metadata: dict[str, Any] = None,
    ) -> Case:
        """Create a new case"""
        case_id = f"case_{uuid.uuid4().hex[:8]}"

        case = Case(
            id=case_id,
            title=title,
            description=description,
            case_type=case_type,
            priority=priority,
            status=CaseStatus.OPEN,
            created_by=created_by,
            tags=set(tags or []),
            sla=self.slas.get(sla_name),
            metadata=metadata or {},
        )

        self.cases[case_id] = case
        self.comments[case_id] = []
        self.activities[case_id] = []

        # Log activity
        self._log_activity(
            case_id,
            "case_created",
            created_by,
            {
                "title": title,
                "case_type": case_type.value,
                "priority": priority.value,
            },
        )

        self._save_data()
        return case

    def get_case(self, case_id: str) -> Optional[Case]:
        """Get case by ID"""
        return self.cases.get(case_id)

    def update_case(
        self, case_id: str, updates: dict[str, Any], actor: str
    ) -> bool:
        """Update case"""
        case = self.cases.get(case_id)
        if not case:
            return False

        # Track changes
        changes = {}

        for field, value in updates.items():
            if hasattr(case, field):
                old_value = getattr(case, field)
                setattr(case, field, value)
                changes[field] = {"old": old_value, "new": value}

        case.updated_at = datetime.utcnow()

        # Log activity
        self._log_activity(case_id, "case_updated", actor, {"changes": changes})

        # Check for status changes
        if "status" in changes:
            self._handle_status_change(
                case, changes["status"]["old"], changes["status"]["new"], actor
            )

        self._save_data()
        return True

    def assign_case(self, case_id: str, assignee: str, actor: str) -> bool:
        """Assign case to user"""
        case = self.cases.get(case_id)
        if not case:
            return False

        old_assignee = case.assigned_to
        case.assigned_to = assignee
        case.updated_at = datetime.utcnow()

        # Log activity
        self._log_activity(
            case_id,
            "case_assigned",
            actor,
            {"old_assignee": old_assignee, "new_assignee": assignee},
        )

        self._save_data()
        return True

    def add_comment(
        self, case_id: str, author: str, content: str, is_internal: bool = False
    ) -> Optional[CaseComment]:
        """Add comment to case"""
        if case_id not in self.cases:
            return None

        comment_id = f"comment_{uuid.uuid4().hex[:8]}"
        comment = CaseComment(
            id=comment_id,
            case_id=case_id,
            author=author,
            content=content,
            is_internal=is_internal,
        )

        if case_id not in self.comments:
            self.comments[case_id] = []
        self.comments[case_id].append(comment)

        # Log activity
        self._log_activity(
            case_id,
            "comment_added",
            author,
            {"comment_id": comment_id, "is_internal": is_internal},
        )

        self._save_data()
        return comment

    def get_comments(self, case_id: str) -> list[CaseComment]:
        """Get comments for case"""
        return self.comments.get(case_id, [])

    def get_activities(self, case_id: str) -> list[CaseActivity]:
        """Get activities for case"""
        return self.activities.get(case_id, [])

    def search_cases(self, filters: dict[str, Any] = None) -> list[Case]:
        """Search cases with filters"""
        cases = list(self.cases.values())

        if not filters:
            return cases

        filtered_cases = []

        for case in cases:
            match = True

            for field, value in filters.items():
                if hasattr(case, field):
                    case_value = getattr(case, field)
                    if isinstance(value, list):
                        if case_value not in value:
                            match = False
                            break
                    else:
                        if case_value != value:
                            match = False
                            break
                elif field == "tags" and value:
                    if not case.tags.intersection(set(value)):
                        match = False
                        break

            if match:
                filtered_cases.append(case)

        return filtered_cases

    def escalate_case(
        self,
        case_id: str,
        target_level: EscalationLevel,
        actor: str,
        reason: str = "",
    ) -> bool:
        """Escalate case to higher level"""
        case = self.cases.get(case_id)
        if not case:
            return False

        old_level = case.escalation_level
        case.escalation_level = target_level
        case.updated_at = datetime.utcnow()

        # Log activity
        self._log_activity(
            case_id,
            "case_escalated",
            actor,
            {
                "old_level": old_level.value,
                "new_level": target_level.value,
                "reason": reason,
            },
        )

        # Add comment
        self.add_comment(
            case_id,
            actor,
            f"Case escalated to {target_level.value}: {reason}",
            is_internal=True,
        )

        self._save_data()
        return True

    def resolve_case(
        self, case_id: str, actor: str, resolution_notes: str = ""
    ) -> bool:
        """Resolve case"""
        case = self.cases.get(case_id)
        if not case:
            return False

        case.status = CaseStatus.RESOLVED
        case.resolved_at = datetime.utcnow()
        case.updated_at = datetime.utcnow()

        # Log activity
        self._log_activity(
            case_id,
            "case_resolved",
            actor,
            {"resolution_notes": resolution_notes},
        )

        # Add comment
        if resolution_notes:
            self.add_comment(
                case_id, actor, f"Case resolved: {resolution_notes}"
            )

        self._save_data()
        return True

    def close_case(
        self, case_id: str, actor: str, closure_notes: str = ""
    ) -> bool:
        """Close case"""
        case = self.cases.get(case_id)
        if not case:
            return False

        case.status = CaseStatus.CLOSED
        case.closed_at = datetime.utcnow()
        case.updated_at = datetime.utcnow()

        # Log activity
        self._log_activity(
            case_id, "case_closed", actor, {"closure_notes": closure_notes}
        )

        # Add comment
        if closure_notes:
            self.add_comment(case_id, actor, f"Case closed: {closure_notes}")

        self._save_data()
        return True

    def _log_activity(
        self,
        case_id: str,
        action: str,
        actor: str,
        details: dict[str, Any] = None,
    ):
        """Log case activity"""
        activity_id = f"activity_{uuid.uuid4().hex[:8]}"
        activity = CaseActivity(
            id=activity_id,
            case_id=case_id,
            action=action,
            actor=actor,
            details=details or {},
        )

        if case_id not in self.activities:
            self.activities[case_id] = []
        self.activities[case_id].append(activity)

    def _handle_status_change(
        self,
        case: Case,
        old_status: CaseStatus,
        new_status: CaseStatus,
        actor: str,
    ):
        """Handle case status changes"""
        if (
            new_status == CaseStatus.IN_PROGRESS
            and old_status == CaseStatus.OPEN
        ):
            # Case started - check SLA
            self._check_sla_compliance(case)

        elif new_status in [CaseStatus.RESOLVED, CaseStatus.CLOSED]:
            # Case completed - update metrics
            self._update_case_metrics(case)

    def _check_sla_compliance(self, case: Case):
        """Check SLA compliance for case"""
        if not case.sla:
            return

        # Calculate response time
        response_time = datetime.utcnow() - case.created_at
        sla_response_time = (
            case.sla.response_time
            * case.sla.priority_multipliers.get(case.priority, 1.0)
        )

        if response_time > sla_response_time:
            # SLA breached - trigger escalation
            self._trigger_escalation(case, "sla_breach")

    def _trigger_escalation(self, case: Case, reason: str):
        """Trigger escalation for case"""
        for rule in sorted(self.escalation_rules, key=lambda r: r.priority):
            if not rule.is_active:
                continue

            if self._evaluate_escalation_condition(case, rule.conditions):
                for action in rule.actions:
                    self._execute_escalation_action(case, action)

    def _evaluate_escalation_condition(
        self, case: Case, condition: dict[str, Any]
    ) -> bool:
        """Evaluate escalation condition"""
        condition_type = condition.get("type")

        if condition_type == "time_exceeded":
            field = condition.get("field")
            threshold = condition.get("threshold", 0.8)

            if field == "response_time" and case.sla:
                response_time = datetime.utcnow() - case.created_at
                sla_time = (
                    case.sla.response_time
                    * case.sla.priority_multipliers.get(case.priority, 1.0)
                )
                return response_time > (sla_time * threshold)

        elif condition_type == "priority_check":
            required_priorities = condition.get("priority", [])
            return case.priority in required_priorities

        return False

    def _execute_escalation_action(self, case: Case, action: dict[str, Any]):
        """Execute escalation action"""
        action_type = action.get("type")

        if action_type == "escalate_level":
            target_level = EscalationLevel(action.get("target_level"))
            self.escalate_case(
                case.id, target_level, "system", "Automatic escalation"
            )

        elif action_type == "notify":
            recipients = action.get("recipients", [])
            # TODO: Implement notification system
            logger.info(f"Notification sent to {recipients} for case {case.id}")

    def _update_case_metrics(self, case: Case):
        """Update case metrics"""
        # TODO: Implement metrics tracking
        pass

    def get_sla_status(self, case_id: str) -> dict[str, Any]:
        """Get SLA status for case"""
        case = self.cases.get(case_id)
        if not case or not case.sla:
            return {}

        now = datetime.utcnow()
        response_time = now - case.created_at
        sla_response_time = (
            case.sla.response_time
            * case.sla.priority_multipliers.get(case.priority, 1.0)
        )

        if case.resolved_at:
            resolution_time = case.resolved_at - case.created_at
            sla_resolution_time = (
                case.sla.resolution_time
                * case.sla.priority_multipliers.get(case.priority, 1.0)
            )
        else:
            resolution_time = now - case.created_at
            sla_resolution_time = (
                case.sla.resolution_time
                * case.sla.priority_multipliers.get(case.priority, 1.0)
            )

        return {
            "response_time": response_time.total_seconds(),
            "sla_response_time": sla_response_time.total_seconds(),
            "response_breached": response_time > sla_response_time,
            "resolution_time": resolution_time.total_seconds(),
            "sla_resolution_time": sla_resolution_time.total_seconds(),
            "resolution_breached": resolution_time > sla_resolution_time,
        }


# Global case manager instance
case_manager = CaseManager()


# Convenience functions
def create_case(
    title: str,
    description: str,
    case_type: CaseType,
    priority: CasePriority,
    created_by: str,
    **kwargs,
) -> Case:
    """Create a new case"""
    return case_manager.create_case(
        title, description, case_type, priority, created_by, **kwargs
    )


def get_case(case_id: str) -> Optional[Case]:
    """Get case by ID"""
    return case_manager.get_case(case_id)


def update_case(case_id: str, updates: dict[str, Any], actor: str) -> bool:
    """Update case"""
    return case_manager.update_case(case_id, updates, actor)


def assign_case(case_id: str, assignee: str, actor: str) -> bool:
    """Assign case to user"""
    return case_manager.assign_case(case_id, assignee, actor)


def add_comment(
    case_id: str, author: str, content: str, is_internal: bool = False
) -> Optional[CaseComment]:
    """Add comment to case"""
    return case_manager.add_comment(case_id, author, content, is_internal)


def search_cases(filters: dict[str, Any] = None) -> list[Case]:
    """Search cases with filters"""
    return case_manager.search_cases(filters)


def escalate_case(
    case_id: str, target_level: EscalationLevel, actor: str, reason: str = ""
) -> bool:
    """Escalate case to higher level"""
    return case_manager.escalate_case(case_id, target_level, actor, reason)


def resolve_case(case_id: str, actor: str, resolution_notes: str = "") -> bool:
    """Resolve case"""
    return case_manager.resolve_case(case_id, actor, resolution_notes)


def close_case(case_id: str, actor: str, closure_notes: str = "") -> bool:
    """Close case"""
    return case_manager.close_case(case_id, actor, closure_notes)


def get_sla_status(case_id: str) -> dict[str, Any]:
    """Get SLA status for case"""
    return case_manager.get_sla_status(case_id)


# Example usage
if __name__ == "__main__":
    # Create example case
    case = create_case(
        title="Database Connection Issue",
        description="Users unable to connect to production database",
        case_type=CaseType.INCIDENT,
        priority=CasePriority.HIGH,
        created_by="user@example.com",
        tags=["database", "production", "connectivity"],
    )

    print(f"Created case: {case.id}")
    print(f"Status: {case.status.value}")
    print(f"Priority: {case.priority.value}")

    # Add comment
    comment = add_comment(
        case.id, "admin@example.com", "Investigating the issue..."
    )
    print(f"Added comment: {comment.id}")

    # Update status
    update_case(
        case.id, {"status": CaseStatus.IN_PROGRESS}, "admin@example.com"
    )
    print(f"Updated status to: {get_case(case.id).status.value}")

    # Check SLA status
    sla_status = get_sla_status(case.id)
    print(f"SLA Status: {sla_status}")
