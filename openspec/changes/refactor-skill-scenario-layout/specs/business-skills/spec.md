## ADDED Requirements

### Requirement: Scenario-Centric Skill Layout
The system SHALL organize fixed business scenarios as self-contained directories under their parent domain.

#### Scenario: Store a fixed scenario as a self-contained package
- **WHEN** a domain defines a fixed scenario
- **THEN** the scenario SHALL live under `domains/<domain>/scenarios/<scenario_name>/`
- **AND** the scenario metadata SHALL be defined in `scenario.py`
- **AND** the scenario-specific SQL and scripts SHALL be stored under that scenario directory

#### Scenario: Store reusable assets separately from scenario-local assets
- **WHEN** an asset is intended to be reused by multiple scenarios in the same domain
- **THEN** the asset SHALL be stored under `domains/<domain>/shared/`
- **AND** scenario-local assets SHALL remain in the scenario directory

### Requirement: Automatic Skill and Scenario Discovery
The system SHALL automatically discover valid domain skills and scenario skills from the filesystem without manual registry edits.

#### Scenario: Register a new scenario without editing the registry module
- **WHEN** a maintainer adds a valid `scenarios/<scenario_name>/scenario.py` under an existing domain
- **THEN** the system SHALL discover that scenario during skill registry assembly
- **AND** the scenario SHALL be returned by `list_scenarios_by_skill()`
- **AND** the scenario SHALL be loadable through `load_scenario_content()`

#### Scenario: Reject invalid scenario packaging
- **WHEN** a discovered scenario directory has a name that does not match `SCENARIO["name"]`
- **OR** the scenario references a different `skill_name` than its parent domain
- **THEN** the registry assembly SHALL fail with a clear error

### Requirement: Scoped Asset Resolution
The system SHALL resolve skill assets relative to an explicit ownership scope instead of requiring full domain-relative path strings.

#### Scenario: Resolve scenario-local assets
- **WHEN** a scenario asset is declared with `scope="scenario"` and a relative `path`
- **THEN** the asset SHALL be resolved relative to the current scenario directory

#### Scenario: Resolve shared domain assets
- **WHEN** a scenario asset is declared with `scope="shared"` and a relative `path`
- **THEN** the asset SHALL be resolved relative to the parent domain `shared/` directory

#### Scenario: Preserve runtime loading interfaces after the refactor
- **WHEN** the system loads a discovered domain or scenario
- **THEN** `load_skill()` and `load_scenario()` SHALL continue to work without changes to their public call signatures
