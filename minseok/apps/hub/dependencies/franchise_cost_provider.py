from __future__ import annotations

from fastapi import Depends

from hub.app.ports.input.franchise_cost_ingest_use_case import FranchiseCostIngestUseCase
from hub.app.ports.output.franchise_cost_storage_port import FranchiseCostStoragePort
from hub.app.use_cases.franchise_cost_ingest_interactor import FranchiseCostIngestInteractor


def get_franchise_cost_storage_port() -> FranchiseCostStoragePort:
    raise NotImplementedError("get_franchise_cost_storage_port는 main.py의 dependency_overrides로 market 구현을 주입해야 합니다.")


def get_franchise_cost_ingest_use_case(
    storage: FranchiseCostStoragePort = Depends(get_franchise_cost_storage_port),
) -> FranchiseCostIngestUseCase:
    return FranchiseCostIngestInteractor(storage=storage)
