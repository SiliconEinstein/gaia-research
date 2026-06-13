"""Standalone Gaia research package."""

from gaia_research.artifacts import (
    ResearchPackage,
    ResearchTargetError,
    append_research_event,
    ensure_research_manifest,
    load_research_package,
    scaffold_suggestion,
    write_research_artifact,
)
from gaia_research.assessment import (
    AssessmentSchemaError,
    build_assessment_artifact,
    build_assessment_from_analysis,
    build_assessment_from_landscapes,
    validate_assessment_artifact,
    validate_assessment_grounding,
    validate_assessment_relation,
)
from gaia_research.contracts import (
    CORE_PUBLIC_SURFACES,
    ResearchContractError,
    assess_contract,
    field_map_contract,
    focus_contract,
    propose_contract,
    research_contract,
    verify_core_contract,
)
from gaia_research.evidence_selection import (
    SELECTED_EVIDENCE_SCHEMA_VERSION,
    build_selected_evidence_artifact,
)
from gaia_research.field_map import (
    FIELD_MAP_SCHEMA_VERSION,
    FieldMapSchemaError,
    build_field_map_artifact,
    validate_field_map_artifact,
)
from gaia_research.focus import (
    FocusSynthesisSchemaError,
    build_focus_synthesis_artifact,
    validate_focus_synthesis_artifact,
)
from gaia_research.landscape import ScanBatch, build_research_landscape
from gaia_research.orchestrator_ports import (
    ResearchOrchestratorError,
    ResearchOrchestratorPaused,
    ResearchOrchestratorRuntime,
)
from gaia_research.proposal import (
    ProposalSchemaError,
    build_proposal_from_assessment,
    validate_proposal_artifact,
    validate_proposal_record,
)
from gaia_research.report import (
    ResearchReportError,
    render_final_research_report_markdown,
    render_markdown_with_research_citations,
    render_research_artifact_markdown,
)
from gaia_research.run_config import (
    ResearchRunConfig,
    load_research_run_config_file,
    resolve_research_run_config,
)
from gaia_research.source_packages import (
    ResearchSourcePackage,
    attach_source_package_refs,
    materialize_landscape_source_package,
)
from gaia_research.stop import STOP_SCHEMA_VERSION, evaluate_research_stop
from gaia_research.sync import (
    ResearchSyncResult,
    ResearchSyncSourceError,
    sync_assessment_artifact,
    sync_focus_artifact,
    sync_landscape_artifact,
    sync_materialization,
    sync_proposal_artifact,
)
from gaia_research.workflow_state import (
    ReportRunHandle,
    ReportRunState,
    create_report_run,
    read_events,
    read_state,
    record_event,
    resume_report_run,
    write_state,
)

__all__ = [
    "CORE_PUBLIC_SURFACES",
    "FIELD_MAP_SCHEMA_VERSION",
    "SELECTED_EVIDENCE_SCHEMA_VERSION",
    "STOP_SCHEMA_VERSION",
    "AssessmentSchemaError",
    "FieldMapSchemaError",
    "FocusSynthesisSchemaError",
    "ProposalSchemaError",
    "ReportRunHandle",
    "ReportRunState",
    "ResearchContractError",
    "ResearchOrchestratorError",
    "ResearchOrchestratorPaused",
    "ResearchOrchestratorRuntime",
    "ResearchPackage",
    "ResearchReportError",
    "ResearchRunConfig",
    "ResearchSourcePackage",
    "ResearchSyncResult",
    "ResearchSyncSourceError",
    "ResearchTargetError",
    "ScanBatch",
    "append_research_event",
    "assess_contract",
    "attach_source_package_refs",
    "build_assessment_artifact",
    "build_assessment_from_analysis",
    "build_assessment_from_landscapes",
    "build_field_map_artifact",
    "build_focus_synthesis_artifact",
    "build_proposal_from_assessment",
    "build_research_landscape",
    "build_selected_evidence_artifact",
    "create_report_run",
    "ensure_research_manifest",
    "evaluate_research_stop",
    "field_map_contract",
    "focus_contract",
    "load_research_package",
    "load_research_run_config_file",
    "materialize_landscape_source_package",
    "propose_contract",
    "read_events",
    "read_state",
    "record_event",
    "render_final_research_report_markdown",
    "render_markdown_with_research_citations",
    "render_research_artifact_markdown",
    "research_contract",
    "resolve_research_run_config",
    "resume_report_run",
    "scaffold_suggestion",
    "sync_assessment_artifact",
    "sync_focus_artifact",
    "sync_landscape_artifact",
    "sync_materialization",
    "sync_proposal_artifact",
    "validate_assessment_artifact",
    "validate_assessment_grounding",
    "validate_assessment_relation",
    "validate_field_map_artifact",
    "validate_focus_synthesis_artifact",
    "validate_proposal_artifact",
    "validate_proposal_record",
    "verify_core_contract",
    "write_research_artifact",
    "write_state",
]
