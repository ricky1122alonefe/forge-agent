"""Dashboard data layer — typed access to manifest, traces, metrics, code, and reports."""

from forge_agent.dashboard.data.manifest import AgentInfo, VersionInfo, load_manifest
from forge_agent.dashboard.data.reports import ReportDataSource, ReportDetail, ReportSummary

__all__ = [
    "AgentInfo",
    "ReportDataSource",
    "ReportDetail",
    "ReportSummary",
    "VersionInfo",
    "load_manifest",
]
