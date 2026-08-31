# vNext Boundary: execution/admission

SYSTEM = "execution"
NODE = "execution/admission"
OWNS = "hierarchical execution quotas, identity-aware admission decisions and lease accounting"
MUST_NOT_OWN = "scheduling order/fairness, executor lifecycle or model/environment truth"
AUTHORITY = "admission_decision"

# This module is intentionally declarative. Concrete behavior belongs in runtime/providers.


from research_platform.platform.kernel.leaf_contract import SystemLeafContract


CONTRACT = SystemLeafContract(
    system_id="execution",
    node="execution/admission",
    package_prefix='research_platform.execution.admission',
    authority_id="admission_decision",
    owns="hierarchical execution quotas, identity-aware admission decisions and lease accounting",
    must_not_own="scheduling order/fairness, executor lifecycle or model/environment truth",
    api_module='research_platform.execution.admission.api',
    runtime_module='research_platform.execution.admission.runtime',
    provider_module='research_platform.execution.admission.providers',
    composition_module='research_platform.execution.admission.composition',
)


def contract() -> SystemLeafContract:
    return CONTRACT
