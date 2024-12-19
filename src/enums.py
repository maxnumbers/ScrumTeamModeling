from enum import Enum, auto

class Role(Enum):
    DEVELOPER = auto()
    PO_PRIMARY = auto()
    PO_SECONDARY = auto() 
    PO_TERTIARY = auto()
    ADMIN_PRIMARY = auto()
    ADMIN_SECONDARY = auto()
    ADMIN_TERTIARY = auto()
    REVIEWER = auto()

    @staticmethod
    def is_po_role(role):
        return role in [Role.PO_PRIMARY, Role.PO_SECONDARY, Role.PO_TERTIARY]
        
    @staticmethod
    def is_admin_role(role):
        return role in [Role.ADMIN_PRIMARY, Role.ADMIN_SECONDARY, Role.ADMIN_TERTIARY]

class Phase(Enum):
    TODO = 'TO DO'
    IN_PROGRESS = 'IN PROGRESS'
    BLOCKED = 'BLOCKED'
    PEER_REVIEW = 'IN PEER REVIEW'
    PO_REVIEW = 'IN PO CONCURRENCE'
    VALIDATION = 'IN VALIDATION'
    DONE = 'DONE'

class Meeting(Enum):
    STANDUP = auto()
    SPRINT_PLANNING = auto()
    REFINEMENT = auto()
    RETRO = auto()
    REVIEW = auto()
    DOCUMENTATION = auto()
    TEAM_MEETING = auto()
    SUPPORT = auto()
