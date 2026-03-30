from dataclasses import dataclass


@dataclass
class User:
    id: int
    username: str
    role: str
    is_active: bool = True

    def is_admin(self) -> bool:
        return self.role == "admin"

    def is_viewer(self) -> bool:
        return self.role == "viewer"
