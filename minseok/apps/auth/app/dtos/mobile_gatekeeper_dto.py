from dataclasses import dataclass


@dataclass(frozen=True)
class MobileGatekeeperQuery:

    id: int
    name: str


@dataclass(frozen=True)
class MobileGatekeeperResponse:

    id: int
    name: str
    introduction: str
