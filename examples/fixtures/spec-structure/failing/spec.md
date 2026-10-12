# Feature Specification: Widget Import

**Feature Branch**: `fixture/failing`

## User Scenarios & Testing

A user imports widgets from a CSV file produced by another tool.

## Requirements

### Functional Requirements

- **FR-001**: The system MUST parse an uploaded CSV file into widget records.
- **FR-002**: The import MUST reject rows whose name column is empty.
- **FR-003**: The import MUST report how many rows were imported and rejected.
